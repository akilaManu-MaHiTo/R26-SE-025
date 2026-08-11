"""Transcribe audio using Whisper model when available."""
from functools import lru_cache
import json
import os
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parent
DEFAULT_TRANSCRIPTION_OUTPUT = ENGINE_ROOT / "outputs" / "transcription_result.json"


@lru_cache(maxsize=2)
def _load_whisper_model(model_size):
    import whisper

    print(f"Loading Whisper model: {model_size}")
    return whisper.load_model(model_size)


def transcribe_audio(audio_path, model_size="base", output_path=None):
    """Transcribe audio using Whisper model
    
    Args:
        audio_path: Path to audio file
        model_size: Size of Whisper model (tiny, base, small, medium, large)
        output_path: Optional JSON file path for transcription details.
    """
    try:
        model = _load_whisper_model(model_size)
    except ImportError:
        print("Whisper is not installed; skipping transcription and returning an empty transcript.")
        return "", []
    
    print(f"Transcribing audio: {audio_path}")
    result = model.transcribe(audio_path, word_timestamps=True, verbose=False)
    
    transcript = result["text"]
    segments = result["segments"]
    
    # Extract word-level timing information
    words_with_times = []
    for segment in segments:
        for word_info in segment.get('words', []):
            words_with_times.append({
                'word': word_info['word'],
                'start': word_info['start'],
                'end': word_info['end']
            })
    
    # Save results
    output_data = {
        "transcript": transcript,
        "segments": segments,
        "words_with_times": words_with_times,
        "language": result.get("language", "unknown"),
        "duration": result.get("duration", 0)
    }
    
    destination = Path(output_path) if output_path else DEFAULT_TRANSCRIPTION_OUTPUT
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"Transcription completed.")
    print(f"  - Output: {destination}")
    print(f"  - Text length: {len(transcript)} characters")
    print(f"  - Number of segments: {len(segments)}")
    print(f"  - Language: {result.get('language', 'unknown')}")
    
    return transcript, segments

if __name__ == "__main__":
    audio_path = "audio.wav"
    if os.path.exists(audio_path):
        transcribe_audio(audio_path)
    else:
        print(f"Audio file not found: {audio_path}")
        print("Please run extract_audio.py first")
