"""Hybrid Bloom classifier using ModernBERT (safetensors) with confidence threshold.

Mirrors `test_it2040_exam.py` loading but as lazy singleton for V2 engine.
- Weights: models/bloom_modernbert/bloom.safetensors (or model.safetensors)
- Tokenizer: models/bloom_modernbert/tokenizer/
- Config: models/bloom_modernbert/config.json (id2label BT1..BT6)

Usage:
    from app.classifier.bloom_classifier import get_bloom_classifier, predict_bloom, is_bloom_model_available

    result = predict_bloom("Convert EER model to relational model")
    # {"label":"BT3","level":"Apply","confidence":0.81,"probs":{"BT1":..},"model_version":"modernbert-bloom-v1"}

Hybrid policy (Option B): caller checks confidence >= settings.bloom_model_threshold
before trusting the prediction; otherwise fall back to LLM/rules.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

BLOOM_ID2LEVEL: dict[str, str] = {
    "BT1": "Remember",
    "BT2": "Understand",
    "BT3": "Apply",
    "BT4": "Analyze",
    "BT5": "Evaluate",
    "BT6": "Create",
}
# reverse for validation against app.analytics.taxonomy.BLOOM_LEVELS
LEVEL2ID = {v: k for k, v in BLOOM_ID2LEVEL.items()}

_MODEL = None
_TOKENIZER = None
_CONFIG = None
_LOAD_ERROR: str | None = None


def _model_dir() -> Path:
    # settings.bloom_model_dir may be relative to project root
    p = Path(settings.bloom_model_dir)
    if not p.is_absolute():
        # app/classifier/bloom_classifier.py -> parents[2] = V2_QuestionExamPredictionEngine
        project_root = Path(__file__).resolve().parents[2]
        p = project_root / p
    return p


def is_bloom_model_available() -> bool:
    """Lightweight check without loading torch."""
    if not getattr(settings, "bloom_enabled", True):
        return False
    d = _model_dir()
    has_config = (d / "config.json").exists()
    has_weights = (d / "bloom.safetensors").exists() or (d / "model.safetensors").exists()
    has_tok = (d / "tokenizer" / "tokenizer.json").exists()
    return has_config and has_weights and has_tok


def _load_model():
    global _MODEL, _TOKENIZER, _CONFIG, _LOAD_ERROR
    if _MODEL is not None:
        return _MODEL, _TOKENIZER, _CONFIG
    if _LOAD_ERROR is not None:
        raise RuntimeError(_LOAD_ERROR)
    try:
        import torch  # noqa: F401
        from safetensors.torch import load_file
        from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        _LOAD_ERROR = f"bloom model deps missing: {exc}"
        raise RuntimeError(_LOAD_ERROR) from exc

    d = _model_dir()
    try:
        config = AutoConfig.from_pretrained(d, local_files_only=True)
        model = AutoModelForSequenceClassification.from_config(config)
        weights_path = d / "bloom.safetensors"
        if not weights_path.exists():
            weights_path = d / "model.safetensors"
        state_dict = load_file(str(weights_path), device="cpu")
        missing, unexpected = model.load_state_dict(state_dict, strict=False)
        if missing or unexpected:
            raise RuntimeError(f"Checkpoint mismatch missing={missing} unexpected={unexpected}")
        model.eval()
        # respect bloom_device setting if torch available
        device = getattr(settings, "bloom_device", "cpu")
        if device != "cpu":
            try:
                model.to(device)
            except Exception:
                logger.warning("Failed to move bloom model to %s, staying on cpu", device)
        tokenizer = AutoTokenizer.from_pretrained(d / "tokenizer", local_files_only=True)
        _MODEL, _TOKENIZER, _CONFIG = model, tokenizer, config
        logger.info("Bloom ModernBERT loaded from %s (%s)", d, config.id2label)
        return _MODEL, _TOKENIZER, _CONFIG
    except Exception as exc:
        _LOAD_ERROR = str(exc)
        logger.exception("Failed to load bloom model from %s", d)
        raise


def get_bloom_classifier():
    """Return loaded (model, tokenizer, config) tuple, lazy."""
    return _load_model()


def predict_bloom(text: str, max_length: int | None = None) -> dict[str, Any]:
    """Predict single text, return {label, level, confidence, probs, model_version}."""
    results = predict_bloom_batch([text], max_length=max_length)
    return results[0]


def predict_bloom_batch(texts: list[str], max_length: int | None = None) -> list[dict[str, Any]]:
    """Batched prediction. Returns list of dicts with label/level/confidence/probs."""
    if not texts:
        return []
    import torch

    model, tokenizer, config = _load_model()
    ml = max_length if max_length is not None else int(getattr(settings, "bloom_max_length", 512))
    # clamp to config max_position_embeddings
    try:
        ml = min(ml, int(getattr(config, "max_position_embeddings", 8192)))
    except Exception:
        pass

    encoded = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=ml,
        return_tensors="pt",
    )
    # move to model device if needed
    try:
        device = next(model.parameters()).device
        encoded = {k: v.to(device) for k, v in encoded.items()}
    except Exception:
        pass

    with torch.inference_mode():
        logits = model(**encoded).logits
        probs = torch.softmax(logits, dim=-1)

    id2label: dict[int, str] = getattr(config, "id2label", {0: "BT1", 1: "BT2", 2: "BT3", 3: "BT4", 4: "BT5", 5: "BT6"})
    # normalize keys to int
    id2label = {int(k): v for k, v in id2label.items()}

    results: list[dict[str, Any]] = []
    for row in probs:
        pred_idx = int(row.argmax().item())
        label = id2label.get(pred_idx, f"BT{pred_idx+1}")
        level = BLOOM_ID2LEVEL.get(label, label)
        conf = float(row[pred_idx].item())
        prob_dict = {id2label[i]: round(float(s), 6) for i, s in enumerate(row)}
        # also map to level names for convenience
        level_probs = {BLOOM_ID2LEVEL.get(k, k): v for k, v in prob_dict.items()}
        results.append(
            {
                "label": label,
                "level": level,
                "confidence": round(conf, 6),
                "probs": prob_dict,
                "level_probs": level_probs,
                "pred_index": pred_idx,
                "model_version": "modernbert-bloom-v1",
            }
        )
    return results


def reload_bloom_model() -> None:
    """Clear cached model (for tests)."""
    global _MODEL, _TOKENIZER, _CONFIG, _LOAD_ERROR
    _MODEL = _TOKENIZER = _CONFIG = None
    _LOAD_ERROR = None
