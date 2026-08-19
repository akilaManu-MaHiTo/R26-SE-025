"""Conversation analyzer (AI 1) + pair extraction. Groq is mocked.

Run:
  python -m unittest VivaEvaluationEngine.tests.test_conversation_understanding -v
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
    format_clock,
    full_transcript_text,
)
from services.conversation_understanding import (
    apply_conversation_understanding,
    chunks_for_budget,
    merge_turn_types,
    pairs_from_segments,
    resolve_segments,
    understand_conversation,
)
from services.qa_relevance import attach_qa_analysis


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


PG_Q = "Can you explain why you selected PostgreSQL?"
PG_A = "We selected PostgreSQL because our data has strong relationships."
TX_Q = "How did you handle concurrent transactions?"
TX_A = "We use database transactions and locking."
DEPLOY = "For deployment we use Docker and nginx."


def _mixed_conversation():
    words, segments = _dialogue(
        ("SPEAKER_00", "Today I will explain our project architecture."),
        ("SPEAKER_01", PG_Q),
        ("SPEAKER_00", PG_A),
        ("SPEAKER_01", "Okay, move to the deployment section."),
        ("SPEAKER_00", DEPLOY),
        ("SPEAKER_01", TX_Q),
        ("SPEAKER_00", TX_A),
    )
    return build_conversation(words, segments, student_speaker="SPEAKER_00")


def _structure_payload():
    return {
        "segments": [
            {"type": "presentation", "turn_ids": ["T00"]},
            {"type": "panel_question", "turn_ids": ["T01"]},
            {"type": "student_answer", "turn_ids": ["T02"]},
            {"type": "instruction", "turn_ids": ["T03"]},
            {"type": "presentation", "turn_ids": ["T04"]},
            {"type": "panel_question", "turn_ids": ["T05"]},
            {"type": "student_answer", "turn_ids": ["T06"]},
        ]
    }


class TranscriptContractTests(unittest.TestCase):
    def test_format_clock(self):
        self.assertEqual(format_clock(4.32), "00:04.32")
        self.assertEqual(format_clock(251.2), "04:11.20")

    def test_labeled_transcript_uses_roles_and_end_times(self):
        conversation = _mixed_conversation()
        text = conversation["labeled_transcript"]
        self.assertIn("] STUDENT\n", text)
        self.assertIn("] PANEL_01\n", text)
        self.assertNotIn("SPEAKER_", text)
        self.assertNotIn("PANEL\n", text.replace("PANEL_01", ""))
        prompt = full_transcript_text(conversation["turns"], include_turn_ids=True)
        self.assertTrue(prompt.startswith("T00 "))
        self.assertIn("T01 [", prompt)


class ResolveTests(unittest.TestCase):
    def test_drops_unknown_ids_and_nested_qa(self):
        turns = [
            {"turn_id": "T00", "start": 0, "end": 10, "label": "STUDENT", "role": "student", "text": "Hello"},
            {"turn_id": "T01", "start": 11, "end": 14, "label": "PANEL_01", "role": "panel", "text": "Why Postgres?"},
            {"turn_id": "T02", "start": 15, "end": 20, "label": "STUDENT", "role": "student", "text": "Relations."},
        ]
        resolved = resolve_segments(
            [
                {"type": "presentation", "turn_ids": ["T00", "T99"]},
                {
                    "type": "qa",
                    "question": {"turn_ids": ["T01"]},
                    "answer": {"turn_ids": ["T02"]},
                },
            ],
            turns,
        )
        self.assertEqual([item["type"] for item in resolved], ["presentation", "panel_question", "student_answer"])
        self.assertEqual(resolved[0]["turn_ids"], ["T00"])
        self.assertEqual(resolved[1]["start"], 11)
        self.assertEqual(resolved[2]["text"], "Relations.")

    def test_pairs_skip_instruction_and_presentation(self):
        turns = [
            {"turn_id": "T00", "start": 0, "end": 10, "label": "STUDENT", "role": "student", "speaker_id": "SPEAKER_00", "text": "Intro"},
            {"turn_id": "T01", "start": 11, "end": 14, "label": "PANEL_01", "role": "panel", "speaker_id": "SPEAKER_01", "text": PG_Q},
            {"turn_id": "T02", "start": 15, "end": 20, "label": "STUDENT", "role": "student", "speaker_id": "SPEAKER_00", "text": PG_A},
            {"turn_id": "T03", "start": 21, "end": 23, "label": "PANEL_01", "role": "panel", "speaker_id": "SPEAKER_01", "text": "Move on."},
            {"turn_id": "T04", "start": 24, "end": 30, "label": "STUDENT", "role": "student", "speaker_id": "SPEAKER_00", "text": DEPLOY},
        ]
        segments = resolve_segments(
            [
                {"type": "presentation", "turn_ids": ["T00"]},
                {"type": "panel_question", "turn_ids": ["T01"]},
                {"type": "student_answer", "turn_ids": ["T02"]},
                {"type": "instruction", "turn_ids": ["T03"]},
                {"type": "presentation", "turn_ids": ["T04"]},
            ],
            turns,
        )
        pairs = pairs_from_segments(segments, turns)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["question"], PG_Q)
        self.assertEqual(pairs[0]["answer"], PG_A)
        self.assertEqual(pairs[0]["question_start"], 11)

    def test_later_window_wins_on_overlap(self):
        turns = [
            {"turn_id": "T00", "start": 0, "end": 5, "label": "STUDENT", "role": "student", "text": "A"},
            {"turn_id": "T01", "start": 6, "end": 8, "label": "PANEL_01", "role": "panel", "text": "B"},
            {"turn_id": "T02", "start": 9, "end": 12, "label": "STUDENT", "role": "student", "text": "C"},
        ]
        first = resolve_segments(
            [
                {"type": "presentation", "turn_ids": ["T00"]},
                {"type": "panel_question", "turn_ids": ["T01"]},
                {"type": "student_answer", "turn_ids": ["T02"]},
            ],
            turns,
        )
        second = resolve_segments(
            [
                {"type": "instruction", "turn_ids": ["T01"]},
                {"type": "return_to_presentation", "turn_ids": ["T02"]},
            ],
            turns,
        )
        merged = merge_turn_types([first, second], turns)
        types = [item["type"] for item in merged]
        self.assertEqual(types, ["presentation", "instruction", "return_to_presentation"])

    def test_one_shot_when_under_budget(self):
        turns = [{"turn_id": "T00", "start": 0, "end": 1, "label": "STUDENT", "text": "short"}]
        chunks = chunks_for_budget(turns, char_budget=40_000)
        self.assertEqual(len(chunks), 1)


class UnderstandingTests(unittest.TestCase):
    def test_student_only_skips_groq(self):
        words, segments = _dialogue(("SPEAKER_00", "Today I will explain the whole system in detail."))
        conversation = build_conversation(words, segments, student_speaker="SPEAKER_00")

        def boom(*_args, **_kwargs):
            raise AssertionError("AI 1 must not run for student-only recordings")

        updated = apply_conversation_understanding(conversation, groq_call=boom)
        self.assertEqual(updated["structure"]["status"], "skipped")
        self.assertEqual(updated["pair_count"], 0)
        self.assertTrue(all(turn["label"] == "STUDENT" for turn in updated["turns"]))

    def test_mixed_presentation_qa_resume(self):
        conversation = _mixed_conversation()
        calls = []

        def fake_structure(transcript, _key, _model):
            calls.append(transcript)
            self.assertIn("T00 ", transcript)
            self.assertIn("PANEL_01", transcript)
            return json.dumps(_structure_payload())

        updated = apply_conversation_understanding(
            conversation,
            groq_call=fake_structure,
            api_key="gsk_test",
            model="llama-test",
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(updated["structure"]["source"], "llm")
        self.assertEqual(updated["pair_count"], 2)
        self.assertEqual(updated["pair_candidates"][0]["question"], PG_Q)
        self.assertEqual(updated["pair_candidates"][1]["question"], TX_Q)
        self.assertNotIn("deployment section", " ".join(p["question"] for p in updated["pair_candidates"]))
        phases = [turn["phase"] for turn in updated["turns"]]
        self.assertEqual(
            phases,
            [
                "presentation",
                "panel_question",
                "student_answer",
                "instruction",
                "presentation",
                "panel_question",
                "student_answer",
            ],
        )
        self.assertEqual(updated["turns"][4]["text"], DEPLOY)

    def test_invalid_json_falls_back_to_heuristic(self):
        conversation = _mixed_conversation()
        heuristic_count = conversation["pair_count"]
        self.assertGreaterEqual(heuristic_count, 1)

        updated = apply_conversation_understanding(
            conversation,
            groq_call=lambda *_a, **_k: "not-json",
            api_key="gsk_test",
            model="x",
        )
        self.assertEqual(updated["structure"]["source"], "heuristic")
        self.assertEqual(updated["structure"]["status"], "fallback")
        self.assertEqual(updated["pair_count"], heuristic_count)

    def test_no_key_falls_back(self):
        conversation = _mixed_conversation()

        def boom(*_a, **_k):
            raise AssertionError("Groq should not be called without a key")

        with patch("services.conversation_understanding._api_key", return_value=None):
            updated = apply_conversation_understanding(conversation, groq_call=boom, api_key=None)
        self.assertEqual(updated["structure"]["status"], "fallback")
        self.assertGreater(updated["pair_count"], 0)

    def test_understand_conversation_skip_has_no_model_call(self):
        words, segments = _dialogue(("SPEAKER_00", "Just a student talking the whole time."))
        conversation = build_conversation(words, segments, student_speaker="SPEAKER_00")

        def boom(*_a, **_k):
            raise AssertionError("skip path must not call Groq")

        result = understand_conversation(conversation["turns"], groq_call=boom, api_key="gsk_test")
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["source"], "heuristic")


class AttachPipelineTests(unittest.TestCase):
    def test_attach_uses_ai1_pairs_for_ai2_only(self):
        conversation = _mixed_conversation()
        pair_questions = []

        def fake_structure(_transcript, _key, _model):
            return json.dumps(_structure_payload())

        def fake_pair(question, answer, _key, _model):
            pair_questions.append(question)
            return json.dumps(
                {
                    "addresses_question": True,
                    "relevance": "high",
                    "answer_type": "direct",
                    "explanation": "Addresses the asked topic.",
                    "confidence": 0.9,
                }
            )

        result = {"audio_analysis": {"conversation": conversation}}
        with patch("services.conversation_understanding._api_key", return_value="gsk_test"):
            with patch("services.qa_relevance._api_key", return_value="gsk_test"):
                with patch("services.qa_relevance._model_name", return_value="llama-test"):
                    enriched = attach_qa_analysis(
                        result,
                        groq_call=fake_pair,
                        structure_groq_call=fake_structure,
                    )

        self.assertEqual(pair_questions, [PG_Q, TX_Q])
        qa = enriched["qa_analysis"]
        self.assertEqual(qa["pair_count"], 2)
        self.assertEqual(qa["status"], "success")
        structure = enriched["audio_analysis"]["conversation"]["structure"]
        self.assertEqual(structure["source"], "llm")
        self.assertEqual(enriched["audio_analysis"]["conversation"]["turns"][3]["phase"], "instruction")
        self.assertEqual(enriched["audio_analysis"]["conversation"]["turns"][4]["phase"], "presentation")

    def test_attach_student_only_calls_neither_model(self):
        words, segments = _dialogue(("SPEAKER_00", "I will present the entire project now."))
        conversation = build_conversation(words, segments, student_speaker="SPEAKER_00")

        def boom(*_a, **_k):
            raise AssertionError("student-only must not call Groq")

        result = {"audio_analysis": {"conversation": conversation}}
        with patch("services.qa_relevance._api_key", return_value="gsk_test"):
            enriched = attach_qa_analysis(result, groq_call=boom, structure_groq_call=boom)
        self.assertEqual(enriched["qa_analysis"]["status"], "empty")
        self.assertEqual(enriched["qa_analysis"]["pair_count"], 0)
        self.assertEqual(enriched["audio_analysis"]["conversation"]["structure"]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
