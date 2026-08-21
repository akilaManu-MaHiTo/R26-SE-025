"""LLM-as-judge layer for viva delivery criteria.

Design rules:
- Never sends raw audio/video.
- Only synthesizes already-computed deterministic features.
- Validates JSON schema; on failure falls back to formula-derived scores.
- Uses Groq OpenAI-compatible chat API when AI_API_KEY / GROQ_API_KEY is set
  (same env convention as GradingEngine). Missing key → formula fallback.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


CRITERIA = ("communication_clarity", "confidence", "engagement")
_ENV_LOADED = False


def _load_env_files() -> None:
    """Load local .env files without requiring python-dotenv."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    engine_root = Path(__file__).resolve().parents[1]
    candidates = [
        engine_root / ".env",
        engine_root.parent / "Gradex_AI_Server" / "app" / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except OSError:
            continue


def _api_key() -> Optional[str]:
    _load_env_files()
    for name in ("VIVA_LLM_API_KEY", "GROQ_API_KEY", "AI_API_KEY", "BACKUP_API_KEY"):
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _model_name() -> str:
    _load_env_files()
    return os.getenv("VIVA_LLM_MODEL") or os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b"


# Groq retired llama-3.3-70b-versatile / llama-3.1-8b-instant on 16 Aug 2026.
LIVE_CHAT_MODELS = (
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
)


def _model_candidates(preferred: Optional[str] = None) -> List[str]:
    ordered: List[str] = []
    for name in (preferred or _model_name(), *LIVE_CHAT_MODELS):
        if name and name not in ordered:
            ordered.append(name)
    return ordered

_SYSTEM_PROMPT = """You are an academic viva examiner assistant. You are given pre-computed
acoustic, transcript, and video-engagement features for one student's oral exam
response — not the raw recording. Score the student on three criteria using only
the data provided. Do not invent facts not present in the data. Cite specific
numbers from the data in your justification, in the style: "Confidence reduced —
8 hedge phrases detected ('I think', 'maybe'), concentrated in the first 2 minutes."

Criteria (score each 0-10):
- Communication Clarity: speech rate, hedge/filler frequency, sentence completion
- Confidence: pitch variation, energy consistency, hedge/filler frequency; use audio emotion only if source is "model"
- Engagement: video engagement_summary ratios, emotion summary

If audio_emotion.excluded_from_scoring is true, ignore speech-emotion labels entirely.
Return strict JSON only (no markdown):
{
  "communication_clarity": {"score": X, "justification": "..."},
  "confidence": {"score": X, "justification": "..."},
  "engagement": {"score": X, "justification": "..."}
}
"""


def _clamp(value: float, minimum: float = 0.0, maximum: float = 10.0) -> float:
    return max(minimum, min(maximum, value))


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or number in (float("inf"), float("-inf")):
        return default
    return number


def build_formula_judge_scores(
    *,
    confidence_score: Optional[float],
    engagement_score: Optional[float],
    audio_grade: Optional[float],
    transcript_features: Optional[Dict[str, Any]] = None,
    grade_breakdown: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Deterministic fallback / side-by-side scores from existing pipeline metrics."""
    features = transcript_features or {}
    breakdown = grade_breakdown or {}

    clarity_parts = []
    for key in ("clarity_score", "articulation_score", "transcript_score"):
        value = _safe_float(breakdown.get(key))
        if value is not None:
            clarity_parts.append(value)
    if clarity_parts:
        communication = sum(clarity_parts) / len(clarity_parts) * 10.0
    elif audio_grade is not None:
        communication = float(audio_grade)
    else:
        communication = 5.0

    hedge = int(features.get("hedge_count") or 0)
    filler = int(features.get("filler_count") or 0)
    disfluency_penalty = min(3.0, (hedge + filler) * 0.15)
    communication = _clamp(communication - disfluency_penalty)

    if confidence_score is not None:
        confidence = _clamp(float(confidence_score) / 10.0)
    else:
        pitch_stability = _safe_float(breakdown.get("pitch_stability"))
        emotion_score = _safe_float(breakdown.get("emotion_score"))
        parts = [p for p in (pitch_stability, emotion_score) if p is not None]
        confidence = _clamp((sum(parts) / len(parts) * 10.0) if parts else 5.0)
    confidence = _clamp(confidence - min(2.0, hedge * 0.1))

    if engagement_score is not None:
        engagement = _clamp(float(engagement_score) / 10.0)
    else:
        engagement = 5.0

    band = features.get("speech_rate_band")
    clarity_note = "Derived from acoustic clarity/articulation/transcript components"
    if band == "too_slow":
        clarity_note += "; speech rate below the 120–160 WPM band"
        communication = _clamp(communication - 0.5)
    elif band == "too_fast":
        clarity_note += "; speech rate above the 120–160 WPM band"
        communication = _clamp(communication - 0.5)

    return {
        "source": "formula_fallback",
        "model": None,
        "communication_clarity": {
            "score": round(communication, 2),
            "justification": (
                f"{clarity_note}. Hedge phrases={hedge}, fillers={filler}."
            ),
        },
        "confidence": {
            "score": round(confidence, 2),
            "justification": (
                "Mapped from facial positivity / acoustic stability with a hedge penalty "
                f"({hedge} hedge phrases)."
                if confidence_score is not None
                else "Mapped from acoustic stability/emotion components with a hedge penalty."
            ),
        },
        "engagement": {
            "score": round(engagement, 2),
            "justification": (
                "Mapped from the multimodal engagement_score (0–100 → 0–10)."
                if engagement_score is not None
                else "Default mid score — video engagement unavailable."
            ),
        },
    }


def _validate_judge_payload(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    validated: Dict[str, Any] = {}
    for key in CRITERIA:
        item = payload.get(key)
        if not isinstance(item, dict):
            return None
        score = _safe_float(item.get("score"))
        justification = item.get("justification")
        if score is None or not isinstance(justification, str) or not justification.strip():
            return None
        validated[key] = {
            "score": round(_clamp(score), 2),
            "justification": justification.strip()[:600],
        }
    return validated


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _call_groq_chat_once(payload: Dict[str, Any], api_key: str, model: str) -> str:
    body = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Score this viva using only the following JSON feature payload:\n"
                    + json.dumps(payload, ensure_ascii=False)
                ),
            },
        ],
    }
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "GradexVivaEvaluationEngine/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return str(raw["choices"][0]["message"]["content"])


def _call_groq_chat(payload: Dict[str, Any], api_key: str, model: str) -> str:
    last_error: Optional[Exception] = None
    used_model = model
    for candidate in _model_candidates(model):
        used_model = candidate
        try:
            content = _call_groq_chat_once(payload, api_key, candidate)
            _call_groq_chat.last_model = candidate  # type: ignore[attr-defined]
            return content
        except urllib.error.HTTPError as exc:
            last_error = exc
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = str(exc.reason or exc)
            lowered = body.lower()
            if exc.code == 404 or (
                exc.code == 400 and ("model" in lowered or "not exist" in lowered or "not found" in lowered)
            ):
                continue
            raise
    _call_groq_chat.last_model = used_model  # type: ignore[attr-defined]
    if last_error:
        raise last_error
    raise RuntimeError("Groq chat failed")


def assemble_judge_input(result: Dict[str, Any]) -> Dict[str, Any]:
    audio = result.get("audio_analysis") or {}
    transcript_features = audio.get("transcript_features") or {}
    excerpt = audio.get("transcript_excerpt") or (audio.get("transcript") or "")[:500]
    raw_emotion = audio.get("audio_emotion") or {}
    emotion_source = str(raw_emotion.get("source", "heuristic")).strip().lower() or "heuristic"
    if emotion_source == "model":
        audio_emotion = raw_emotion
    else:
        # Heuristic SER must not influence LLM grades — pass provenance only.
        audio_emotion = {
            "source": emotion_source,
            "excluded_from_scoring": True,
            "note": "Heuristic speech-emotion omitted; not used for scoring.",
        }

    return {
        "transcript_excerpt": excerpt,
        "transcript_features": {
            key: transcript_features.get(key)
            for key in (
                "hedge_count",
                "hedge_phrases",
                "filler_count",
                "filler_words",
                "speech_rate_wpm",
                "speech_rate_band",
                "pause_count",
                "long_pause_count",
                "sentence_completion_ratio",
                "pause_detection_granularity",
                "word_count",
            )
            if key in transcript_features
        },
        "acoustic_features": audio.get("acoustic_features") or {},
        "pitch_profile": audio.get("pitch_profile") or {},
        "audio_emotion": audio_emotion,
        "audio_grade": audio.get("audio_grade"),
        "grade_breakdown": {
            key: value
            for key, value in (audio.get("grade_breakdown") or {}).items()
            if key.endswith("_score")
            or key in {"pitch_stability", "emotion_source", "emotion_excluded"}
        },
        "video_summary": {
            "summary": result.get("summary") or {},
            "engagement_summary": result.get("engagement_summary") or {},
            "confidence_score": result.get("confidence_score"),
            "engagement_score": result.get("engagement_score"),
            "video_status": result.get("video_status"),
            "coverage": result.get("coverage") or {},
        },
    }


def run_llm_judge(result: Dict[str, Any], debug: bool = False) -> Dict[str, Any]:
    """Return llm_evaluation dict with LLM scores or formula fallback."""
    audio = result.get("audio_analysis") or {}
    fallback = build_formula_judge_scores(
        confidence_score=_safe_float(result.get("confidence_score")),
        engagement_score=_safe_float(result.get("engagement_score")),
        audio_grade=_safe_float(audio.get("audio_grade")),
        transcript_features=audio.get("transcript_features") or {},
        grade_breakdown=audio.get("grade_breakdown") or {},
    )

    api_key = _api_key()
    if not api_key:
        fallback["status"] = "fallback"
        fallback["error"] = "No LLM API key configured (set AI_API_KEY or GROQ_API_KEY)"
        return fallback

    judge_input = assemble_judge_input(result)
    model = _model_name()
    last_error = None

    for attempt in range(2):
        try:
            content = _call_groq_chat(judge_input, api_key=api_key, model=model)
            parsed = _extract_json_object(content)
            validated = _validate_judge_payload(parsed)
            if validated is None:
                last_error = "LLM response failed schema validation"
                if debug:
                    print(f"[llm_judge] attempt {attempt + 1}: {last_error}")
                continue
            resolved = getattr(_call_groq_chat, "last_model", model)
            return {
                "source": "llm",
                "status": "success",
                "model": resolved,
                **validated,
                "formula_fallback": {
                    key: fallback[key]
                    for key in CRITERIA
                },
            }
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if debug:
                print(f"[llm_judge] attempt {attempt + 1} failed: {exc}")

    fallback["status"] = "fallback"
    fallback["error"] = last_error or "LLM judge unavailable"
    fallback["model_requested"] = model
    return fallback


def attach_llm_evaluation(result: Dict[str, Any], debug: bool = False) -> Dict[str, Any]:
    """Mutate+return merged pipeline result with llm_evaluation attached."""
    enriched = dict(result)
    enriched["llm_evaluation"] = run_llm_judge(enriched, debug=debug)
    return enriched
