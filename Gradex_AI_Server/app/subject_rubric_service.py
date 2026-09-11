"""Turns a lecturer-uploaded subject PDF into a structured "concept rubric" —
a list of concepts the student is expected to cover in a technical viva —
and stores/retrieves it per subject_code.

Deliberately independent of GradingEngine and VivaEvaluationEngine: this is a
fresh implementation (PDF extraction via pypdf, Groq call via urllib) that
follows the same *ideas* used elsewhere in this monorepo (PDF -> Groq ->
strict JSON, defensive output normalization) without importing or depending
on any other subproject's code, so those subprojects can change freely
without affecting this feature.
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
from pymongo.errors import DuplicateKeyError
from pypdf import PdfReader

_ENV_LOADED = False
_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
_LIVE_CHAT_MODELS = (
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
)
_MAX_SOURCE_CHARS = 60000

# Extracted text retained per source file so the lecturer can see what the AI
# read (the PDF itself is not kept). Bounded to protect the 16MB document limit.
_MAX_STORED_TEXT_CHARS = 200000

# Groq's JSON mode fails sporadically on long inputs; a few spaced-out retries
# absorb it. Kept small so an upload still fails fast when Groq is truly down.
_RUBRIC_ATTEMPTS = 3
_RUBRIC_RETRY_DELAY_S = 1.5


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


class RubricGenerationError(Exception):
    pass


def extract_pdf_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {file_path}")
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(page.strip() for page in pages if page.strip())
    return text.strip()


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


_SYSTEM_PROMPT = """You are helping a university lecturer build a concept checklist for grading
technical vivas. You are given lecture/subject content text. Extract the distinct technical
concepts a student should be able to explain, at a granularity useful for oral questioning
(not every sentence - the core ideas, terms, and techniques covered).

