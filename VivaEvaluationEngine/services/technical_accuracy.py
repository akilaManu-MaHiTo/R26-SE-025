"""LLM-as-judge for technical accuracy: does the student's viva transcript
correctly cover the subject's expected concepts?

One Groq call per batch of concepts. Does not grade delivery, engagement, or
whether panel questions were answered — only concept coverage/correctness
against a lecturer-provided concept rubric. Purely additive to the engine:
nothing else in this package imports or calls this module, so it has no
effect unless a caller explicitly invokes attach_technical_accuracy.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from services.llm_judge import _api_key, _extract_json_object, _model_candidates, _model_name


CONCEPT_BATCH_SIZE = 12

# Set by _call_groq_batch to the model that actually answered. Thread-local so
# concurrent batches cannot overwrite each other's value.
_USED_MODEL = threading.local()

_SYSTEM_PROMPT = """You are grading the technical accuracy of a university viva transcript
against a list of concepts the student was expected to know for this subject.

For each concept, decide:
- covered: did the student say anything relevant to this concept anywhere in the transcript?
- correct: if covered, was what they said factually correct? Use null if not covered.
- evidence_quote: a short quote from the transcript supporting your judgement, or null if not covered.
- score: 0.0-1.0 quality of coverage+correctness for this concept (0 if not covered).

Do not penalize a concept as incorrect merely because it was never mentioned - use
covered=false, correct=null, score=0 for that case. Only mark correct=false when the
student said something about the concept that is actually wrong.

