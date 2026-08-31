"""Transcribe audio using Whisper model when available."""
from functools import lru_cache
import json
import os
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parent
DEFAULT_TRANSCRIPTION_OUTPUT = ENGINE_ROOT / "outputs" / "transcription_result.json"

ALLOWED_WHISPER_MODELS = (
    "tiny",
    "base",
    "small",
    "medium",
    "large",
    "large-v2",
    "large-v3",
    "turbo",
)
# small is the CPU default: medium on CPU is FP32 and often minutes per minute of audio.
DEFAULT_WHISPER_MODEL = "small"


def resolve_whisper_model_size(raw: str | None, *, default: str = DEFAULT_WHISPER_MODEL) -> str:
    """Normalize VIVA_WHISPER_MODEL env value."""
    value = (raw or default).strip().lower()
    aliases = {
        "largev3": "large-v3",
        "large_v3": "large-v3",
        "large-v3-turbo": "turbo",
    }
    value = aliases.get(value, value)
    if value in ALLOWED_WHISPER_MODELS:
        return value
    print(f"Unknown Whisper model {raw!r}; falling back to {default}.")
    return default


@lru_cache(maxsize=2)
def _load_whisper_model(model_size):
    import whisper

    print(f"Loading Whisper model: {model_size}")
    try:
        from services.pipeline_progress import emit

        emit("whisper", f"Loading Whisper model ({model_size})")
    except Exception:
        pass
    return whisper.load_model(model_size)


def release_whisper_models() -> None:
    """Drop cached Whisper weights so later SER/video steps have RAM headroom."""
    import gc

    _load_whisper_model.cache_clear()
    gc.collect()


def transcribe_audio(audio_path, model_size=None, output_path=None):
    """Transcribe audio using Whisper.

    Returns:
        transcript (str), segments (list), meta (dict with available/reason)
    """
    model_size = resolve_whisper_model_size(model_size)
    try:
        model = _load_whisper_model(model_size)
    except ImportError:
        print("Whisper is not installed; skipping transcription and returning an empty transcript.")
        return "", [], {"available": False, "reason": "whisper_not_installed", "words_with_times": []}

    print(f"Transcribing audio: {audio_path}")
    try:
        from services.pipeline_progress import emit

        emit("whisper", "Transcribing speech (Whisper)")
    except Exception:
        pass
    use_gpu = False
    try:
        import torch

        use_gpu = bool(torch.cuda.is_available())
    except ImportError:
        use_gpu = False

    # The FP16 warning is not a failure: openai-whisper always prints it on CPU.
    # GPU uses FP16 (faster). CPU stays FP32. language=en skips language detect.
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        verbose=False,
        fp16=use_gpu,
        language="en",
    )

    transcript = result["text"]
    segments = result["segments"]

    words_with_times = []
    for segment in segments:
        for word_info in segment.get("words", []):
            words_with_times.append(
                {
                    "word": word_info["word"],
                    "start": word_info["start"],
                    "end": word_info["end"],
                }
            )

    output_data = {
        "transcript": transcript,
        "segments": segments,
        "words_with_times": words_with_times,
        "language": result.get("language", "unknown"),
        "duration": result.get("duration", 0),
    }

    destination = Path(output_path) if output_path else DEFAULT_TRANSCRIPTION_OUTPUT
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print("Transcription completed.")
    print(f"  - Output: {destination}")
    print(f"  - Text length: {len(transcript)} characters")
    print(f"  - Number of segments: {len(segments)}")
    print(f"  - Language: {result.get('language', 'unknown')}")

    return transcript, segments, {
        "available": True,
        "reason": None,
        "model": model_size,
        "words_with_times": words_with_times,
    }


if __name__ == "__main__":
    audio_path = "audio.wav"
    if os.path.exists(audio_path):
        transcribe_audio(audio_path)
    else:
        print(f"Audio file not found: {audio_path}")
        print("Please run extract_audio.py first")