Return strict JSON only (no markdown) with exactly this shape:
{
  "concepts": [
    {"name": "short concept name", "description": "one sentence of what correct coverage looks like", "weight": 3}
  ]
}
"weight" is 1-5 importance (5 = core/foundational, 1 = minor detail).
Produce at most 25 concepts, and keep each "description" to one short sentence (under 20 words).
Prefer the most important concepts if the content covers more than 25.
Do not invent concepts not present in the text.
"""


def _call_groq_once(text: str, subject_name: str, api_key: str, model: str) -> str:
    user = f"Subject: {subject_name}\n\nContent:\n{text[:_MAX_SOURCE_CHARS]}"
    body = {
        "model": model,
        "temperature": 0.2,
        # Without an explicit budget the model can be cut off mid-object on
        # content-rich PDFs; Groq's JSON mode then rejects the truncated body
        # with json_validate_failed and an empty failed_generation. This is
        # sized for the 25-concept cap the system prompt asks for.
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
            "User-Agent": "GradexSubjectRubricService/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return str(raw["choices"][0]["message"]["content"])


def _call_groq(text: str, subject_name: str, api_key: str, model: str) -> str:
    last_error: Optional[BaseException] = None
    for candidate in _model_candidates(model):
        try:
            return _call_groq_once(text, subject_name, api_key, candidate)
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
            raise RubricGenerationError(f"Groq request failed: {body[:300]}") from exc
        except urllib.error.URLError as exc:
            raise RubricGenerationError(f"Groq unreachable: {exc.reason}") from exc
    if last_error:
        raise RubricGenerationError(f"Groq request failed: {last_error}")
    raise RubricGenerationError("Groq request failed")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug[:60] or "concept"


def _normalize_concepts(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    items = payload.get("concepts")
    if not isinstance(items, list):
        return []

    normalized: List[Dict[str, Any]] = []
    seen_names: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)

        description = str(item.get("description") or "").strip()[:400]
        try:
            weight = float(item.get("weight"))
        except (TypeError, ValueError):
            weight = 3.0
        weight = max(1.0, min(5.0, weight))

        normalized.append(
            {
                "id": _slugify(name),
                "name": name,
                "description": description,
                "weight": round(weight, 1),
            }
        )
        if len(normalized) >= 40:
            break
    return normalized


def generate_concept_rubric(pdf_text: str, subject_name: str) -> List[Dict[str, Any]]:
    if not pdf_text.strip():
        raise RubricGenerationError("No extractable text in the uploaded PDF.")

    api_key = _api_key()
    if not api_key:
        raise RubricGenerationError(
            "No LLM API key configured (set AI_API_KEY or GROQ_API_KEY in Gradex_AI_Server/app/.env)"
        )

    model = _model_name()
    last_error = "Groq response failed schema validation"
    for attempt in range(_RUBRIC_ATTEMPTS):
        try:
            content = _call_groq(pdf_text, subject_name, api_key, model)
        except RubricGenerationError as exc:
            # Groq's JSON mode intermittently rejects its own output
            # (code "json_validate_failed", often with an empty
            # failed_generation). That is transient, so it must be retried
            # like a schema miss rather than failing the upload outright —
            # previously this raise escaped the loop and only one call was
            # ever made despite the retry range.
            last_error = f"attempt {attempt + 1}: {exc}"
            if attempt + 1 < _RUBRIC_ATTEMPTS:
                time.sleep(_RUBRIC_RETRY_DELAY_S * (attempt + 1))
            continue

        parsed = _extract_json_object(content)
        concepts = _normalize_concepts(parsed)
        if concepts:
            return concepts
        last_error = f"attempt {attempt + 1}: no usable concepts in Groq response"

    raise RubricGenerationError(last_error)


# ---------------------------------------------------------------------------
# Persistence (Mongo). Uses the already-connected `db_instance.db` handle from
# core/database.py directly rather than adding a new collection attribute to
# the shared Database class, so this module stays a pure addition.
# ---------------------------------------------------------------------------


def _collection(db_instance):
    if db_instance.db is None:
        return None
    return db_instance.db["subject_rubrics"]


async def get_subject_rubric(db_instance, subject_code: str) -> Optional[Dict[str, Any]]:
    collection = _collection(db_instance)
    if collection is None:
        return None
    doc = await collection.find_one({"subject_code": subject_code})
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


async def list_subject_rubrics(db_instance) -> List[Dict[str, Any]]:
    """Summaries for the subject browser: no concepts, no extracted text.

    Both are large and unused by a list view, so they are projected away rather
    than fetched and discarded client-side.
    """
    collection = _collection(db_instance)
    if collection is None:
        raise RuntimeError("MongoDB is not connected.")

    cursor = collection.find(
        {},
        {
            "subject_code": 1,
            "subject_name": 1,
            "updated_at": 1,
            "generated_at": 1,
            "concepts": 1,
            "source_files.filename": 1,
            "source_files.uploaded_at": 1,
        },
    ).sort("updated_at", -1)

    summaries: List[Dict[str, Any]] = []
    async for doc in cursor:
        summaries.append(
            {
                "subject_code": doc.get("subject_code"),
                "subject_name": doc.get("subject_name"),
                "concept_count": len(doc.get("concepts") or []),
                "source_files": doc.get("source_files") or [],
                "updated_at": doc.get("updated_at"),
                "generated_at": doc.get("generated_at"),
            }
        )
    return summaries


MAX_UPSERT_RETRIES = 5


async def _ensure_subject_rubric_indexes(collection) -> None:
    try:
        await collection.create_index("subject_code", unique=True)
    except Exception:
        # Best-effort: a transient connectivity blip here shouldn't block a write.
        pass


async def upsert_subject_rubric(
    db_instance,
    subject_code: str,
    subject_name: str,
    filename: str,
    new_concepts: List[Dict[str, Any]],
    source_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge concepts from one uploaded file into the subject's rubric.

    Re-uploading the same filename replaces only that file's concepts;
    concepts from other files for the same subject are kept. Concepts are
    deduped by name (case-insensitive) across files, keeping the newest.

    Concurrency: two lecturers uploading different files for the same
    subject_code at the same moment is a legitimate scenario, not a misuse.
    A plain find-then-update would let one write silently clobber the other
    (confirmed by test_subject_rubric_service.py before this fix). This uses
    optimistic concurrency instead: each document carries a `version`, the
    write is conditioned on the version we read, and a version mismatch (or
    a duplicate-key on first insert) means someone else wrote first — so we
    re-read and re-merge rather than overwrite blindly, up to
    MAX_UPSERT_RETRIES times.
    """
    collection = _collection(db_instance)
    if collection is None:
        raise RuntimeError("MongoDB is not connected.")

    await _ensure_subject_rubric_indexes(collection)

    for _attempt in range(MAX_UPSERT_RETRIES):
        now = datetime.now(timezone.utc)
        tagged = [{**concept, "source_file": filename} for concept in new_concepts]
        existing = await collection.find_one({"subject_code": subject_code})

        # The PDF itself is discarded after extraction, so the extracted text is
        # kept here as the only record of what the AI actually read. Capped so a
        # large deck cannot push the document toward Mongo's 16MB limit.
        file_entry: Dict[str, Any] = {"filename": filename, "uploaded_at": now}
        if source_text:
            file_entry["extracted_text"] = source_text[:_MAX_STORED_TEXT_CHARS]
            file_entry["extracted_chars"] = len(source_text)

        if existing is None:
            doc = {
                "subject_code": subject_code,
                "subject_name": subject_name or subject_code,
                "source_files": [file_entry],
                "concepts": tagged,
                "generated_at": now,
                "updated_at": now,
                "version": 1,
            }
            try:
                await collection.insert_one(doc)
                return await get_subject_rubric(db_instance, subject_code)
            except DuplicateKeyError:
                # Someone else created the document between our find_one and
                # insert_one — retry as a merge against what they just wrote.
                continue

        kept = [
            c for c in (existing.get("concepts") or []) if c.get("source_file") != filename
        ]
        merged_by_name: Dict[str, Dict[str, Any]] = {c["name"].lower(): c for c in kept}
        for concept in tagged:
            merged_by_name[concept["name"].lower()] = concept
        merged_concepts = list(merged_by_name.values())

        source_files = [
            f for f in (existing.get("source_files") or []) if f.get("filename") != filename
        ]
        source_files.append(file_entry)

        current_version = existing.get("version", 0)
        result = await collection.update_one(
            {"subject_code": subject_code, "version": current_version},
            {
                "$set": {
                    "subject_code": subject_code,
                    "subject_name": subject_name or existing.get("subject_name") or subject_code,
                    "source_files": source_files,
                    "concepts": merged_concepts,
                    "updated_at": now,
                    "version": current_version + 1,
                }
            },
        )
        if result.matched_count == 1:
            return await get_subject_rubric(db_instance, subject_code)
        # Version mismatch: someone else updated between our read and write. Retry.

    raise RuntimeError(
        f"Could not save subject rubric for {subject_code!r} after {MAX_UPSERT_RETRIES} "
        "retries — too many concurrent uploads for the same subject. Try again."
    )