Return strict JSON only (no markdown) with exactly this shape:
{
  "concepts": [
    {"concept_id": "...", "covered": true, "correct": true, "evidence_quote": "...", "score": 0.9}
  ]
}
Include exactly one object per concept_id given, in the same order.
"""


def _clamp01(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number or number in (float("inf"), float("-inf")):
        return 0.0
    return round(max(0.0, min(1.0, number)), 4)


def _as_bool_or_none(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return None


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def validate_concept_result(item: Any, expected_id: str) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    concept_id = str(item.get("concept_id") or "").strip()
    if concept_id != expected_id:
        return None
    covered = _as_bool_or_none(item.get("covered"))
    if covered is None:
        return None
    correct = _as_bool_or_none(item.get("correct")) if covered else None
    evidence = item.get("evidence_quote")
    evidence = evidence.strip()[:400] if isinstance(evidence, str) and evidence.strip() else None
    return {
        "concept_id": concept_id,
        "covered": covered,
        "correct": correct,
        "evidence_quote": evidence,
        "score": _clamp01(item.get("score")),
    }


def validate_batch_payload(payload: Any, expected_ids: List[str]) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(payload, dict):
        return None
    items = payload.get("concepts")
    if not isinstance(items, list) or len(items) != len(expected_ids):
        return None
    validated: List[Dict[str, Any]] = []
    for expected_id, item in zip(expected_ids, items):
        result = validate_concept_result(item, expected_id)
        if result is None:
            return None
        validated.append(result)
    return validated


def _call_groq_batch_once(
    transcript: str, concepts: List[Dict[str, Any]], api_key: str, model: str
) -> str:
    concept_lines = "\n".join(
        f"- concept_id={c['id']}: {c['name']} - {c.get('description') or ''}".strip()
        for c in concepts
    )
    user = (
        "Student viva transcript:\n"
        f"{transcript.strip()[:12000]}\n\n"
        "Concepts to check (concept_id: name - description):\n"
        f"{concept_lines}\n"
    )
    body = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user},
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
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return str(raw["choices"][0]["message"]["content"])


def _call_groq_batch(
    transcript: str, concepts: List[Dict[str, Any]], api_key: str, model: str
) -> str:
    last_error: Optional[BaseException] = None
    for candidate in _model_candidates(model):
        try:
            content = _call_groq_batch_once(transcript, concepts, api_key, candidate)
            # Record which candidate actually answered. The configured model may
            # be retired (Groq 404s it) and the call then falls through to the
            # next candidate, so reporting the *requested* model would credit a
            # model that never ran. Thread-local because batches run in a pool.
            _USED_MODEL.value = candidate
            return content
        except urllib.error.HTTPError as exc:
            last_error = exc
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = str(exc.reason or exc)
            lowered = body.lower()
            if exc.code == 404 or (
                exc.code == 400
                and ("model" in lowered or "not exist" in lowered or "not found" in lowered)
            ):
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("Groq technical-accuracy call failed")


def _chunk(items: List[Any], size: int) -> List[List[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def score_concepts_batch(
    transcript: str,
    concepts_batch: List[Dict[str, Any]],
    *,
    api_key: str,
    model: str,
    debug: bool = False,
    groq_call=_call_groq_batch,
) -> List[Dict[str, Any]]:
    expected_ids = [str(c["id"]) for c in concepts_batch]
    last_error = "LLM response failed schema validation"
    for attempt in range(2):
        try:
            content = groq_call(transcript, concepts_batch, api_key, model)
            parsed = _extract_json_object(content)
            validated = validate_batch_payload(parsed, expected_ids)
            if validated is None:
                if debug:
                    print(f"[technical_accuracy] attempt {attempt + 1}: invalid schema")
                continue
            return validated
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
        ) as exc:
            last_error = str(exc)
            if debug:
                print(f"[technical_accuracy] attempt {attempt + 1} failed: {exc}")
    raise RuntimeError(last_error)


def _normalize_concepts(concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for concept in concepts:
        cid = str(
            concept.get("id") or concept.get("concept_id") or concept.get("name") or ""
        ).strip()
        if not cid:
            continue
        weight_raw = concept.get("weight")
        weight = max(0.0, float(weight_raw)) if _is_number(weight_raw) else 1.0
        normalized.append(
            {
                "id": cid,
                "name": str(concept.get("name") or cid),
                "description": concept.get("description") or "",
                "weight": weight,
            }
        )
    return normalized


def run_technical_accuracy(
    result: Dict[str, Any],
    concept_rubric: Optional[Dict[str, Any]],
    debug: bool = False,
    groq_call=_call_groq_batch,
) -> Dict[str, Any]:
    concepts = list((concept_rubric or {}).get("concepts") or [])
    if not concepts:
        return {
            "status": "skipped",
            "model": None,
            "overall_score": None,
            "concepts": [],
            "error": "No concept rubric available for this subject.",
        }

    audio = result.get("audio_analysis") or {}
    conversation = audio.get("conversation") or {}
    transcript = str(
        conversation.get("full_transcript") or audio.get("transcript") or ""
    ).strip()
    if not transcript:
        return {
            "status": "unavailable",
            "model": None,
            "overall_score": None,
            "concepts": [],
            "error": "No transcript available to check against the concept rubric.",
        }

    api_key = _api_key()
    if not api_key:
        return {
            "status": "unavailable",
            "model": None,
            "overall_score": None,
            "concepts": [],
            "error": "No LLM API key configured (set AI_API_KEY or GROQ_API_KEY)",
        }

    normalized = _normalize_concepts(concepts)
    if not normalized:
        return {
            "status": "skipped",
            "model": None,
            "overall_score": None,
            "concepts": [],
            "error": "Concept rubric had no usable concepts.",
        }

    model = _model_name()
    batches = _chunk(normalized, CONCEPT_BATCH_SIZE)
    errors: List[str] = []

    def _score_one(batch: List[Dict[str, Any]]) -> Any:
        _USED_MODEL.value = None
        try:
            scored_batch = score_concepts_batch(
                transcript, batch, api_key=api_key, model=model, debug=debug, groq_call=groq_call
            )
            # Carry the worker thread's value back — the caller reads it from the
            # main thread, where the thread-local would otherwise be unset.
            return (scored_batch, getattr(_USED_MODEL, "value", None))
        except Exception as exc:  # noqa: BLE001 - collected below, never raised to caller
            return exc

    workers = min(4, len(batches)) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        batch_results = list(pool.map(_score_one, batches))

    by_id = {c["id"]: c for c in normalized}
    scored: List[Dict[str, Any]] = []
    used_model: Optional[str] = None
    for batch, batch_result in zip(batches, batch_results):
        if isinstance(batch_result, Exception):
            errors.append(str(batch_result))
            continue
        batch_result, batch_model = batch_result
        if batch_model:
            used_model = batch_model
        for item in batch_result:
            concept = by_id.get(item["concept_id"])
            scored.append(
                {
                    **item,
                    "name": concept["name"] if concept else item["concept_id"],
                    "weight": concept["weight"] if concept else 1.0,
                }
            )

    if not scored:
        return {
            "status": "unavailable",
            "model": model,
            "overall_score": None,
            "concepts": [],
            "error": "; ".join(errors) or "Technical-accuracy scoring unavailable",
        }

    total_weight = sum(c["weight"] for c in scored) or 1.0
    weighted = sum(c["weight"] * c["score"] for c in scored)
    overall_score = round((weighted / total_weight) * 10.0, 2)

    payload: Dict[str, Any] = {
        "status": "success" if not errors else "partial",
        # The model that answered, not the one requested — they differ whenever
        # the configured model is retired and the call falls through.
        "model": used_model or model,
        "overall_score": overall_score,
        "concepts": scored,
    }
    if errors:
        payload["error"] = "; ".join(errors)
    return payload


def attach_technical_accuracy(
    result: Dict[str, Any],
    concept_rubric: Optional[Dict[str, Any]],
    debug: bool = False,
    groq_call=_call_groq_batch,
) -> Dict[str, Any]:
    """Mutate+return merged pipeline result with technical_accuracy_ai attached."""
    enriched = dict(result)
    enriched["technical_accuracy_ai"] = run_technical_accuracy(
        enriched, concept_rubric, debug=debug, groq_call=groq_call
    )
    return enriched
