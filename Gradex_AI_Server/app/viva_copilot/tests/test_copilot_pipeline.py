"""Unit tests for the isolated copilot pipeline (mocked Groq)."""
from __future__ import annotations

import json
import unittest

from Gradex_AI_Server.app.viva_copilot.answer_detector import (
    answer_hash,
    detect_final_answer,
    is_duplicate,
    normalize_answer,
)
from Gradex_AI_Server.app.viva_copilot.context_builder import build_llm_context
from Gradex_AI_Server.app.viva_copilot.followup_llm import (
    generate_followups,
    parse_followup_payload,
    validate_suggestions,
)
from Gradex_AI_Server.app.viva_copilot.groq_client import extract_json_object, friendly_groq_error, is_probable_hallucination
from Gradex_AI_Server.app.viva_copilot.pipeline import (
    enter_viva_phase,
    ingest_audio_chunk,
    should_refresh_presentation_suggestions,
    _finalize_utterance,
    _run_followups,
)
from Gradex_AI_Server.app.viva_copilot.session_store import CopilotSession


class AnswerDetectorTests(unittest.TestCase):
    def test_normalize_and_hash_stable(self):
        a = answer_hash("We use JWT authentication.")
        b = answer_hash("we use jwt authentication!")
        self.assertEqual(a, b)
        self.assertTrue(a)

    def test_duplicate_ignored(self):
        text = "We use JWT authentication with NestJS."
        digest = answer_hash(text)
        self.assertTrue(is_duplicate(text, [digest]))
        self.assertIsNone(detect_final_answer(text, [digest], min_words=5))

    def test_short_utterance_ignored(self):
        self.assertIsNone(detect_final_answer("Yes okay", [], min_words=5))

    def test_accepts_new_long_answer(self):
        text = "We use JWT authentication with NestJS for our API."
        self.assertEqual(detect_final_answer(text, [], min_words=5), text)


class FollowupValidationTests(unittest.TestCase):
    def test_parse_and_rank_top_three(self):
        raw = json.dumps(
            {
                "analysis": {
                    "topics": ["Authentication"],
                    "concepts": ["JWT"],
                    "technologies": ["NestJS"],
                    "claims": ["JWT is used"],
                    "gaps": ["Token expiration"],
                },
                "main_points": ["JWT access tokens"],
                "suggestions": [
                    {
                        "question": "How do you handle JWT token expiration?",
                        "reason": "Lifetime was not explained.",
                        "difficulty": "intermediate",
                        "priority": "high",
                    },
                    {
                        "question": "Where do you store the JWT on the client side and why?",
                        "reason": "Client storage is unexplored.",
                        "difficulty": "intermediate",
                        "priority": "medium",
                    },
                    {
                        "question": "How would you revoke a JWT before it expires?",
                        "reason": "Revocation is a common JWT challenge.",
                        "difficulty": "advanced",
                        "priority": "medium",
                    },
                    {
                        "question": "What is REST?",
                        "reason": "Unrelated extra.",
                        "difficulty": "basic",
                        "priority": "low",
                    },
                ],
            }
        )
        parsed = parse_followup_payload(raw, asked=[])
        self.assertEqual(len(parsed["suggestions"]), 3)
        self.assertEqual(parsed["suggestions"][0]["priority"], "high")
        self.assertEqual(parsed["analysis"]["topics"], ["Authentication"])
        self.assertEqual(parsed["main_points"], ["JWT access tokens"])

    def test_drops_asked_duplicates(self):
        suggestions = validate_suggestions(
            [
                {
                    "question": "How do you handle JWT token expiration?",
                    "reason": "Gap.",
                    "difficulty": "intermediate",
                    "priority": "high",
                }
            ],
            asked=["How do you handle JWT token expiration?"],
        )
        self.assertEqual(suggestions, [])

    def test_invalid_json_yields_empty(self):
        parsed = parse_followup_payload("not-json", asked=[])
        self.assertEqual(parsed["suggestions"], [])
        self.assertEqual(parsed["analysis"]["topics"], [])

    def test_generate_uses_injected_chat(self):
        def fake_chat(_system, payload):
            self.assertIn("sessionId", payload)
            return json.dumps(
                {
                    "analysis": {
                        "topics": ["Auth"],
                        "concepts": [],
                        "technologies": [],
                        "claims": [],
                        "gaps": ["expiry"],
                    },
                    "main_points": ["tokens"],
                    "suggestions": [
                        {
                            "question": "How do you handle JWT token expiration?",
                            "reason": "Not mentioned.",
                            "difficulty": "intermediate",
                            "priority": "high",
                        }
                    ],
                }
            )

        result = generate_followups({"sessionId": "session_001"}, asked=[], chat=fake_chat)
        self.assertEqual(len(result["suggestions"]), 1)
        self.assertEqual(result["main_points"], ["tokens"])


