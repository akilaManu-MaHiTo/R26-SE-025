"""Turns a lecturer-uploaded ER-diagram marking-guideline PDF into the
structured guideline document that /api/diagram-evaluate grades against.

The output shape is fixed by what ``grade_diagram_with_ollama`` already
consumes from the ``diagram_marking`` collection::

    {"examCode": ..., "guideLines": [{id, criterion, description, expected, marks}], "totalMarks": N}

Mirrors subject_rubric_service.py's approach (pypdf text extraction, Groq via
urllib with strict JSON mode, defensive normalization) but stays independent of
it so either feature can change without breaking the other.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pypdf import PdfReader

_ENV_LOADED = False
_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
_LIVE_CHAT_MODELS = (
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
)
_MAX_SOURCE_CHARS = 60000
_MAX_STORED_TEXT_CHARS = 200000
_MAX_CRITERIA = 40

# Groq's JSON mode fails sporadically; a few spaced-out retries absorb it.
_ATTEMPTS = 3
_RETRY_DELAY_S = 1.5


def _load_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


def _api_key() -> Optional[str]:
    _load_env()
    for name in ("GROQ_API_KEY", "AI_API_KEY", "VIVA_LLM_API_KEY", "BACKUP_API_KEY"):
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _model_name() -> str:
    _load_env()
    return os.getenv("GROQ_MODEL") or os.getenv("VIVA_LLM_MODEL") or "openai/gpt-oss-20b"


def _model_candidates(preferred: Optional[str] = None) -> List[str]:
    ordered: List[str] = []
    for name in (preferred or _model_name(), *_LIVE_CHAT_MODELS):
        if name and name not in ordered:
            ordered.append(name)
    return ordered


class GuidelineGenerationError(Exception):
    pass


def extract_pdf_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {file_path}")
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(page.strip() for page in pages if page.strip()).strip()


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    cleaned = (text or "").strip()
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


_SYSTEM_PROMPT = """You convert a university ER-diagram marking guideline into strict JSON
that an automatic grader consumes. You are given the raw text of the lecturer's marking scheme.

Return strict JSON only (no markdown) with exactly this shape:
{
  "guideLines": [
    {
      "id": 1,
      "criterion": "Short criterion name",
      "description": "One sentence stating what the student's diagram must show.",
      "expected": { },
      "marks": 2
    }
  ]
}

Rules:
- One entry per numbered criterion in the source text, in the same order, "id" starting at 1.
- "marks" is the mark allocation stated for that criterion (a number).
- "expected" is a machine-checkable object describing what must be present. Use the shape that
  fits the criterion, choosing from these patterns:
    entity present:      {"type": "entity", "name": "Student"}
    attributes:          {"entity": "Student", "attributes": ["Name", "Email"]}
    primary key:         {"entity": "Student", "attribute": "S_Id", "type": "primary_key"}
    relationship:        {"type": "relationship", "name": "Joins", "entities": ["Student", "Course"]}
    connections:         {"connections": ["Student-Joins", "Joins-Course", "Student-Name"]}
    notation:            {"entityShape": "rectangle", "attributeShape": "ellipse",
                          "relationshipShape": "diamond", "primaryKeyNotation": "underlined"}
    completeness:        {"complete": true}
