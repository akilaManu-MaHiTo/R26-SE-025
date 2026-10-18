"""The pre-analysis video gate: bad uploads are refused before any ML resource is spent.

Covers viva_video_validation.validate_viva_video with small synthetic videos, and the
/api/viva-analyze upload path (size minimum and gate failures never reach the pipeline).

  python -m unittest Gradex_AI_Server.app.tests.test_viva_video_gate -v
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from Gradex_AI_Server.app import viva_video_validation as gate
from Gradex_AI_Server.app.core.database import db_instance
from Gradex_AI_Server.app.main import UPLOAD_DIR, viva_analyze
from Gradex_AI_Server.app.tests.test_viva_http import _form_defaults

cv2 = __import__("cv2")


def _write_video(path: Path, *, seconds: float, frame_fn, fps: int = 10, size=(320, 240)) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    assert writer.isOpened(), "OpenCV cannot write mp4v on this machine"
    for index in range(int(seconds * fps)):
        writer.write(frame_fn(index, size))
    writer.release()


def _textured(_index, size):
    rng = np.random.default_rng(1)
    return rng.integers(0, 256, (size[1], size[0], 3), dtype=np.uint8)


def _flat(value):
    return lambda _index, size: np.full((size[1], size[0], 3), value, dtype=np.uint8)


class ValidateVivaVideoTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        # Synthetic clips are far below 2 MB; the size rule has its own tests below.
        patcher = patch.object(gate, "MIN_VIVA_UPLOAD_BYTES", 1)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _video(self, name, **kwargs):
        path = Path(self.dir.name) / name
        _write_video(path, **kwargs)
        return path

    def test_a_clear_long_enough_video_passes(self):
        facts = gate.validate_viva_video(self._video("ok.mp4", seconds=12, frame_fn=_textured))
        self.assertGreaterEqual(facts["duration_seconds"], 10)
        self.assertGreater(facts["frame_count"], 0)

    def test_missing_file_is_refused(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            gate.validate_viva_video(Path(self.dir.name) / "nope.mp4")

    def test_under_the_minimum_size_is_refused(self):
        path = self._video("small.mp4", seconds=12, frame_fn=_textured)
        with patch.object(gate, "MIN_VIVA_UPLOAD_BYTES", path.stat().st_size + 1):
            with self.assertRaisesRegex(ValueError, "at least 2 MB"):
                gate.validate_viva_video(path)

    def test_a_file_that_is_not_a_video_is_refused(self):
        path = Path(self.dir.name) / "notes.mp4"
        path.write_bytes(b"this is not a video" * 100)
        with self.assertRaises(ValueError):
            gate.validate_viva_video(path)

    def test_a_clip_shorter_than_ten_seconds_is_refused(self):
        with self.assertRaisesRegex(ValueError, "at least 10 seconds"):
            gate.validate_viva_video(self._video("short.mp4", seconds=4, frame_fn=_textured))

    def test_a_clip_longer_than_thirty_minutes_is_refused(self):
        path = self._video("long.mp4", seconds=12, frame_fn=_textured)
        with patch.object(gate, "MAX_VIVA_DURATION_SECONDS", 11.0):
            with self.assertRaisesRegex(ValueError, "30 minutes"):
                gate.validate_viva_video(path)

    def test_a_blank_blurry_video_is_refused(self):
        with self.assertRaisesRegex(ValueError, "blurry"):
            gate.validate_viva_video(self._video("blur.mp4", seconds=12, frame_fn=_flat(128)))

    def test_a_dark_video_is_refused(self):
        def dark(_index, size):
            # Sharp (a fine checkerboard) but far too dark: mean brightness is about 15.
            board = (np.indices((size[1], size[0])).sum(axis=0) % 2) * 30
            return np.repeat(board[:, :, None], 3, axis=2).astype(np.uint8)

        with self.assertRaisesRegex(ValueError, "dark or overexposed"):
            gate.validate_viva_video(self._video("dark.mp4", seconds=12, frame_fn=dark))


def _upload(body: bytes) -> UploadFile:
    return UploadFile(
        filename="clip.mp4",
        file=BytesIO(body),
        headers=Headers({"content-type": "video/mp4"}),
    )


def _analyze(body: bytes):
    kwargs = _form_defaults(viva_analyze)
    kwargs.update(video=_upload(body), student_id="IT22000001", viva_id="x", request=None)
    return asyncio.run(viva_analyze(**kwargs))


class UploadGateTests(unittest.TestCase):
    """What /api/viva-analyze does with a bad file: refuse it, spend nothing, leave no file behind."""

    def setUp(self):
        self._saved = (db_instance.allow_autoconnect, db_instance.client)
        db_instance.allow_autoconnect = False
        db_instance.client = None
        self.addCleanup(self._restore)
        self.before = {p.name for p in UPLOAD_DIR.glob("*")}

        async def vivas_ok(_viva_id, _request):
            return {
                "_id": "v1", "name": "V", "category": "non_technical", "subject_code": "SE1",
                "subject_name": "S", "year": 2026, "semester": 1,
            }

        async def no_duplicates(*_a, **_k):
            return None

        for p in (
            patch("Gradex_AI_Server.app.main.fetch_viva_for_analysis", vivas_ok),
            patch("Gradex_AI_Server.app.main.ensure_no_duplicate_mark", no_duplicates),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _restore(self):
        db_instance.allow_autoconnect, db_instance.client = self._saved

    def test_an_upload_under_2_mb_is_refused_without_running_the_pipeline(self):
        with patch("Gradex_AI_Server.app.viva_service.analyze_video_file") as pipeline:
            with self.assertRaises(HTTPException) as ctx:
                _analyze(b"x" * 1024)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("at least 2 MB", ctx.exception.detail)
        pipeline.assert_not_called()
        self.assertEqual({p.name for p in UPLOAD_DIR.glob("*")}, self.before)

    def test_a_failed_gate_is_a_400_and_the_pipeline_never_runs_and_the_file_is_deleted(self):
        def refuse(_path):
            raise ValueError("The video is too blurry for reliable viva analysis.")

        big = b"x" * (gate.MIN_VIVA_UPLOAD_BYTES + 1)
        with patch("Gradex_AI_Server.app.main.validate_viva_video", refuse):
            with patch("Gradex_AI_Server.app.viva_service.analyze_video_file") as pipeline:
                with self.assertRaises(HTTPException) as ctx:
                    _analyze(big)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("blurry", ctx.exception.detail)
        pipeline.assert_not_called()
        self.assertEqual({p.name for p in UPLOAD_DIR.glob("*")}, self.before)


if __name__ == "__main__":
    unittest.main()
