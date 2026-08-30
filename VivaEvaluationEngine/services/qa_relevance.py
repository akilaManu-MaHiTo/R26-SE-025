"""Semantic Q&A relevance: did the student's answer address the panel question?

One Groq call per pair. Does not grade, mark, or judge technical correctness.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from services.conversation import MAX_PAIRS, pair_question_answers
from services.conversation_understanding import apply_conversation_understanding
from services.llm_judge import _api_key, _extract_json_object, _model_candidates, _model_name


RELEVANCE_VALUES = frozenset({"high", "medium", "low", "irrelevant"})
ANSWER_TYPES = frozenset({"direct", "partial", "indirect", "unclear", "irrelevant", "no_answer"})

_SYSTEM_PROMPT = """You are analyzing a university viva conversation.

Your task is ONLY to determine whether the student's answer addresses the examiner's question.

Do not grade the student.
Do not judge the student's intelligence.
Do not assign academic marks.
Do not determine technical correctness unless explicitly requested.

Analyze semantic meaning, not keyword overlap.

Return strict JSON only (no markdown) with exactly these fields:
{
  "addresses_question": true or false,
  "relevance": "high" | "medium" | "low" | "irrelevant",
  "answer_type": "direct" | "partial" | "indirect" | "unclear" | "irrelevant" | "no_answer",
  "explanation": "short explanation",
  "confidence": 0.0
}
"""


def _clamp_confidence(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return round(max(0.0, min(1.0, number)), 4)


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return None


def validate_relevance_payload(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    addresses = _as_bool(payload.get("addresses_question"))
    relevance = str(payload.get("relevance") or "").strip().lower()
    answer_type = str(payload.get("answer_type") or "").strip().lower()
    explanation = payload.get("explanation")
    confidence = _clamp_confidence(payload.get("confidence"))
    if addresses is None:
        return None
    if relevance not in RELEVANCE_VALUES:
        return None
    if answer_type not in ANSWER_TYPES:
        return None
    if not isinstance(explanation, str) or not explanation.strip():
        return None
    if confidence is None:
        return None
    return {
        "addresses_question": addresses,
        "relevance": relevance,
        "answer_type": answer_type,
        "explanation": explanation.strip()[:600],
        "confidence": confidence,
    }


def _empty_answer_result() -> Dict[str, Any]:
    return {
        "status": "success",
        "addresses_question": False,
        "relevance": "irrelevant",
        "answer_type": "no_answer",
        "explanation": "The student did not answer after this panel question.",
        "confidence": 1.0,
        "source": "rule",
    }


def _unavailable(reason: str) -> Dict[str, Any]:
    return {
        "status": "unavailable",
        "addresses_question": None,
        "relevance": None,
        "answer_type": None,
        "explanation": None,
        "confidence": None,
        "source": "unavailable",
        "error": reason,
    }


def _chat_url() -> str:
    _load_env_files()
    base = (os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL") or os.getenv("VIVA_LLM_BASE_URL") or "https://api.groq.com/openai/v1").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _call_groq_pair_once(question: str, answer: str, api_key: str, model: str) -> str:
    user = (
        "Question:\n"
        f"{question.strip()}\n\n"
        "Student answer:\n"
        f"{answer.strip()}\n"
    )
    body = {
        "model": model,
        "temperature": 0.2,
        "stream": False,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        _chat_url(),
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



def _call_groq_pair(question: str, answer: str, api_key: str, model: str) -> str:
    last_error: Optional[BaseException] = None
    for candidate in _model_candidates(model):
        try:
            return _call_groq_pair_once(question, answer, api_key, candidate)
        except urllib.error.HTTPError as exc:
            last_error = exc
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
    if last_error:
        raise last_error
    raise RuntimeError("Groq Q&A call failed")


def analyze_pair(
    pair: Dict[str, Any],
    *,
    api_key: Optional[str],
    model: str,
    debug: bool = False,
    groq_call=_call_groq_pair,
) -> Dict[str, Any]:
    result = {
        "question": pair.get("question") or "",
        "answer": pair.get("answer") or "",
        "question_start": pair.get("question_start"),
        "question_end": pair.get("question_end"),
        "answer_start": pair.get("answer_start"),
        "answer_end": pair.get("answer_end"),
        "panel_speaker": pair.get("panel_speaker"),
        "panel_label": pair.get("panel_label") or "PANEL",
    }
    if not str(result["answer"]).strip():
        result.update(_empty_answer_result())
        return result
    if not api_key:
        result.update(_unavailable("No LLM API key configured (set AI_API_KEY or GROQ_API_KEY)"))
        return result

    last_error = "LLM response failed schema validation"
    for attempt in range(2):
        try:
            content = groq_call(result["question"], result["answer"], api_key, model)
            parsed = _extract_json_object(content)
            validated = validate_relevance_payload(parsed)
            if validated is None:
                if debug:
                    print(f"[qa_relevance] attempt {attempt + 1}: invalid schema")
                continue
            result.update(validated)
            result["status"] = "success"
            result["source"] = "llm"
            return result
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if debug:
                print(f"[qa_relevance] attempt {attempt + 1} failed: {exc}")
    result.update(_unavailable(last_error))
    return result


def run_qa_analysis(result: Dict[str, Any], debug: bool = False, groq_call=_call_groq_pair) -> Dict[str, Any]:
    audio = result.get("audio_analysis") or {}
    conversation = audio.get("conversation") or {}
    turns = conversation.get("turns") or []
    pairs = conversation.get("pair_candidates")
    if pairs is None:
        pairs = pair_question_answers(turns)
    pairs = list(pairs)[:MAX_PAIRS]

    model = _model_name()
    api_key = _api_key()
    analyzed: List[Dict[str, Any]] = []
    if pairs:
        workers = min(4, len(pairs))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            analyzed = list(
                pool.map(
                    lambda pair: analyze_pair(
                        pair, api_key=api_key, model=model, debug=debug, groq_call=groq_call
                    ),
                    pairs,
                )
            )

    if not pairs:
        status = "empty"
        error = "No panel question–student answer pairs were detected"
    elif all(item.get("status") == "unavailable" for item in analyzed):
        status = "unavailable"
        error = analyzed[0].get("error") if analyzed else "Q&A analysis unavailable"
    elif any(item.get("status") == "unavailable" for item in analyzed):
        status = "partial"
        error = None
    else:
        status = "success"
        error = None

    payload: Dict[str, Any] = {
        "status": status,
        "model": model if api_key else None,
        "pair_count": len(analyzed),
        "pairs": analyzed,
    }
    if error:
        payload["error"] = error
    return payload


def attach_qa_analysis(
    result: Dict[str, Any],
    debug: bool = False,
    groq_call=_call_groq_pair,
    structure_groq_call=None,
) -> Dict[str, Any]:
    """Run AI 1 (conversation structure) then AI 2 (pair relevance)."""
    enriched = dict(result)
    audio = dict(enriched.get("audio_analysis") or {})
    conversation = dict(audio.get("conversation") or {})
    kwargs = {
        "debug": debug,
    }
    if structure_groq_call is not None:
        kwargs["groq_call"] = structure_groq_call
    conversation = apply_conversation_understanding(conversation, **kwargs)
    audio["conversation"] = conversation
    if conversation.get("full_transcript"):
        audio["full_transcript"] = conversation["full_transcript"]
    enriched["audio_analysis"] = audio
    enriched["qa_analysis"] = run_qa_analysis(enriched, debug=debug, groq_call=groq_call)
    return enriched
