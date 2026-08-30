"""Whisper model env resolution."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from transcribe import DEFAULT_WHISPER_MODEL, resolve_whisper_model_size


class WhisperModelResolveTests(unittest.TestCase):
    def test_default_is_small(self):
        self.assertEqual(DEFAULT_WHISPER_MODEL, "small")
        self.assertEqual(resolve_whisper_model_size(None), "small")

    def test_large_v3_alias(self):
        self.assertEqual(resolve_whisper_model_size("large-v3"), "large-v3")
        self.assertEqual(resolve_whisper_model_size("large_v3"), "large-v3")

    def test_unknown_falls_back(self):
        self.assertEqual(resolve_whisper_model_size("not-a-model"), "small")


if __name__ == "__main__":
    unittest.main()
