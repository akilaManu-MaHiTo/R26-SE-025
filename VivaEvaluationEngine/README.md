# Viva Evaluation Engine

Video/audio viva scoring (face, engagement, speech) and Stage-1 official `/100`. Used as a library by `Gradex_AI_Server` (`POST /api/viva-analyze`, live copilot analyze). This folder is the install surface for the viva stack.

## Install (Python)

From the **repo root**, same venv as the server:

```text
pip install -r VivaEvaluationEngine/requirements.txt
```

That file is the full viva package list: torch, openai-whisper, mediapipe, librosa, praat-parselmouth, timm, transformers, huggingface_hub.

`Gradex_AI_Server/app/requirements.txt` does **not** include these. Install this file as well if you run analyze or live viva.

## System (not in requirements.txt)

| Need | Why |
|---|---|
| **ffmpeg** on PATH | Audio extract + Whisper. Check with `ffmpeg -version`. |
| Python 3.11 or 3.12 | Torch / Whisper / MediaPipe |

## Env

Copy `.env.example` → `.env` in this folder (standalone CLI). When the server imports this engine, it uses `Gradex_AI_Server/app/.env`:

- `GROQ_API_KEY` or `AI_API_KEY` — judge / Q&A / technical-accuracy AI
- `VIVA_WHISPER_MODEL=small` — CPU default (medium is slow on CPU)
- `VIVA_SER_BACKEND=huggingface` and `VIVA_SER_MODEL=superb/wav2vec2-base-superb-er`

## Download models (after env is set)

CNN weights in `models/` are already in git (`hsemotion_improved.pt`, `engagement_cnn.pt`).

Prefetch Whisper + SER so the first analyze is not a long download:

```text
python VivaEvaluationEngine/download_models.py
```

Or from this directory: `python download_models.py`.

First video may still download MediaPipe Face Landmarker into `.models/` (gitignored).

## Run standalone

```text
cd VivaEvaluationEngine
python setup_audio_env.py
python main.py --video videos/your.mp4
```

## Tests

From the repo root:

```text
python -m unittest discover -s VivaEvaluationEngine/tests -v
```
