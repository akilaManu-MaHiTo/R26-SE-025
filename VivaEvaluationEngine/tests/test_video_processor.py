"""Unreadable video must raise VideoUnreadableError (HTTP 400 on the server)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from services.video_processor import VideoProcessor, VideoUnreadableError


class VideoProcessorTests(unittest.TestCase):
    def test_junk_bytes_raise_unreadable(self):
        handle = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        try:
            handle.write(b"not a video file")
            handle.close()
            with self.assertRaises(VideoUnreadableError) as ctx:
                list(VideoProcessor().iter_frames(handle.name))
            self.assertIn("could not be opened as a video", str(ctx.exception).lower())
        finally:
            Path(handle.name).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