async def replace_subject_rubric(
    db_instance, subject_code: str, subject_name: str, concepts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Full replace, used by the lecturer-edit endpoint (PUT)."""
    collection = _collection(db_instance)
    if collection is None:
        raise RuntimeError("MongoDB is not connected.")

    now = datetime.now(timezone.utc)

    # The PUT payload model carries no source_file, so an edited concept would
    # come back unattributed. That tag is what lets upsert_subject_rubric
    # replace only one file's concepts on re-upload — dropping it orphans every
    # edited concept, and re-uploading the same PDF then duplicates rather than
    # replaces them. Carry the existing tag over by concept id, falling back to
    # name for a concept the lecturer renamed.
    existing = await collection.find_one({"subject_code": subject_code})
    previous = (existing or {}).get("concepts") or []
    source_by_id = {c.get("id"): c.get("source_file") for c in previous if c.get("source_file")}
    source_by_name = {
        str(c.get("name", "")).lower(): c.get("source_file")
        for c in previous
        if c.get("source_file")
    }

    merged: List[Dict[str, Any]] = []
    for concept in concepts:
        entry = dict(concept)
        source = source_by_id.get(entry.get("id")) or source_by_name.get(
            str(entry.get("name", "")).lower()
        )
        if source:
            entry["source_file"] = source
        merged.append(entry)

    await collection.update_one(
        {"subject_code": subject_code},
        {
            "$set": {
                "subject_code": subject_code,
                "subject_name": subject_name,
                "concepts": merged,
                "updated_at": now,
            },
            "$setOnInsert": {"generated_at": now, "source_files": []},
        },
        upsert=True,
    )
    return await get_subject_rubric(db_instance, subject_code)
