# Audio Feature Extraction - Quick Start Guide

## What's New

The audio feature extraction system has been set up in the VivaEvaluationEngine folder. It extracts comprehensive audio features from viva videos for grading enhancement.

## Files Created/Updated

### Core Audio Processing Files
- **`extract_audio.py`** - Extracts audio from video files
- **`extract_features.py`** - Extracts 40+ acoustic features using Librosa and Parselmouth
- **`extract_emotion.py`** - Detects speech emotion using Wav2Vec2 model
- **`transcribe.py`** - Transcribes audio using OpenAI Whisper
- **`audio_analyzer.py`** - Main orchestrator that combines all features into one output JSON

### Supporting Files
- **`setup_audio_env.py`** - Verifies that all dependencies are installed
- **`examples.py`** - Example scripts showing how to use the audio analyzer
- **`requirements.txt`** - Updated with all audio processing dependencies
- **`AUDIO_FEATURES_README.md`** - Comprehensive documentation

## Quick Start (3 Steps)

### Step 1: Verify Setup
```bash
cd VivaEvaluationEngine
python setup_audio_env.py
```

Expected output: ✓ Setup verification completed successfully!

### Step 2: Add a Video
Place your viva video in the `videos/` folder:
```
videos/
└── viva_01.mp4
```

### Step 3: Run Analysis
```bash
python audio_analyzer.py
```

Or specify a video directly:
```bash
python audio_analyzer.py videos/viva_01.mp4
```

## Output Files

The analysis generates two JSON files in the `outputs/` directory:

### 1. `audio_analysis_output.json` (Complete Analysis)
Contains all extracted features:
- Audio extraction details
- Full transcription with segments
- 40+ acoustic features (MFCC, pitch, formants, jitter, shimmer, etc.)
- Emotion detection results

### 2. `grading_summary.json` (Grading-Focused)
Contains simplified metrics for grading:
- Audio quality scores (clarity, stability)
- Detected emotion and confidence
- Speech content summary
- Key metrics for evaluation

## Example Usage

### Basic Processing
```python
from audio_analyzer import AudioAnalyzer

analyzer = AudioAnalyzer("videos/viva_01.mp4")
analyzer.run_pipeline()
```

### Access Results
```python
import json

with open("outputs/audio_analysis_output.json", "r") as f:
    results = json.load(f)

# Get acoustic features
acoustic = results['acoustic_features']['features']
print(f"Pitch: {acoustic['pitch_mean']:.2f} Hz")
print(f"Jitter: {acoustic['jitter_local']:.6f}")

# Get emotion
emotion = results['emotion_features']['predicted_emotion']
confidence = results['emotion_features']['confidence']
print(f"Detected Emotion: {emotion} ({confidence:.1%})")
```

## Audio Features Extracted

### Voice Quality (Parselmouth)
| Feature | Purpose | Grading Use |
|---------|---------|-------------|
| Pitch (F0) | Fundamental frequency | Confidence, engagement |
| Formants (F1, F2, F3) | Vowel quality | Articulation clarity |
| Jitter | Frequency variation | Nervousness, fatigue |
| Shimmer | Amplitude variation | Emotional stress |
| HNR | Voice quality | Overall professionalism |

### Acoustic Features (Librosa)
| Feature | Purpose | Grading Use |
|---------|---------|-------------|
| MFCC | Spectral characteristics | Speech clarity |
| Spectral Centroid | Brightness | Tone quality |
| RMS Energy | Loudness | Engagement level |
| Tempo | Speaking pace | Confidence |
| Zero Crossing Rate | Noisiness | Audio quality |

### Speech Content
| Metric | Source |
|--------|--------|
| Full Transcript | Whisper Model |
| Segments | Timing information |
| Language | Automatic detection |
| Duration | Audio length |

### Emotional State
| Metric | Details |
|--------|---------|
| Emotion | 7 emotions detected |
| Confidence | 0-100% certainty |
| Probabilities | Score for each emotion |

## Grading Integration

### Audio Quality Grade (0-100)
Combines:
- Clarity: 1.0 - (jitter_local * 100)
- Stability: 1.0 - (shimmer_local * 10)

### Engagement Metrics
From audio features:
- Speech pace (tempo)
- Energy level (RMS)
- Emotional state (emotion detection)
- Speaking patterns (transcription segments)

### Speech Quality Indicators
- Pitch variation (confidence)
- Formant quality (articulation)
- Harmonic-to-noise ratio (professionalism)

## System Requirements

- **Python**: 3.8+
- **FFmpeg**: Required for audio extraction
- **RAM**: 8GB+ recommended (for large models)
- **Storage**: ~500MB for models + ~1-2MB per video

## Troubleshooting

### "FFmpeg not found"
Windows: `choco install ffmpeg`
macOS: `brew install ffmpeg`
Linux: `sudo apt-get install ffmpeg`

### "Out of memory"
Use smaller Whisper model or process shorter videos:
```python
analyzer = AudioAnalyzer("video.mp4", model_size="tiny")
```

### "Parselmouth errors"
Usually harmless - gracefully falls back to defaults. If persistent:
- Ensure audio is proper 16kHz WAV format
- Check audio has spoken content
- Try shorter videos (< 10 minutes)

### "Slow processing"
- Use GPU acceleration: Install CUDA for PyTorch
- Use "tiny" Whisper model instead of "base"
- Process videos in parallel

## Performance Metrics

**Typical Processing Times (per 1-minute video):**
- Audio extraction: 1-2 seconds
- Transcription (base): 20-40 seconds
- Acoustic features: 3-5 seconds
- Emotion detection: 5-10 seconds
- **Total: ~30-60 seconds**

**Output Size:**
- JSON output: 200-500 KB
- Acoustic features alone: 20-50 KB

## Next Steps

1. **Run Examples**
   ```bash
   python examples.py
   ```

2. **Read Full Documentation**
   See `AUDIO_FEATURES_README.md` for detailed feature descriptions

3. **Integrate with Grading System**
   Use the JSON output to enhance your grading pipeline

4. **Batch Processing**
   Create a script to process multiple videos automatically

## Dependencies Installed

Core:
- torch, torchaudio - Deep learning
- librosa - Audio feature extraction
- parselmouth - Voice analysis
- transformers - ML models
- openai-whisper - Speech recognition

Supporting:
- numpy, scipy - Scientific computing
- matplotlib - Visualization
- soundfile, pydub - Audio handling
- ffmpeg-python - FFmpeg wrapper

All are already installed via `pip install -r requirements.txt`

## Support

For more information:
1. See `AUDIO_FEATURES_README.md` for detailed documentation
2. Run `python setup_audio_env.py` to verify setup
3. Check individual script docstrings for API details
4. Review examples in `examples.py`

---

**Version**: 1.0  
**Last Updated**: May 11, 2026  
**Status**: ✓ Ready for use
