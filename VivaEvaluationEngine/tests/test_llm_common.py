"""Shared LLM helpers: key / model / URL resolution, JSON extraction, and that every engine
module uses them (no network).

Run:
  python -m unittest VivaEvaluationEngine.tests.test_llm_common -v
"""
from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from services import llm_common
from services.llm_common import (
    API_KEY_ENV_VARS,
    COPILOT_API_KEY_ENV_VARS,
    COPILOT_MODEL_ENV_VARS,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    chat_url,
    extract_json_object,
    is_model_unavailable_error,
    post_chat_completion,
    resolve_api_key,
    resolve_model_name,
)

ALL_ENV_NAMES = (
    set(API_KEY_ENV_VARS)
    | set(COPILOT_API_KEY_ENV_VARS)
    | set(COPILOT_MODEL_ENV_VARS)
    | {"VIVA_LLM_MODEL", "GROQ_MODEL", "OPENAI_BASE_URL", "LLM_BASE_URL", "VIVA_LLM_BASE_URL"}
)


class _CleanEnv(unittest.TestCase):
    """Start every test with none of the LLM variables set and the .env files treated as loaded."""

    def setUp(self):
        patcher = patch.dict("os.environ", {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        import os

        for name in ALL_ENV_NAMES:
            os.environ.pop(name, None)
        loaded = patch.object(llm_common, "_ENV_LOADED", True)
        loaded.start()
        self.addCleanup(loaded.stop)


class ResolveApiKeyTests(_CleanEnv):
    def test_no_key_configured_is_none(self):
        self.assertIsNone(resolve_api_key())

    def test_first_name_in_the_list_wins(self):
        with patch.dict("os.environ", {"AI_API_KEY": "ai", "GROQ_API_KEY": "groq", "VIVA_LLM_API_KEY": "viva"}):
            self.assertEqual(resolve_api_key(), "viva")
        with patch.dict("os.environ", {"AI_API_KEY": "ai", "GROQ_API_KEY": "groq"}):
            self.assertEqual(resolve_api_key(), "groq")

    def test_blank_values_are_skipped_and_values_are_trimmed(self):
        with patch.dict("os.environ", {"VIVA_LLM_API_KEY": "   ", "GROQ_API_KEY": "  key  "}):
            self.assertEqual(resolve_api_key(), "key")

    def test_copilot_list_also_accepts_its_own_key(self):
        with patch.dict("os.environ", {"VIVA_COPILOT_API_KEY": "cop"}):
            self.assertIsNone(resolve_api_key())
            self.assertEqual(resolve_api_key(COPILOT_API_KEY_ENV_VARS), "cop")


class ResolveModelNameTests(_CleanEnv):
    def test_default_when_nothing_is_set(self):
        self.assertEqual(resolve_model_name(), DEFAULT_MODEL)

    def test_order_for_the_judge_and_for_the_copilot(self):
        with patch.dict("os.environ", {"GROQ_MODEL": "g", "VIVA_LLM_MODEL": "v", "VIVA_COPILOT_LLM_MODEL": "c"}):
            self.assertEqual(resolve_model_name(), "v")
            self.assertEqual(resolve_model_name(COPILOT_MODEL_ENV_VARS), "c")


class ChatUrlTests(_CleanEnv):
    def test_default_is_groq(self):
        self.assertEqual(chat_url(), f"{DEFAULT_BASE_URL}/chat/completions")

    def test_override_order_and_normalisation(self):
        with patch.dict("os.environ", {"VIVA_LLM_BASE_URL": "http://c.example/v1/"}):
            self.assertEqual(chat_url(), "http://c.example/v1/chat/completions")
        with patch.dict(
            "os.environ",
            {"VIVA_LLM_BASE_URL": "http://c.example/v1", "OPENAI_BASE_URL": "http://a.example/v1/chat/completions"},
        ):
            self.assertEqual(chat_url(), "http://a.example/v1/chat/completions")


class ExtractJsonObjectTests(unittest.TestCase):
    def test_plain_fenced_and_surrounded_json(self):
        self.assertEqual(extract_json_object('{"a": 1}'), {"a": 1})
        self.assertEqual(extract_json_object('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(extract_json_object('```JSON\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(extract_json_object('Sure! {"a": 1} Hope that helps.'), {"a": 1})

    def test_nothing_usable_is_none(self):
        for bad in (None, "", "no json here", "{broken", "[1, 2]"):
            self.assertIsNone(extract_json_object(bad), bad)


class ModelUnavailableTests(unittest.TestCase):
    @staticmethod
    def _error(code, message):
        return urllib.error.HTTPError("http://x", code, "err", {}, io.BytesIO(message.encode()))

    def test_404_and_model_400_mean_try_the_next_model(self):
        self.assertTrue(is_model_unavailable_error(self._error(404, "anything")))
        self.assertTrue(is_model_unavailable_error(self._error(400, "The model does not exist")))

    def test_other_errors_are_not_retried(self):
        self.assertFalse(is_model_unavailable_error(self._error(400, "bad request")))
        self.assertFalse(is_model_unavailable_error(self._error(401, "invalid key")))
        self.assertFalse(is_model_unavailable_error(self._error(500, "model overloaded")))


class PostChatCompletionTests(_CleanEnv):
    def test_posts_to_the_resolved_url_and_returns_the_reply_text(self):
        response = MagicMock()
        response.read.return_value = json.dumps({"choices": [{"message": {"content": "hello"}}]}).encode()
        response.__enter__.return_value = response
        with patch.dict("os.environ", {"LLM_BASE_URL": "http://llm.example/v1"}):
            with patch("urllib.request.urlopen", return_value=response) as urlopen:
                text = post_chat_completion({"model": "m"}, "secret", timeout=7)
        self.assertEqual(text, "hello")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://llm.example/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(json.loads(request.data), {"model": "m"})
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 7)


class EveryModuleSharesTheHelpersTests(unittest.TestCase):
    """The duplicated copies are gone and cannot drift apart again."""

    def test_qa_relevance_can_build_its_url(self):
        # Regression: qa_relevance used to call an undefined _load_env_files() before it could
        # even build the endpoint, so a recording with a panel question crashed the analysis.
        import services.qa_relevance as qa

        self.assertTrue(hasattr(qa, "post_chat_completion"))
        self.assertFalse(hasattr(qa, "_chat_url"))
        response = MagicMock()
        response.read.return_value = json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode()
        response.__enter__.return_value = response
        with patch("urllib.request.urlopen", return_value=response):
            self.assertEqual(qa._call_groq_pair_once("Q?", "A.", "key", "model"), "{}")

    def test_no_module_keeps_its_own_copy(self):
        import services.conversation_understanding as cu
        import services.live_question_recommender as lqr
        import services.llm_judge as judge
        import services.qa_relevance as qa
        import services.technical_accuracy as ta

        for module in (judge, qa, cu, ta, lqr):
            for private in ("_chat_url", "_load_env_files", "get_llm_base_url"):
                self.assertFalse(hasattr(module, private), f"{module.__name__}.{private}")
        self.assertIs(judge._extract_json_object, extract_json_object)
        self.assertIs(lqr._extract_json_object, extract_json_object)


if __name__ == "__main__":
    unittest.main()
