"""Smoke tests for Colab health URL derivation and availability cache."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.services import ai_model_route as route


class ColabHealthUrlTests(unittest.TestCase):
    def test_health_url_from_evaluate(self):
        with patch.object(route, "COLAB_URL", "https://example.ngrok.app/evaluate"):
            self.assertEqual(
                route._colab_health_url(),
                "https://example.ngrok.app/health",
            )

    def test_health_url_trailing_slash(self):
        with patch.object(route, "COLAB_URL", "https://example.ngrok.app/evaluate/"):
            self.assertEqual(
                route._colab_health_url(),
                "https://example.ngrok.app/health",
            )

    def test_health_url_already_health(self):
        with patch.object(route, "COLAB_URL", "https://example.ngrok.app/health"):
            self.assertEqual(
                route._colab_health_url(),
                "https://example.ngrok.app/health",
            )


class ColabAvailabilityCacheTests(unittest.TestCase):
    def setUp(self):
        route.reset_colab_availability_cache()

    def tearDown(self):
        route.reset_colab_availability_cache()

    def test_probe_skips_colab_when_health_fails(self):
        with patch.object(route, "COLAB_URL", "https://offline.ngrok.app/evaluate"):
            with patch.object(
                route,
                "_probe_colab_endpoint",
                side_effect=[(False, "HTTP 404"), (False, "HTTP 404")],
            ):
                self.assertFalse(route.probe_colab_availability(force=True))
                self.assertFalse(route._colab_is_available_cached())
                self.assertIsNone(route.try_forward_to_colab({"topic": "t"}))

    def test_probe_uses_cache_within_ttl(self):
        route._mark_colab_available("test")
        with patch.object(route, "COLAB_URL", "https://x/evaluate"):
            with patch.object(route, "_probe_colab_endpoint") as mock_probe:
                self.assertTrue(route.probe_colab_availability(force=False))
                mock_probe.assert_not_called()

    def test_mid_batch_failure_invalidates_cache(self):
        route._mark_colab_available("test")
        with patch.object(route, "COLAB_URL", "https://x/evaluate"):
            with patch.object(route, "COLAB_RETRIES", 1):
                with patch("app.services.ai_model_route.requests.post") as mock_post:
                    mock_resp = mock_post.return_value
                    mock_resp.status_code = 404
                    mock_resp.text = "not found"
                    self.assertIsNone(route.try_forward_to_colab({"topic": "t"}))
        self.assertFalse(route._colab_is_available_cached())


if __name__ == "__main__":
    unittest.main()
