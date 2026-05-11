# Audio Feature Extraction for Viva Evaluation

This module extracts comprehensive audio features from viva videos for grading enhancement.

## Features

### 1. Audio Extraction
- Extracts audio from video files (MP4, AVI, MOV, MKV, etc.)
- Converts to 16kHz mono WAV format for consistency

### 2. Audio Transcription
- Uses OpenAI's Whisper model for speech-to-text
- Provides word-level timestamps
- Detects language automatically

### 3. Acoustic Feature Extraction
Extracts 40+ acoustic features using Librosa and Parselmouth:

**Librosa Features:**
- **MFCC** (Mel-Frequency Cepstral Coefficients): 13 coefficients capturing spectral characteristics
- **Spectral Features**: Centroid, Rolloff, Bandwidth - describe spectral distribution
- **Zero Crossing Rate (ZCR)**: Indicates noisiness/voicedness
- **Chroma Features**: Pitch-based features (12 coefficients)
- **RMS Energy**: Overall energy of the audio
- **Tempo & Beat**: Detected tempo in BPM and beat frames
- **Duration**: Total audio duration

**Parselmouth Features (Voice Quality):**
- **Pitch (F0)**: Fundamental frequency (mean, std, min, max)
- **Formants**: First 3 formants (F1, F2, F3) - characterize vowel quality
- **Jitter**: Voice frequency variation (local, relative, rap, ppq5)
- **Shimmer**: Voice amplitude variation (local, local_dB, apq3, apq5, apq11)
- **Harmonics-to-Noise Ratio (HNR)**: Voice quality indicator

### 4. Emotion Recognition
- Uses Wav2Vec2 model for speech emotion recognition
- Detects emotions: neutral, happy, sad, angry, fearful, disgusted, surprised
- Provides confidence scores for each emotion

## Output Format

### Main Output: `audio_analysis_output.json`
```json
{
  "metadata": {
    "timestamp": "2024-05-11T10:30:00",
    "video_source": "videos/viva_01.mp4",
    "components": {
      "audio_extraction": "success",
      "transcription": "success",
      "acoustic_features": "success",
      "emotion_features": "success"
    }
  },
  "audio_extraction": {
    "status": "success",
    "audio_path": "audio_temp.wav",
    "file_size_mb": 5.2
  },
  "transcription": {
    "status": "success",
    "transcript": "Lorem ipsum...",
    "num_segments": 45,
    "duration_seconds": 120.5,
    "language": "english"
  },
  "acoustic_features": {
    "status": "success",
    "features": {
      "mfcc_mean": [0.1, 0.2, ...],
      "pitch_mean": 150.5,
      "jitter_local": 0.0025,
      "shimmer_local": 0.015,
      "hnr_mean": 18.5,
      ...
    },
    "key_metrics": {...}
  },
  "emotion_features": {
    "status": "success",
    "predicted_emotion": "neutral",
    "confidence": 0.92,
    "emotion_probabilities": {
      "neutral": 0.92,
      "happy": 0.05,
      ...
    }
  },
  "grading_summary": {
    "audio_quality": {
      "duration_seconds": 120.5,
      "clarity": 0.98,
      "stability": 0.97,
      "energy_level": 0.45
    },
    "speech_emotion": {...},
    "speech_content": {...}
  }
}
```

### Grading Summary: `grading_summary.json`
- Focused on metrics relevant for grading
- Includes audio quality scores
- Speech emotion and confidence
- Transcript preview and statistics

## Installation

### 1. Prerequisites

**System Requirements:**
- Python 3.8+
- FFmpeg (for audio extraction)