class ContextBuilderTests(unittest.TestCase):
    def test_sliding_window_keeps_last_pairs(self):
        pairs = [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(8)]
        ctx = build_llm_context(
            session_id="session_001",
            current_question="Latest Q",
            candidate_answer="Latest A",
            recent_qa=pairs,
            presentation_points=["JWT"],
        )
        speakers = [row["speaker"] for row in ctx["recentConversation"]]
        self.assertEqual(ctx["currentQuestion"]["text"], "Latest Q")
        self.assertLessEqual(len(ctx["recentConversation"]), 10)
        self.assertIn("interviewer", speakers)
        self.assertEqual(ctx["presentationPoints"], ["JWT"])


class GroqClientHelpersTests(unittest.TestCase):
    def test_extract_json_from_fences(self):
        parsed = extract_json_object('```json\n{"a": 1}\n```')
        self.assertEqual(parsed, {"a": 1})

    def test_hallucination_filter(self):
        self.assertTrue(is_probable_hallucination("Thank you."))
        self.assertFalse(is_probable_hallucination("We use JWT authentication with NestJS."))

    def test_normalize_answer(self):
        self.assertEqual(normalize_answer("  Hello, World! "), "hello world")

    def test_friendly_rate_limit_message(self):
        raw = '{"error":{"message":"Rate limit reached for model whisper-large-v3-turbo","code":"rate_limit_exceeded"}}'
        self.assertIn("rate limit", friendly_groq_error(raw, kind="Speech recognition").lower())

    def test_friendly_model_missing_message(self):
        raw = '{"error":{"message":"The model llama-3.3-70b-versatile does not exist","code":"model_not_found"}}'
        self.assertIn("not available", friendly_groq_error(raw, kind="Follow-up generation").lower())


