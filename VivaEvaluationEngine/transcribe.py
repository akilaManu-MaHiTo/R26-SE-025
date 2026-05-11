"""Transcribe audio using Whisper model"""
import whisper
import json
import os

def transcribe_audio(audio_path, model_size="base"):
    """Transcribe audio using Whisper model
    
    Args:
        audio_path: Path to audio file
        model_size: Size of Whisper model (tiny, base, small, medium, large)
    """
    print(f"Loading Whisper model: {model_size}")
    model = whisper.load_model(model_size)
    
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
    
    with open("transcription_result.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"Transcription completed.")
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