- Use the exact entity, attribute and relationship names written in the source text.
- Do not invent criteria that are not in the text, and do not merge two criteria into one.
"""


def _call_groq_once(text: str, exam_code: str, api_key: str, model: str) -> str:
    user = f"Exam code: {exam_code}\n\nMarking guideline text:\n{text[:_MAX_SOURCE_CHARS]}"
    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        _CHAT_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "GradexDiagramGuidelineService/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return str(raw["choices"][0]["message"]["content"])


def _call_groq(text: str, exam_code: str, api_key: str, model: str) -> str:
    last_error: Optional[BaseException] = None
    for candidate in _model_candidates(model):
        try:
            return _call_groq_once(text, exam_code, api_key, candidate)
        except urllib.error.HTTPError as exc:
            last_error = exc
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(exc.reason or exc)
            lowered = detail.lower()
            if exc.code == 404 or (
                exc.code == 400
                and ("model" in lowered or "not exist" in lowered or "not found" in lowered)
            ):
                continue
            raise GuidelineGenerationError(f"Groq request failed: {detail[:300]}") from exc
        except urllib.error.URLError as exc:
            raise GuidelineGenerationError(f"Groq unreachable: {exc.reason}") from exc
    if last_error:
        raise GuidelineGenerationError(f"Groq request failed: {last_error}")
    raise GuidelineGenerationError("Groq request failed")


def _clean_expected(value: Any) -> Dict[str, Any]:
    """Keep only JSON-serialisable scalars/lists — the grader reads this back
    verbatim into a prompt, so an unexpected nested blob is dropped rather than
    stored."""
    if not isinstance(value, dict):
        return {}
    cleaned: Dict[str, Any] = {}
    for key, item in value.items():
        name = str(key).strip()
        if not name:
            continue
        if isinstance(item, (str, int, float, bool)):
            cleaned[name] = item
        elif isinstance(item, list):
            cleaned[name] = [
                str(entry).strip()
                for entry in item
                if isinstance(entry, (str, int, float)) and str(entry).strip()
            ]
    return cleaned


def normalize_guidelines(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    items = payload.get("guideLines")
    if not isinstance(items, list):
        # Tolerate the model answering with a differently-cased key.
        items = payload.get("guidelines") if isinstance(payload.get("guidelines"), list) else None
    if not isinstance(items, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        criterion = str(item.get("criterion") or "").strip()
        if not criterion:
            continue

        try:
            marks = float(item.get("marks"))
        except (TypeError, ValueError):
            marks = 0.0
        marks = max(0.0, marks)

        normalized.append(
            {
                # Renumbered sequentially: the grader matches criterion_results
                # back by id, so gaps or duplicates from the model would break it.
                "id": len(normalized) + 1,
                "criterion": criterion[:200],
                "description": str(item.get("description") or "").strip()[:600],
                "expected": _clean_expected(item.get("expected")),
                "marks": int(marks) if float(marks).is_integer() else round(marks, 2),
            }
        )
        if len(normalized) >= _MAX_CRITERIA:
            break
    return normalized


def generate_guidelines(pdf_text: str, exam_code: str) -> List[Dict[str, Any]]:
    if not pdf_text.strip():
        raise GuidelineGenerationError("No extractable text in the uploaded PDF.")

    api_key = _api_key()
    if not api_key:
        raise GuidelineGenerationError(
            "No LLM API key configured (set AI_API_KEY or GROQ_API_KEY in Gradex_AI_Server/app/.env)"
        )

    model = _model_name()
    last_error = "Groq response failed schema validation"
    for attempt in range(_ATTEMPTS):
        try:
            content = _call_groq(pdf_text, exam_code, api_key, model)
        except GuidelineGenerationError as exc:
            last_error = f"attempt {attempt + 1}: {exc}"
            if attempt + 1 < _ATTEMPTS:
                time.sleep(_RETRY_DELAY_S * (attempt + 1))
            continue

        guidelines = normalize_guidelines(_extract_json_object(content))
        if guidelines:
            return guidelines
        last_error = f"attempt {attempt + 1}: no usable criteria in Groq response"

    raise GuidelineGenerationError(last_error)


def build_guideline_document(
    exam_code: str,
    guidelines: List[Dict[str, Any]],
    filename: str = "",
    source_text: str = "",
) -> Dict[str, Any]:
    """The document written to ``diagram_marking``. ``examCode``/``guideLines``
    are exactly what /api/diagram-evaluate reads; the rest is provenance."""
    now = datetime.now(timezone.utc)
    total = sum(float(entry.get("marks") or 0) for entry in guidelines)
    return {
        "examCode": exam_code,
        "guideLines": guidelines,
        "totalMarks": int(total) if float(total).is_integer() else round(total, 2),
        "source_file": {
            "filename": filename,
            "uploaded_at": now,
            "extracted_text": (source_text or "")[:_MAX_STORED_TEXT_CHARS],
            "extracted_chars": len(source_text or ""),
        },
        "created_at": now,
        "updated_at": now,
    }
