from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
import sys

import httpx
import numpy as np
import pytest

from app.classifier import bloom_classifier
from app.classifier.rules import classify_by_rules
from app.config import settings
from app.services import llm_service


@pytest.fixture
def bloom_prediction(monkeypatch):
    prediction = {"label": "BT3", "level": "Apply", "confidence": 0.9,
                  "probs": {"BT3": 0.9}, "model_version": "modernbert-bloom-v1"}
    predict = Mock(return_value=prediction)
    monkeypatch.setattr(bloom_classifier, "is_bloom_model_available", lambda: True)
    monkeypatch.setattr(bloom_classifier, "predict_bloom", predict)
    return predict


def test_classify_question_infers_bloom_once(bloom_prediction):
    text = "Write a SQL SELECT query"
    expected_rules = llm_service._rules_dict(classify_by_rules(text))
    bloom_prediction.reset_mock()
    result = llm_service.classify_question(text)
    assert result == {"status": "bloom_model", "rules": expected_rules,
                      "bloom": bloom_prediction.return_value}
    bloom_prediction.assert_called_once_with(text)


def test_classify_question_still_requires_modernbert(monkeypatch):
    monkeypatch.setattr(bloom_classifier, "is_bloom_model_available", lambda: False)
    with pytest.raises(RuntimeError, match="Bloom ModernBERT not available"):
        llm_service.classify_question("Explain SQL")


async def test_bloom_endpoint_infers_once(bloom_prediction):
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/lecturers/bloom-predict", json={"text": "Write a SQL SELECT query"})
    assert response.status_code == 200
    assert response.json()["bloom"] == bloom_prediction.return_value
    assert response.json()["topic_hint"]
    bloom_prediction.assert_called_once()


@pytest.mark.parametrize("available, error, status", [
    (False, None, 503), (True, RuntimeError("checkpoint failure"), 500)])
async def test_bloom_endpoint_preserves_errors(monkeypatch, available, error, status):
    from app.main import app

    monkeypatch.setattr(bloom_classifier, "is_bloom_model_available", lambda: available)
    monkeypatch.setattr(bloom_classifier, "predict_bloom", Mock(side_effect=error))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/lecturers/bloom-predict", json={"text": "Explain SQL"})
    assert response.status_code == status
    assert "Bloom" in response.json()["detail"]


@pytest.fixture
def similarity_embedder(monkeypatch):
    from app.embeddings.embedder import Embedder

    vectors = {"candidate": np.array([1., 0.]), "opposite": np.array([-1., 0.]),
               "historical": np.array([1., 0.])}
    embedder = Embedder()
    monkeypatch.setattr(embedder, "embed", Mock(side_effect=lambda text: vectors[text]))
    monkeypatch.setattr(llm_service, "is_embedding_available", lambda: True)
    monkeypatch.setattr(llm_service, "_get_embedder", lambda: embedder)
    return embedder, vectors


def test_similarity_reuses_history_only_within_request(similarity_embedder):
    embedder, vectors = similarity_embedder
    parsed = SimpleNamespace(candidates=[SimpleNamespace(text="candidate"), SimpleNamespace(text="opposite")])
    recommendation = {"historical_questions": [
        {"question_text": "historical", "question_id": "first"},
        {"question_text": "historical", "question_id": "duplicate"}]}
    expected = [
        {"candidate_text": "candidate", "max_similarity": 1.0, "source_question_id": "first", "flagged": True},
        {"candidate_text": "opposite", "max_similarity": 0.0, "source_question_id": None, "flagged": False}]
    assert llm_service._similarity_checks(parsed, recommendation) == expected
    assert embedder.embed.call_count == 3
    vectors["historical"] = np.array([0., 1.])
    assert llm_service._similarity_checks(parsed, recommendation)[0]["max_similarity"] == 0.0
    assert embedder.embed.call_count == 6


def test_similarity_failure_still_degrades(similarity_embedder):
    embedder, _ = similarity_embedder
    embedder.embed.side_effect = RuntimeError("model unavailable")
    assert llm_service._similarity_checks(
        SimpleNamespace(candidates=[SimpleNamespace(text="candidate")]), {}) == []


def test_similarity_threshold_is_strict(similarity_embedder, monkeypatch):
    monkeypatch.setattr(settings, "candidate_similarity_threshold", 1.0)
    checks = llm_service._similarity_checks(
        SimpleNamespace(candidates=[SimpleNamespace(text="candidate")]),
        {"historical_questions": [{"question_text": "historical", "question_id": "first"}]})
    assert checks[0]["max_similarity"] == 1.0
    assert checks[0]["flagged"] is False


def test_bloom_first_load_is_shared_between_threads(monkeypatch):
    entered, release, duplicate, second_started = Event(), Event(), Event(), Event()
    models = []
    config = SimpleNamespace(id2label={0: "BT1"})

    def construct(_config):
        model = SimpleNamespace(eval=lambda: None, load_state_dict=lambda *a, **k: ([], []))
        models.append(model)
        if len(models) > 1:
            duplicate.set()
        entered.set()
        assert release.wait(5)
        return model

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "safetensors.torch", SimpleNamespace(load_file=lambda *a, **k: {}))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        AutoConfig=SimpleNamespace(from_pretrained=lambda *a, **k: config),
        AutoModelForSequenceClassification=SimpleNamespace(from_config=construct),
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a, **k: object())))
    monkeypatch.setattr(settings, "bloom_device", "cpu")
    bloom_classifier.reload_bloom_model()

    def second_load():
        second_started.set()
        return bloom_classifier.get_bloom_classifier()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(bloom_classifier.get_bloom_classifier)
            try:
                assert entered.wait(5)
                second = pool.submit(second_load)
                assert second_started.wait(5)
                duplicate.wait(0.2)
            finally:
                release.set()
            assert first.result(timeout=5)[0] is second.result(timeout=5)[0]
        assert len(models) == 1
    finally:
        bloom_classifier.reload_bloom_model()
