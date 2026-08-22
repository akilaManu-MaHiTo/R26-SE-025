"""Q&A pairing + semantic relevance (mocked Groq, no network).

Run:
  python -m unittest VivaEvaluationEngine.tests.test_qa_relevance -v
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

from services.conversation import (
    build_conversation,
    build_turns,
    is_panel_question,
    pair_question_answers,
)
from services.qa_relevance import (
    analyze_pair,
    attach_qa_analysis,
    validate_relevance_payload,
)


def _utterance(speaker: str, start: float, text: str, word_dur: float = 0.25):
    words = []
    t = start
    for token in text.split():
        words.append({"word": token, "start": round(t, 3), "end": round(t + word_dur, 3)})
        t += word_dur + 0.05
    segments = [{"start": start, "end": round(t, 3), "speaker": speaker}]
    return words, segments, round(t, 3)


def _dialogue(*utterances):
    words = []
    segments = []
    t = 0.0
    for speaker, text in utterances:
        t += 0.4
        w, segs, end = _utterance(speaker, t, text)
        words.extend(w)
        segments.extend(segs)
        t = end + 1.5
    return words, segments


YOLO_Q = "What AI model did you use in your project?"
YOLO_A = "We used YOLOv8 for object detection and trained it on our custom dataset."
WALK_A = "I was walking to the university yesterday..."
PG_Q = "Why did you choose PostgreSQL?"
PG_A = "Because it is very good for databases."


class PairingTests(unittest.TestCase):
    def test_three_example_pairs(self):
        words, segments = _dialogue(
            ("SPEAKER_00", "Welcome everyone this is my project presentation."),
            ("SPEAKER_01", YOLO_Q),
            ("SPEAKER_00", YOLO_A),
            ("SPEAKER_01", "What AI model did you use in your project?"),
            ("SPEAKER_00", WALK_A),
            ("SPEAKER_01", PG_Q),
            ("SPEAKER_00", PG_A),
        )
        conversation = build_conversation(words, segments, student_speaker="SPEAKER_00")
        pairs = conversation["pair_candidates"]
        self.assertEqual(conversation["pair_count"], 3)
        self.assertEqual(pairs[0]["question"], YOLO_Q)
        self.assertEqual(pairs[0]["answer"], YOLO_A)
        self.assertEqual(pairs[1]["answer"], WALK_A)
        self.assertEqual(pairs[2]["question"], PG_Q)
        self.assertEqual(pairs[2]["answer"], PG_A)
        self.assertTrue(all(p["panel_speaker"] == "SPEAKER_01" for p in pairs))

    def test_opening_monologue_skipped(self):
        words, segments = _dialogue(
            ("SPEAKER_00", "I will now present my three tier architecture."),
            ("SPEAKER_01", "What is the architecture of your application?"),
            ("SPEAKER_00", "We use a three-tier architecture."),
        )
        pairs = pair_question_answers(build_turns(words, segments, "SPEAKER_00"))
        self.assertEqual(len(pairs), 1)
        self.assertIn("three-tier", pairs[0]["answer"])

    def test_unanswered_question_emits_empty_answer(self):
        words, segments = _dialogue(
            ("SPEAKER_01", "What operating system does your application support?"),
            ("SPEAKER_01", "Why did you choose that architecture?"),
            ("SPEAKER_00", "Because it separates presentation and data."),
        )
        pairs = pair_question_answers(build_turns(words, segments, "SPEAKER_00"))
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0]["answer"], "")
        self.assertIn("separates", pairs[1]["answer"])

    def test_student_only_monologue_has_no_qa_pairs(self):
        words, segments = _dialogue(
            (
                "SPEAKER_00",
                "So if you go last an even longer period of time. You can just get it over with and sit back and relax.",
            ),
        )
        conversation = build_conversation(words, segments, student_speaker="SPEAKER_00")
        self.assertEqual(conversation["pair_count"], 0)
        self.assertFalse(conversation["has_panel"])
        self.assertIsNone(conversation["qa_start"])
        self.assertTrue(all(turn["role"] == "student" for turn in conversation["turns"]))
        self.assertTrue(all(turn["phase"] == "presentation" for turn in conversation["turns"]))
        self.assertIn("STUDENT", conversation["full_transcript"])
        self.assertRegex(conversation["full_transcript"], r"\[\d{2}:\d{2}\.\d{2} - \d{2}:\d{2}\.\d{2}\] STUDENT")
        self.assertEqual(conversation["turns"][0]["turn_id"], "T00")

    def test_off_camera_voice_starts_qa_after_presentation(self):
        words, segments = _dialogue(
            ("SPEAKER_00", "Today I will present my three tier architecture."),
            ("SPEAKER_01", "Please comment on the database you selected."),
            ("SPEAKER_00", "We used PostgreSQL for transactions."),
        )
        conversation = build_conversation(words, segments, student_speaker="SPEAKER_00")
        self.assertTrue(conversation["has_panel"])
        self.assertEqual(conversation["turns"][0]["phase"], "presentation")
        self.assertEqual(conversation["turns"][1]["phase"], "qa")
        self.assertEqual(conversation["turns"][2]["phase"], "qa")
        self.assertEqual(conversation["pair_count"], 1)
        self.assertIn("PostgreSQL", conversation["pair_candidates"][0]["answer"])
        self.assertIn("PANEL_01", conversation["full_transcript"])
        self.assertIn("STUDENT", conversation["full_transcript"])
        self.assertNotIn("SPEAKER_00", conversation["full_transcript"])
        self.assertRegex(conversation["full_transcript"], r"\[\d{2}:\d{2}\.\d{2} - \d{2}:\d{2}\.\d{2}\] PANEL_01")
        turn = {"role": "panel", "text": "Explain your database choice"}
        self.assertTrue(is_panel_question(turn))
        self.assertFalse(is_panel_question({"role": "student", "text": "What time is it?"}))
        self.assertFalse(is_panel_question({"role": "panel", "text": "Please continue with the demo."}))


class SchemaTests(unittest.TestCase):
    def test_valid_payload(self):
        parsed = validate_relevance_payload(
            {
                "addresses_question": True,
                "relevance": "high",
                "answer_type": "direct",
                "explanation": "The student names the model and how it was used.",
                "confidence": 0.98,
            }
        )
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed["addresses_question"])
        self.assertEqual(parsed["relevance"], "high")

    def test_rejects_bad_relevance(self):
        self.assertIsNone(
            validate_relevance_payload(
                {
                    "addresses_question": False,
                    "relevance": "somewhat",
                    "answer_type": "direct",
                    "explanation": "nope",
                    "confidence": 0.5,
                }
            )
        )

    def test_accepts_string_bool(self):
        parsed = validate_relevance_payload(
            {
                "addresses_question": "false",
                "relevance": "irrelevant",
                "answer_type": "irrelevant",
                "explanation": "Does not address the question.",
                "confidence": 0.99,
            }
        )
        self.assertIsNotNone(parsed)
        self.assertFalse(parsed["addresses_question"])


class AnalyzePairTests(unittest.TestCase):
    def test_empty_answer_skips_groq(self):
        def boom(*_args, **_kwargs):
            raise AssertionError("Groq should not be called for an empty answer")

        result = analyze_pair(
            {"question": YOLO_Q, "answer": "", "panel_label": "PANEL"},
            api_key="gsk_test",
            model="llama-3.3-70b-versatile",
            groq_call=boom,
        )
        self.assertEqual(result["answer_type"], "no_answer")
        self.assertFalse(result["addresses_question"])
        self.assertEqual(result["source"], "rule")

    def test_mocked_groq_yolo_relevant(self):
        payload = {
            "addresses_question": True,
            "relevance": "high",
            "answer_type": "direct",
            "explanation": "The student directly identifies the AI model and explains how it was used.",
            "confidence": 0.98,
        }

        def fake_groq(question, answer, _key, _model):
            self.assertEqual(question, YOLO_Q)
            self.assertIn("YOLOv8", answer)
            return json.dumps(payload)

        result = analyze_pair(
            {"question": YOLO_Q, "answer": YOLO_A, "panel_label": "PANEL"},
            api_key="gsk_test",
            model="llama-3.3-70b-versatile",
            groq_call=fake_groq,
        )
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["addresses_question"])
        self.assertEqual(result["relevance"], "high")
        self.assertEqual(result["answer_type"], "direct")

    def test_mocked_walking_irrelevant(self):
        def fake_groq(_q, _a, _k, _m):
            return json.dumps(
                {
                    "addresses_question": False,
                    "relevance": "irrelevant",
                    "answer_type": "irrelevant",
                    "explanation": "The answer does not address the question about the AI model used.",
                    "confidence": 0.99,
                }
            )

        result = analyze_pair(
            {"question": YOLO_Q, "answer": WALK_A},
            api_key="gsk_test",
            model="x",
            groq_call=fake_groq,
        )
        self.assertFalse(result["addresses_question"])
        self.assertEqual(result["relevance"], "irrelevant")

    def test_partial_postgres(self):
        def fake_groq(_q, _a, _k, _m):
            return json.dumps(
                {
                    "addresses_question": True,
                    "relevance": "medium",
                    "answer_type": "partial",
                    "explanation": "Related to databases but not a specific justification for PostgreSQL.",
                    "confidence": 0.91,
                }
            )

        result = analyze_pair(
            {"question": PG_Q, "answer": PG_A},
            api_key="gsk_test",
            model="x",
            groq_call=fake_groq,
        )
        self.assertTrue(result["addresses_question"])
        self.assertEqual(result["answer_type"], "partial")
        self.assertEqual(result["relevance"], "medium")

    def test_invalid_json_is_unavailable(self):
        result = analyze_pair(
            {"question": YOLO_Q, "answer": YOLO_A},
            api_key="gsk_test",
            model="x",
            groq_call=lambda *_a, **_k: "not-json",
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["relevance"])


class AttachTests(unittest.TestCase):
    def test_attach_uses_conversation_pairs(self):
        result = {
            "audio_analysis": {
                "conversation": {
                    "turns": [],
                    "pair_candidates": [
                        {"question": YOLO_Q, "answer": "", "panel_label": "PANEL"},
                        {"question": PG_Q, "answer": PG_A, "panel_label": "PANEL"},
                    ],
                }
            }
        }

        def fake_groq(_q, _a, _k, _m):
            return json.dumps(
                {
                    "addresses_question": True,
                    "relevance": "medium",
                    "answer_type": "partial",
                    "explanation": "Partial database reason.",
                    "confidence": 0.9,
                }
            )

        with patch("services.qa_relevance._api_key", return_value="gsk_test"):
            with patch("services.qa_relevance._model_name", return_value="llama-test"):
                enriched = attach_qa_analysis(result, groq_call=fake_groq)

        qa = enriched["qa_analysis"]
        self.assertEqual(qa["pair_count"], 2)
        self.assertEqual(qa["pairs"][0]["answer_type"], "no_answer")
        self.assertEqual(qa["pairs"][1]["source"], "llm")
        self.assertEqual(qa["status"], "success")


if __name__ == "__main__":
    unittest.main()
