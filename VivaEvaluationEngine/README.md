# Viva Evaluation Engine

Video/audio viva scoring (face, engagement, speech) and the Stage-1 official `/100` mark. Used as a library by `Gradex_AI_Server` — both the upload path (`POST /api/viva-analyze`) and the live copilot's end-of-session analyze run this same chain. This folder is the install surface for the viva stack.

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
| Python 3.10–3.12 | Torch / Whisper / MediaPipe. Developed and tested on 3.10. |

## Env

Copy `.env.example` → `.env` in this folder (standalone CLI). When the server imports this engine, it uses `Gradex_AI_Server/app/.env`:

- `GROQ_API_KEY` or `AI_API_KEY` — judge / Q&A / technical-accuracy AI
- `VIVA_WHISPER_MODEL=small` — the built-in default is already `small` (medium is slow on CPU)
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

## How the mark is produced

`analyze_video_file` (called by the server) runs, in order:

```text
analyze_video          video CNNs: emotion, engagement, gaze, blinks
analyze_audio_from_video   ffmpeg -> Whisper -> Praat/librosa -> speech emotion
attach_llm_evaluation      Groq narrative feedback  (does NOT affect the mark)
attach_qa_analysis         Q&A relevance            (does NOT affect the mark)
attach_assessment          the official Stage-1 mark
```

The official mark (`assessment.final_score`, scoring version `v1.3`) is computed in
`services/assessment_scoring.py` from **three equally-weighted families**. A family with no
usable inputs is dropped and the rest renormalize, so a student is never penalised for a
signal the recording could not provide.

| Family | Inputs |
|---|---|
| `engagement` | CNN `average_engagement_score`, `facial_confidence`, facial emotion profile, on-camera gaze ratio, head stability, blink-rate score (equal parts; unavailable ones dropped) |
| `audio_acoustics` | pitch stability (from std), HNR clarity, jitter/shimmer articulation, speech-emotion tone (half weight, real SER model only) |
| `transcript` | speech-rate band, hedge count, filler count, long pauses, sentence completion |

Deliberately **not** used for the mark: LLM criterion scores, UI sliders, the diagnostic
`engagement_score` blend (the signals it blends are scored individually as of v1.2), `audio_grade`, and the 180 Hz `pitch_score`. Those remain evidence
and UI only — changing the LLM's scores does not move the mark.

**A visible face is required.** `validate_features` returns `INCOMPLETE` when
`video_status != success`; audio alone cannot produce a mark.

Modes:

- `WITHOUT_TECHNICAL_ACCURACY` — `final = AI performance`, auto-published.
- `WITH_TECHNICAL_ACCURACY` — `final = (1 - t) x AI + t x technical`, where `t` is the technical
  share the lecturer chose for that viva (20-90%, default 50%) and the technical score is out of
  the viva's total marks, scaled to 100 for the blend. The mark is **never** auto-published: it
  stays a draft until an examiner enters the technical score and publishes.

Every official mark is out of the viva's own total marks (set in the Viva Workspace;
`VIVA_MARK_MAX`, default 20, only applies to a viva without one). See `services/marking_scale.py`.

A parallel **feature-complete baseline** is attached as `feature_complete` /
`scoring.feature_complete` and does not affect the official mark. See
[FEATURE_INVENTORY.md](FEATURE_INVENTORY.md), which also holds its validation results.

## Tests

From the repo root:

```text
python -m unittest discover -s VivaEvaluationEngine/tests -v
```

All tests should pass; run them after any change to the scoring or the LLM helpers
(`services/llm_common.py`).

## Import style

The engine's modules import each other as `from services.x import y` and `from config import ...`, as if
this folder were the Python path root. `VivaEvaluationEngine/__init__.py` adds that folder to
`sys.path` so the same code also works when the server imports it as
`VivaEvaluationEngine.services.x`. Keep using the `services.x` form inside the engine; do not mix in
relative imports. Because of this, a module can be loaded under both names, so avoid relying on
module-level state being shared between the two.

## Further reading

| Doc | What it covers |
|---|---|
| [FEATURE_INVENTORY.md](FEATURE_INVENTORY.md) | Every feature, measured vs derived, and the baseline validation results |
| [.env.example](.env.example) | Every setting this engine reads, with defaults |
| `../Gradex_AI_Server/app/.env.example` | The server settings, including the keys this engine also uses |
