from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

import librosa
import numpy as np

from config import (
    HEURISTIC_EMOTION_CONFIDENCE_CAP,
    canonical_emotion_label,
)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _ser_backend() -> str:
    raw = (os.getenv("VIVA_SER_BACKEND") or "huggingface").strip().lower()
    if raw in {"hf", "huggingface", "transformers"}:
        return "huggingface"
    if raw in {"speechbrain", "sb"}:
        return "speechbrain"
    if raw in {"heuristic", "off", "none"}:
        return "heuristic"
    return "huggingface"


def _hf_model_id() -> str:
    # Default to wav2vec2-base SUPERB ER (~360MB) — the previous lg-xlsr checkpoint
    # often OOMs / kills uvicorn on first download during a live request.
    return (
        os.getenv("VIVA_SER_MODEL")
        or "superb/wav2vec2-base-superb-er"
    )


def _speechbrain_source() -> str:
    return (
        os.getenv("VIVA_SER_SPEECHBRAIN_SOURCE")
        or "speechbrain/emotion-recognition-wav2vec2-IEMOCAP"
    )


def _heuristic_speech_emotion(audio_path: str) -> Dict[str, object]:
    # Lightweight fallback when no SER model is available / fails.
    y, sr = librosa.load(audio_path, sr=16000, mono=True)
    if y.size == 0:
        return {
            "predicted_emotion": "neutral",
            "confidence": 0.3,
            "source": "heuristic",
            "emotion_probabilities": {"neutral": 1.0},
        }

    rms = float(np.mean(librosa.feature.rms(y=y)))

    try:
        f0 = librosa.yin(y, fmin=65, fmax=400, sr=sr)
        f0 = np.asarray(f0, dtype=float)
        valid = f0[np.isfinite(f0) & (f0 > 0)]
        pitch_mean = float(np.mean(valid)) if valid.size else 0.0
        pitch_std = float(np.std(valid)) if valid.size else 0.0
    except Exception:
        pitch_mean = 0.0
        pitch_std = 0.0

    if pitch_mean >= 225 or (pitch_std > 45 and rms > 0.04):
        emotion = "surprise"
    elif pitch_mean <= 145:
        emotion = "sad"
    elif rms > 0.05:
        emotion = "happy"
    else:
        emotion = "neutral"

    confidence = 0.35
    confidence += min(0.25, abs(pitch_mean - 180.0) / 220.0)
    confidence += min(0.2, pitch_std / 200.0)
    confidence += min(0.2, rms * 2.5)
    confidence = _clamp(confidence, 0.0, HEURISTIC_EMOTION_CONFIDENCE_CAP)

    probs = {
        "happy": 0.0,
        "surprise": 0.0,
        "neutral": 0.0,
        "sad": 0.0,
    }
    probs[emotion] = round(confidence, 4)
    remaining = max(0.0, 1.0 - probs[emotion])
    probs["neutral"] = round(max(probs["neutral"], remaining * 0.5), 4)

    return {
        "predicted_emotion": emotion,
        "confidence": round(confidence, 4),
        "source": "heuristic",
        "emotion_probabilities": probs,
    }


def _normalize_ranked(scores: List[Tuple[str, float]]) -> Dict[str, object]:
    if not scores:
        return {
            "predicted_emotion": "neutral",
            "confidence": 0.0,
            "source": "model",
            "emotion_probabilities": {"neutral": 1.0},
        }

    ranked = sorted(
        ((canonical_emotion_label(label), float(score)) for label, score in scores),
        key=lambda item: item[1],
        reverse=True,
    )
    # Collapse duplicate canonical labels (e.g. calm→neutral + neutral).
    merged: Dict[str, float] = {}
    for label, score in ranked:
        merged[label] = merged.get(label, 0.0) + max(0.0, score)

    ordered = sorted(merged.items(), key=lambda item: item[1], reverse=True)
    top_label, top_score = ordered[0]
    total = sum(v for _, v in ordered) or 1.0
    probs = {label: round(score / total, 4) for label, score in ordered}
    return {
        "predicted_emotion": top_label,
        "confidence": round(_clamp(top_score if top_score <= 1.0 else top_score / total), 4),
        "source": "model",
        "emotion_probabilities": probs,
    }


@lru_cache(maxsize=1)
def _load_hf_classifier():
    from transformers import pipeline

    model_id = _hf_model_id()
    return pipeline(
        "audio-classification",
        model=model_id,
        top_k=None,
        device=-1,  # CPU — avoids GPU OOM surprises on first load
    )


@lru_cache(maxsize=1)
def _load_speechbrain_classifier():
    # Optional backend — only imported when VIVA_SER_BACKEND=speechbrain.
    from speechbrain.inference.interfaces import foreign_class

    source = _speechbrain_source()
    return foreign_class(
        source=source,
        pymodule_file="custom_interface.py",
        classname="CustomEncoderWav2vec2Classifier",
    )


def _predict_huggingface(audio_path: str) -> Dict[str, object]:
    # Isolated process: wav2vec2 + Whisper + FER in one process OOMs Windows and
    # kills uvicorn with no Python traceback ("Upload failed" in the client).
    worker = Path(__file__).resolve().parent / "ser_worker.py"
    proc = subprocess.run(
        [sys.executable, str(worker), audio_path, _hf_model_id()],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "ser worker failed").strip()[-500:]
        raise RuntimeError(f"SER worker exit {proc.returncode}: {err}")

    lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    raw = json.loads(lines[-1] if lines else "[]")
    if isinstance(raw, dict):
        if raw.get("error"):
            raise RuntimeError(str(raw["error"]))
        raw = [raw]
    scores: List[Tuple[str, float]] = []
    for item in raw or []:
        label = str(item.get("label", ""))
        score = float(item.get("score", 0.0))
        if label:
            scores.append((label, score))
    result = _normalize_ranked(scores)
    result["model"] = _hf_model_id()
    result["backend"] = "huggingface"
    return result


def _predict_speechbrain(audio_path: str) -> Dict[str, object]:
    classifier = _load_speechbrain_classifier()
    out_prob, score, index, text_lab = classifier.classify_file(audio_path)
    label = text_lab[0] if isinstance(text_lab, (list, tuple)) else str(text_lab)
    confidence = float(score[0]) if hasattr(score, "__getitem__") else float(score)
    # SpeechBrain IEMOCAP typically: neu / hap / sad / ang
    result = _normalize_ranked([(str(label), confidence)])
    result["model"] = _speechbrain_source()
    result["backend"] = "speechbrain"
    # Keep full softmax if available.
    try:
        probs_tensor = out_prob[0]
        # Label order depends on the checkpoint; expose raw top only when unsure.
        result["raw_top_score"] = round(confidence, 4)
        _ = probs_tensor  # reserved for future label-order mapping
    except Exception:
        pass
    return result


def extract_speech_emotion(audio_path: str) -> Dict[str, object]:
    """
    Speech emotion recognition.

    Prefer a local model (HuggingFace by default). On import/runtime failure,
    fall back to the pitch/RMS heuristic with source=\"heuristic\" so grades
    continue to exclude SER until a real model succeeds.
    """
    backend = _ser_backend()
    if backend == "heuristic":
        return _heuristic_speech_emotion(audio_path)

    try:
        if backend == "speechbrain":
            return _predict_speechbrain(audio_path)
        return _predict_huggingface(audio_path)
    except Exception as exc:
        fallback = _heuristic_speech_emotion(audio_path)
        fallback["model_error"] = f"{type(exc).__name__}: {exc}"
        fallback["requested_backend"] = backend
        return fallback
