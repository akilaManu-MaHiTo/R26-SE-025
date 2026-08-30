"""Prefetch Whisper + HuggingFace SER used by this engine.

From the repo root, after pip install and after copying .env:

    python VivaEvaluationEngine/download_models.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent
SERVER_ENV = ENGINE_ROOT.parent / "Gradex_AI_Server" / "app" / ".env"
VIVA_ENV = ENGINE_ROOT / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _check_ffmpeg() -> bool:
    try:
        completed = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return completed.returncode == 0
    except (OSError, subprocess.SubprocessError, TimeoutError):
        return False


def main() -> int:
    _load_dotenv(SERVER_ENV)
    _load_dotenv(VIVA_ENV)
    if str(ENGINE_ROOT) not in sys.path:
        sys.path.insert(0, str(ENGINE_ROOT))

    print("1. ffmpeg")
    if _check_ffmpeg():
        print("   OK — ffmpeg is on PATH")
    else:
        print("   MISSING — install ffmpeg (not pip). https://ffmpeg.org/download.html")

    from transcribe import resolve_whisper_model_size

    size = resolve_whisper_model_size(os.getenv("VIVA_WHISPER_MODEL"))
    print(f"2. Whisper model: {size}")
    try:
        import whisper

        whisper.load_model(size)
        print(f"   OK — {size} cached")
    except Exception as exc:
        print(f"   FAILED — {exc}")
        return 1

    backend = (os.getenv("VIVA_SER_BACKEND") or "huggingface").strip().lower()
    ser_model = (os.getenv("VIVA_SER_MODEL") or "superb/wav2vec2-base-superb-er").strip()
    print("3. Speech-emotion (HuggingFace)")
    if backend != "huggingface":
        print(f"   skip — VIVA_SER_BACKEND={backend}")
    else:
        try:
            from huggingface_hub import snapshot_download

            snapshot_download(repo_id=ser_model)
            print(f"   OK — {ser_model} cached")
        except Exception as exc:
            print(f"   FAILED — {exc}")

    print()
    print("Done. First analyze should skip these downloads.")
    print("MediaPipe may still fetch a small .tflite on the first video.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