**Install FFmpeg:**
- **Windows (Chocolatey)**: `choco install ffmpeg`
- **Windows (Manual)**: Download from https://ffmpeg.org/download.html
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt-get install ffmpeg`

### 2. Python Dependencies

Install all required packages:
```bash
pip install -r requirements.txt
```

**Key Dependencies:**
- **torch, torchaudio**: Deep learning framework
- **librosa**: Audio feature extraction
- **parselmouth**: Voice analysis
- **transformers**: Hugging Face models
- **openai-whisper**: Speech transcription
- **numpy, scipy**: Scientific computing

### 3. Verify Setup

Run the setup verification script:
```bash
python setup_audio_env.py
```

## Usage

### Basic Usage

Process a single video:
```bash
python audio_analyzer.py videos/viva_01.mp4
```

### Automatic Detection

If no video is specified, the script will process the first video found in the `videos/` directory:
```bash
python audio_analyzer.py
```

### Output

Results are saved to the `outputs/` directory:
- `audio_analysis_output.json` - Complete analysis with all features
- `grading_summary.json` - Simplified view for grading

## Grading Integration

The audio features can be used for grading in the following ways:

### Audio Quality Assessment
- **Clarity Score**: Based on jitter and voice quality metrics
- **Stability Score**: Based on shimmer measurements
- **Energy Level**: Overall amplitude (indicates engagement)
- **Duration**: Total speaking time

### Engagement Detection
- **Emotion**: Detected emotional state (neutral, confident, stressed)
- **Confidence Score**: How certain the emotion detection is
- **Speech Content**: Full transcript and segment count

### Voice Quality Indicators
- **Pitch Variation**: Student confidence indicator
- **Formants**: Speech clarity and articulation
- **Harmonics-to-Noise Ratio**: Overall voice health

## Advanced Usage

### Custom Video Processing

Create a Python script:
```python
from audio_analyzer import AudioAnalyzer

analyzer = AudioAnalyzer("path/to/video.mp4", output_dir="my_outputs")
analyzer.run_pipeline()
```

### Access Individual Components

```python
from extract_features import extract_acoustic_features
from extract_emotion import extract_speech_emotion

# Extract features from existing audio
features = extract_acoustic_features("audio.wav")
emotion = extract_speech_emotion("audio.wav")
```

## Troubleshooting

### Issue: FFmpeg not found
**Solution:** Install FFmpeg and ensure it's in system PATH

### Issue: Memory error with large videos
**Solution:** Use a smaller Whisper model:
```bash
python audio_analyzer.py videos/large_video.mp4 --model tiny
```

### Issue: Parselmouth errors
**Solution:** 
- Ensure audio is proper WAV format
- Try reducing audio length if > 10 minutes
- Check audio has spoken content

### Issue: Slow processing
**Solution:**
- Use GPU acceleration for torch: Install CUDA
- Use smaller Whisper model (tiny, base instead of large)
- Process videos in parallel

## Feature Extraction Details

### MFCC (Mel-Frequency Cepstral Coefficients)
- 13 coefficients capturing frequency distribution
- **Grading Use**: Speech clarity and articulation
- **Typical Range**: -200 to 200

### Pitch (F0)
- Fundamental frequency range: 50-300 Hz (adults)
- **Grading Use**: Confidence, emotion, engagement
- **Typical Range**: 80-250 Hz for male, 120-300+ Hz for female

### Jitter
- Voice frequency perturbation
- **Grading Use**: Voice quality, nervousness indicator
- **Typical Range**: 0.3-1.0% for healthy voice
- **Increased Jitter**: Can indicate nervousness, fatigue

### Shimmer
- Voice amplitude perturbation
- **Grading Use**: Voice stability, confidence
- **Typical Range**: 3-5 dB for healthy voice
- **Increased Shimmer**: Can indicate emotional stress

### Harmonics-to-Noise Ratio (HNR)
- Ratio of periodic (harmonic) to random (noise) components
- **Grading Use**: Overall voice quality
- **Typical Range**: 15-25 dB for healthy voice
- **Lower HNR**: Indicates more noise, possible fatigue or poor audio quality

## Output Files Structure

```
outputs/
├── audio_analysis_output.json      # Complete analysis
├── grading_summary.json            # Grading-focused summary
└── [other analysis outputs]
```

## Performance Metrics

**Typical Processing Times (per video):**
- Audio Extraction: 1-5 seconds
- Transcription (base model): 30-120 seconds
- Acoustic Features: 5-15 seconds
- Emotion Detection: 10-30 seconds
- **Total: ~1-3 minutes** (depending on video length and model size)

**Storage Requirements:**
- Original Video: Variable
- Extracted Audio: 1-2 MB per minute of video
- Output JSON: 100 KB - 1 MB

## Citation & References

**Models Used:**
- Whisper: https://github.com/openai/whisper
- Wav2Vec2: https://huggingface.co/ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition
- Librosa: https://librosa.org/
- Parselmouth: https://parselmouth.readthedocs.io/

## License

This module is part of the Gradex AI platform for viva evaluation and grading enhancement.

## Support

For issues or questions, refer to the main project documentation or contact the development team.
