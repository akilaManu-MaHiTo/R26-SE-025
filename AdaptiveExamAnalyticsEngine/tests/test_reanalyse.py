from types import SimpleNamespace

import pytest

from app.classifier import bloom_classifier
from app.services import student_pipeline


@pytest.mark.asyncio
@pytest.mark.parametrize("force_reclassify, expected_level", [(False, "Remember"), (True, "Analyze")])
async def test_reanalysis_refreshes_persistent_classification(monkeypatch, force_reclassify, expected_level):
    stored = {"level": "Remember", "topic": "Old topic", "confidence": 0.9}

    class Collection:
        async def find_one(self, query):
            return {"semantics": stored.copy()}

        async def update_one(self, query, update, **kwargs):
            stored.update(update["$set"]["semantics"])

    async def load_taxonomy(db, course_code):
        return {}

    monkeypatch.setattr("app.taxonomy.normalizer.load_taxonomy", load_taxonomy)
    monkeypatch.setattr(bloom_classifier, "is_bloom_model_available", lambda: True)
    monkeypatch.setattr(bloom_classifier, "predict_bloom_batch", lambda texts: [
        {"level": "Analyze", "label": "BT4", "confidence": 0.95} for text in texts
    ])
    normalized = SimpleNamespace(
        course_code="IT2040", rubric_ref="rubric",
        questions=[SimpleNamespace(question_no="01", question_text="Analyze database normalization")],
    )
    cache = {}
    result = await student_pipeline._classify_questions(
        normalized, cache, db={"bloom_classification_cache": Collection()},
        force_reclassify=force_reclassify,
    )
    assert result["01"].level == expected_level
    assert stored["level"] == expected_level

    # The same exam question is classified once, then reused across students.
    def unexpected_inference(texts):
        raise AssertionError("Duplicate inference for the same exam question")

    monkeypatch.setattr(bloom_classifier, "predict_bloom_batch", unexpected_inference)
    repeated = await student_pipeline._classify_questions(
        normalized, cache, db={"bloom_classification_cache": Collection()},
        force_reclassify=force_reclassify,
    )
    assert repeated["01"].level == expected_level
