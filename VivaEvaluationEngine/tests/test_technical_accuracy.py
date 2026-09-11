"""Technical-accuracy concept scoring (mocked Groq, no network).

Run:
  python -m unittest VivaEvaluationEngine.tests.test_technical_accuracy -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from services.technical_accuracy import (
    attach_technical_accuracy,
    run_technical_accuracy,
    score_concepts_batch,
    validate_batch_payload,
    validate_concept_result,
)


def _rubric(*concepts):
    return {"concepts": [{"id": cid, "name": name, "description": desc, "weight": weight} for cid, name, desc, weight in concepts]}


def _result_with_transcript(transcript: str):
    return {
        "audio_analysis": {
            "conversation": {"full_transcript": transcript},
        }
    }


class SchemaTests(unittest.TestCase):
    def test_valid_concept_result(self):
        item = {"concept_id": "c1", "covered": True, "correct": True, "evidence_quote": "we used 3NF", "score": 0.9}
        validated = validate_concept_result(item, "c1")
        self.assertEqual(validated["score"], 0.9)
        self.assertTrue(validated["covered"])

    def test_wrong_concept_id_rejected(self):
        item = {"concept_id": "c2", "covered": True, "correct": True, "evidence_quote": "x", "score": 0.9}
        self.assertIsNone(validate_concept_result(item, "c1"))

    def test_not_covered_forces_correct_none(self):
        item = {"concept_id": "c1", "covered": False, "correct": True, "evidence_quote": None, "score": 0}
        validated = validate_concept_result(item, "c1")
        self.assertIsNone(validated["correct"])

    def test_batch_payload_length_mismatch_rejected(self):
        payload = {"concepts": [{"concept_id": "c1", "covered": True, "correct": True, "score": 1}]}
        self.assertIsNone(validate_batch_payload(payload, ["c1", "c2"]))

    def test_batch_payload_order_preserved(self):
        payload = {
            "concepts": [
                {"concept_id": "c1", "covered": True, "correct": True, "score": 1},
                {"concept_id": "c2", "covered": False, "correct": None, "score": 0},
            ]
        }
        validated = validate_batch_payload(payload, ["c1", "c2"])
        self.assertEqual([c["concept_id"] for c in validated], ["c1", "c2"])


class ScoreBatchTests(unittest.TestCase):
    def test_mocked_groq_success(self):
        concepts = [{"id": "c1", "name": "Normalization", "description": "3NF"}]

        def fake_groq(transcript, batch, api_key, model):
            return json.dumps(
                {"concepts": [{"concept_id": "c1", "covered": True, "correct": True, "evidence_quote": "we normalized to 3NF", "score": 0.95}]}
            )

        result = score_concepts_batch(
            "we normalized to 3NF", concepts, api_key="gsk_test", model="test-model", groq_call=fake_groq
        )
        self.assertEqual(result[0]["score"], 0.95)

    def test_invalid_json_retries_then_raises(self):
        concepts = [{"id": "c1", "name": "Normalization", "description": "3NF"}]

        def fake_groq(transcript, batch, api_key, model):
            return "not json"

        with self.assertRaises(RuntimeError):
            score_concepts_batch(
                "x", concepts, api_key="gsk_test", model="test-model", groq_call=fake_groq
            )


class RunTechnicalAccuracyTests(unittest.TestCase):
    def test_no_rubric_is_skipped(self):
        result = run_technical_accuracy(_result_with_transcript("hello"), None)
        self.assertEqual(result["status"], "skipped")
        self.assertIsNone(result["overall_score"])

    def test_no_transcript_is_unavailable(self):
        rubric = _rubric(("c1", "Normalization", "3NF", 1))
        with patch("services.technical_accuracy._api_key", return_value="gsk_test"):
            result = run_technical_accuracy(_result_with_transcript(""), rubric)
        self.assertEqual(result["status"], "unavailable")

    def test_no_api_key_is_unavailable(self):
        rubric = _rubric(("c1", "Normalization", "3NF", 1))
        with patch("services.technical_accuracy._api_key", return_value=None):
            result = run_technical_accuracy(_result_with_transcript("some transcript"), rubric)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("API key", result["error"])

    def test_weighted_overall_score(self):
        rubric = _rubric(
            ("c1", "Normalization", "3NF", 3.0),
            ("c2", "Indexing", "B-tree index", 1.0),
        )

        def fake_groq(transcript, batch, api_key, model):
            payload = {
                "concepts": [
                    {
                        "concept_id": c["id"],
                        "covered": True,
                        "correct": True,
                        "evidence_quote": "evidence",
                        "score": 1.0 if c["id"] == "c1" else 0.0,
                    }
                    for c in batch
                ]
            }
            return json.dumps(payload)

        with patch("services.technical_accuracy._api_key", return_value="gsk_test"), patch(
            "services.technical_accuracy._model_name", return_value="test-model"
        ):
            result = run_technical_accuracy(
                _result_with_transcript("we normalized to 3NF"), rubric, groq_call=fake_groq
            )
        self.assertEqual(result["status"], "success")
        # weighted: (3*1.0 + 1*0.0) / 4 * 10 = 7.5
        self.assertEqual(result["overall_score"], 7.5)
        self.assertEqual(len(result["concepts"]), 2)

    def test_batches_run_and_partial_failure_reported(self):
        concepts = [(f"c{i}", f"Concept {i}", "desc", 1) for i in range(1, 15)]
        rubric = _rubric(*concepts)

        def flaky_groq(transcript, batch, api_key, model):
            # Deterministically fail whichever batch contains the first concept,
            # regardless of thread scheduling order.
            if any(c["id"] == "c1" for c in batch):
                raise RuntimeError("simulated network failure")
            payload = {
                "concepts": [
                    {"concept_id": c["id"], "covered": True, "correct": True, "evidence_quote": "e", "score": 0.5}
                    for c in batch
                ]
            }
            return json.dumps(payload)

        with patch("services.technical_accuracy._api_key", return_value="gsk_test"), patch(
            "services.technical_accuracy._model_name", return_value="test-model"
        ):
            result = run_technical_accuracy(
                _result_with_transcript("transcript text"), rubric, groq_call=flaky_groq
            )
        # 14 concepts / batch size 12 => 2 batches; one batch fails all retries.
        self.assertIn(result["status"], {"partial"})
        self.assertTrue(result["error"])


class AttachTests(unittest.TestCase):
    def test_attach_adds_key_without_mutating_input(self):
        original = _result_with_transcript("transcript")
        with patch("services.technical_accuracy._api_key", return_value=None):
            enriched = attach_technical_accuracy(original, None)
        self.assertNotIn("technical_accuracy_ai", original)
        self.assertIn("technical_accuracy_ai", enriched)
        self.assertEqual(enriched["technical_accuracy_ai"]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