class PipelineFlowTests(unittest.IsolatedAsyncioTestCase):
    def test_presentation_refresh_needs_bulk_new_words(self):
        self.assertFalse(
            should_refresh_presentation_suggestions(
                word_count_value=10, last_word_count=0, last_at=0, now=100
            )
        )
        self.assertTrue(
            should_refresh_presentation_suggestions(
                word_count_value=40, last_word_count=0, last_at=0, now=100
            )
        )
        self.assertFalse(
            should_refresh_presentation_suggestions(
                word_count_value=40, last_word_count=30, last_at=90, now=100, min_seconds=40
            )
        )

    async def test_presentation_bulk_suggestions_after_enough_words(self):
        session = CopilotSession(session_id="session_test")
        session.phase = "presentation"
        called = []

        def fake_generate(context, _asked):
            called.append(context["candidateAnswer"]["text"])
            return {
                "analysis": {"topics": ["Auth"], "concepts": [], "technologies": [], "claims": [], "gaps": []},
                "main_points": ["JWT"],
                "suggestions": [
                    {
                        "question": "How do you expire tokens?",
                        "reason": "Not covered yet.",
                        "difficulty": "intermediate",
                        "priority": "high",
                    }
                ],
            }

        await _finalize_utterance(
            session,
            "We use JWT authentication with NestJS for our API. ",
            generate=fake_generate,
        )
        self.assertEqual(called, [])

        long_talk = (
            "We use JWT authentication with NestJS for our API. "
            "The client stores the access token after login and sends it on each request. "
            "Guards validate the token before controllers run."
        )
        await _finalize_utterance(session, long_talk, generate=fake_generate)
        self.assertEqual(len(called), 1)
        self.assertEqual(len(session.suggestions), 1)
    async def test_panel_enter_generates_from_presentation(self):
        session = CopilotSession(session_id="session_test")
        session.presentation_parts = ["We use JWT authentication with NestJS for our API."]

        def fake_generate(context, _asked):
            self.assertIn("JWT", context["candidateAnswer"]["text"])
            return {
                "analysis": {
                    "topics": ["Authentication"],
                    "concepts": ["JWT"],
                    "technologies": ["NestJS"],
                    "claims": [],
                    "gaps": ["expiration"],
                },
                "main_points": ["JWT access tokens"],
                "suggestions": [
                    {
                        "question": "How do you handle JWT token expiration?",
                        "reason": "Lifetime was not explained.",
                        "difficulty": "intermediate",
                        "priority": "high",
                    }
                ],
            }

        await enter_viva_phase(session, generate=fake_generate)
        self.assertEqual(session.phase, "viva")
        self.assertEqual(session.main_points, ["JWT access tokens"])
        self.assertEqual(len(session.suggestions), 1)

    async def test_silence_after_speech_finalizes_presentation(self):
        session = CopilotSession(session_id="session_test")
        session.phase = "presentation"

        def transcribe_speech_sync(data, filename="chunk.webm", content_type="audio/webm"):
            return "We use JWT authentication with NestJS for our API."

        def transcribe_silence_sync(data, filename="chunk.webm", content_type="audio/webm"):
            return ""

        await ingest_audio_chunk(session, b"abc" * 400, transcribe=transcribe_speech_sync)
        self.assertTrue(session.utterance_buffer)
        await ingest_audio_chunk(session, b"abc" * 400, transcribe=transcribe_silence_sync)
        self.assertEqual(session.utterance_buffer, "")
        self.assertEqual(len(session.presentation_parts), 1)

    async def test_busy_stt_queues_chunks_fifo(self):
        session = CopilotSession(session_id="session_test")
        session.phase = "presentation"
        order: list[str] = []

        def transcribe(data, filename="chunk.webm", content_type="audio/webm"):
            order.append(data.decode())
            return ""

        session.stt_busy = True
        await ingest_audio_chunk(session, b"one", transcribe=transcribe)
        await ingest_audio_chunk(session, b"two", transcribe=transcribe)
        self.assertEqual(len(session.pending_audio), 2)
        session.stt_busy = False
        await ingest_audio_chunk(session, b"three", transcribe=transcribe)
        self.assertEqual(order, ["three", "one", "two"])
        self.assertEqual(len(session.pending_audio), 0)

    async def test_busy_llm_queues_followup(self):
        session = CopilotSession(session_id="session_test")
        session.phase = "viva"
        session.current_question = "What is JWT?"
        called: list[str] = []

        def fake_generate(context, _asked):
            called.append(context["candidateAnswer"]["text"])
            return {
                "analysis": {"topics": [], "concepts": [], "technologies": [], "claims": [], "gaps": []},
                "main_points": [],
                "suggestions": [
                    {
                        "question": "How do you expire tokens?",
                        "reason": "Not covered.",
                        "difficulty": "intermediate",
                        "priority": "high",
                    }
                ],
            }

        session.busy_llm = True
        await _finalize_utterance(
            session,
            "We use JWT authentication with NestJS for our API.",
            generate=fake_generate,
        )
        self.assertEqual(called, [])
        self.assertEqual(len(session.pending_followups), 1)
        session.busy_llm = False
        await _run_followups(
            session,
            "answer_flush",
            candidate_answer="Flush queued follow-up from the first answer now.",
            generate=fake_generate,
        )
        self.assertGreaterEqual(len(called), 2)


if __name__ == "__main__":
    unittest.main()
