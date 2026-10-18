"""The copilot's provider endpoints default to the public APIs and can be overridden from env."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from Gradex_AI_Server.app.viva_copilot import groq_client

URL_ENV_NAMES = (
    "VIVA_COPILOT_LLM_BASE_URL",
    "OPENAI_BASE_URL",
    "LLM_BASE_URL",
    "VIVA_LLM_BASE_URL",
    "GEMINI_BASE_URL",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_REFERER",
)


def _providers_by_name():
    return {provider.name: provider for provider in groq_client._providers()}


class ProviderEndpointTests(unittest.TestCase):
    def setUp(self):
        # Treat the .env file as already loaded and start with none of the URL variables set.
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        for name in URL_ENV_NAMES:
            os.environ.pop(name, None)
        loaded = patch.object(groq_client, "_ENV_LOADED", True)
        loaded.start()
        self.addCleanup(loaded.stop)

    def test_defaults_are_the_public_endpoints(self):
        providers = _providers_by_name()
        self.assertEqual(providers["Groq"].base_url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(
            providers["Gemini"].base_url, "https://generativelanguage.googleapis.com/v1beta/models"
        )
        self.assertEqual(providers["OpenRouter"].base_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(providers["OpenRouter"].extra_headers["HTTP-Referer"], "https://gradex.local")

    def test_each_endpoint_can_be_overridden(self):
        with patch.dict(
            os.environ,
            {
                "VIVA_COPILOT_LLM_BASE_URL": "http://groq-proxy.example/v1/",
                "GEMINI_BASE_URL": "http://gemini-proxy.example/models/",
                "OPENROUTER_BASE_URL": "http://or.example/api/v1/chat/completions",
                "OPENROUTER_REFERER": "https://gradex.example",
            },
        ):
            providers = _providers_by_name()
        self.assertEqual(providers["Groq"].base_url, "http://groq-proxy.example/v1/chat/completions")
        self.assertEqual(providers["Gemini"].base_url, "http://gemini-proxy.example/models")
        self.assertEqual(providers["OpenRouter"].base_url, "http://or.example/api/v1/chat/completions")
        self.assertEqual(providers["OpenRouter"].extra_headers["HTTP-Referer"], "https://gradex.example")

    def test_groq_follows_the_shared_llm_base_url_chain(self):
        with patch.dict(os.environ, {"LLM_BASE_URL": "http://shared.example/v1"}):
            self.assertEqual(
                _providers_by_name()["Groq"].base_url, "http://shared.example/v1/chat/completions"
            )
        with patch.dict(
            os.environ,
            {"LLM_BASE_URL": "http://shared.example/v1", "VIVA_COPILOT_LLM_BASE_URL": "http://copilot.example/v1"},
        ):
            self.assertEqual(
                _providers_by_name()["Groq"].base_url, "http://copilot.example/v1/chat/completions"
            )


if __name__ == "__main__":
    unittest.main()
