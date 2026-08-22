"""Child-process HuggingFace SER worker.

Runs in a separate process so a native OOM/crash cannot kill the Gradex server.
Prints one JSON object to stdout.
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: ser_worker.py <audio_path> <model_id>"}))
        return 2

    audio_path = sys.argv[1]
    model_id = sys.argv[2]
    max_seconds = 12.0

    import librosa
    from transformers import pipeline

    y, sr = librosa.load(audio_path, sr=16000, mono=True, duration=max_seconds)
    if y.size == 0:
        print(json.dumps({"error": "empty_audio"}))
        return 1

    classifier = pipeline(
        "audio-classification",
        model=model_id,
        top_k=None,
        device=-1,
    )
    raw = classifier({"raw": y, "sampling_rate": int(sr)})
    if isinstance(raw, dict):
        raw = [raw]
    print(json.dumps({
        "scores": raw,
        "model_id": model_id,
        "sample_rate": int(sr),
        "analyzed_duration_seconds": round(float(len(y) / sr), 3) if sr else 0.0,
        "max_seconds_cap": max_seconds,
        "channels": 1,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
