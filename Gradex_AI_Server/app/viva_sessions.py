"""Viva sessions: the label every viva analysis is filed under.

A lecturer creates a viva (name, subject code + name, year, semester, category)
before uploading or recording anything. The category decides the assessment mode
once, so it cannot drift between uploads, and the subject code is what links a
technical viva to its concept rubric.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from Gradex_AI_Server.app.auth import require_lecturer
from Gradex_AI_Server.app.core.database import db_instance, ensure_marks_collection
from VivaEvaluationEngine.services.assessment_scoring import MODE_WITH, MODE_WITHOUT
from VivaEvaluationEngine.services.marking_scale import MARKING_SCALE, MarkingScale

router = APIRouter(prefix="/api/vivas", tags=["vivas"], dependencies=[Depends(require_lecturer)])

# Named like the other viva collections (viva_analysis_results, viva_subject_rubrics).
VIVA_COLLECTION = "viva_sessions"

CATEGORY_TECHNICAL = "technical"
CATEGORY_NON_TECHNICAL = "non_technical"

# Limits on what a lecturer can enter when creating a viva.
MAX_VIVA_NAME_LENGTH = 120
MAX_SUBJECT_CODE_LENGTH = 32
MAX_SUBJECT_NAME_LENGTH = 120
MAX_NOTES_LENGTH = 500
MIN_YEAR, MAX_YEAR = 2000, 2100
MIN_SEMESTER, MAX_SEMESTER = 1, 4
# What the official mark of a viva can be out of (the lecturer chooses it per viva).
MAX_VIVA_TOTAL_MARKS = 1000

# Page size for the viva list.
MAX_LIST_LIMIT = 200


async def ensure_no_duplicate_mark(viva_id: str, student_id: str, allow_duplicate: bool) -> None:
    """409 when the student already has a mark under this viva, unless the examiner confirmed."""
    marks_col = db_instance.marks_col
    if allow_duplicate or marks_col is None:
        return
    existing = await marks_col.find_one({"viva_id": viva_id, "student_id": student_id})
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"{student_id} already has a mark under this viva. Confirm to add another.",
        )


_indexes_ready = False


async def _ensure_indexes(col) -> None:
    """One viva per lecturer, name, subject, year and semester — enforced by the database."""
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        await col.create_index(
            [("examiner_email", 1), ("name_key", 1), ("subject_code", 1), ("year", 1), ("semester", 1)],
            unique=True,
            name="uniq_viva",
        )
        _indexes_ready = True
    except Exception as exc:  # noqa: BLE001 - the explicit check below still guards duplicates
        print(f"[VIVA] Warning: could not create the viva unique index ({type(exc).__name__})")


class CreateVivaPayload(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_VIVA_NAME_LENGTH)
    subject_code: str = Field(min_length=1, max_length=MAX_SUBJECT_CODE_LENGTH)
    subject_name: str = Field(min_length=1, max_length=MAX_SUBJECT_NAME_LENGTH)
    category: Literal["technical", "non_technical"]
    year: int = Field(ge=MIN_YEAR, le=MAX_YEAR)
    semester: int = Field(ge=MIN_SEMESTER, le=MAX_SEMESTER)
    # What this viva is marked out of. Left out, the server default (VIVA_MARK_MAX) applies.
    total_marks: Optional[float] = Field(default=None, gt=0, le=MAX_VIVA_TOTAL_MARKS)
    notes: Optional[str] = Field(default=None, max_length=MAX_NOTES_LENGTH)


def scale_for_total(total: Optional[float]) -> MarkingScale:
    """The marking scale for a viva total; the configured default when there is none."""
    return MARKING_SCALE.for_total(total)


def viva_scale(viva: Dict[str, Any]) -> MarkingScale:
    return scale_for_total(viva.get("total_marks"))


def mode_for_category(category: str) -> str:
    return MODE_WITH if category == CATEGORY_TECHNICAL else MODE_WITHOUT


def display_label(viva: Dict[str, Any]) -> str:
    """e.g. 'SE3040-ER Viva - semester 2 - 2026'."""
    return f"{viva['subject_code']}-{viva['name']} - semester {viva['semester']} - {viva['year']}"


def _examiner(request: Request) -> str:
    user = getattr(request.state, "user", None) or {}
    email = user.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Please sign in")
    return email


async def _vivas_col():
    if not await ensure_marks_collection() or db_instance.db is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is not connected. Check MONGODB_URL / DATABASE_NAME and Atlas credentials.",
        )
    return db_instance.db[VIVA_COLLECTION]


def _public(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in doc.items() if k not in {"_id", "name_key"}}
    out["viva_id"] = str(doc["_id"])
    out["label"] = display_label(doc)
    out["assessment_mode"] = mode_for_category(doc.get("category", ""))
    # Always present, so the client shows the scale the viva is really marked on.
    out["total_marks"] = viva_scale(doc).mark_max
    created = out.get("created_at")
    if isinstance(created, datetime):
        out["created_at"] = created.isoformat()
    return out


def _parse_id(viva_id: str) -> ObjectId:
    try:
        return ObjectId(viva_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid viva id.") from None


async def fetch_viva_for_analysis(viva_id: Optional[str], request: Request) -> Dict[str, Any]:
    """Resolve the viva an upload/recording is filed under.

    Analysis requires an existing viva owned by the signed-in lecturer; other
    lecturers' vivas are viewable but not writable. A technical viva also needs
    its subject's concept rubric to exist.
    """
    if not (viva_id or "").strip():
        raise HTTPException(status_code=400, detail="viva_id is required. Create a viva first.")
    col = await _vivas_col()
    doc = await col.find_one({"_id": _parse_id(viva_id.strip())})
    if not doc:
        raise HTTPException(status_code=404, detail="Viva not found.")
    if doc.get("examiner_email") != _examiner(request):
        raise HTTPException(status_code=403, detail="This viva belongs to another lecturer.")
    if doc.get("category") == CATEGORY_TECHNICAL:
        # A technical viva is scored against its subject's concept rubric, which can be
        # added right after the viva is created — but nothing is analyzed without it.
        from Gradex_AI_Server.app.subject_rubric_service import get_subject_rubric

        if not await get_subject_rubric(db_instance, doc["subject_code"]):
            raise HTTPException(
                status_code=400,
                detail=f"No subject content for {doc['subject_code']} yet. "
                "Add it in the Viva Workspace before analyzing a technical viva.",
            )
    return doc


def viva_extra_doc(viva: Dict[str, Any]) -> Dict[str, Any]:
    """Fields stamped onto every mark filed under a viva."""
    return {
        "viva_id": str(viva["_id"]),
        "viva_name": viva["name"],
        "viva_label": display_label(viva),
        "viva_category": viva["category"],
        "subject_code": viva["subject_code"],
        "subject_name": viva["subject_name"],
        "year": viva["year"],
        "semester": viva["semester"],
        # The scale this mark is given on, kept with the mark so it never changes meaning later.
        "viva_total_marks": viva_scale(viva).mark_max,
    }


@router.post("")
async def create_viva(payload: CreateVivaPayload, request: Request):
    examiner = _examiner(request)
    # Kept exactly as typed/picked: rubrics are stored and matched case-sensitively.
    code = payload.subject_code.strip()
    name = payload.name.strip()
    subject_name = payload.subject_name.strip()
    if not (code and name and subject_name):
        raise HTTPException(status_code=400, detail="Name, subject code and subject name are required.")

    col = await _vivas_col()
    await _ensure_indexes(col)
    name_key = " ".join(name.lower().split())
    duplicate = await col.find_one({
        "examiner_email": examiner,
        "name_key": name_key,
        "subject_code": code,
        "year": payload.year,
        "semester": payload.semester,
    })
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"You already created \"{name}\" for {code}, semester {payload.semester} {payload.year}.",
        )
    doc = {
        "name_key": name_key,
        "name": name,
        "subject_code": code,
        "subject_name": subject_name,
        "category": payload.category,
        "year": payload.year,
        "semester": payload.semester,
        "total_marks": payload.total_marks,
        "notes": (payload.notes or "").strip() or None,
        "examiner_email": examiner,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = await col.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="This viva already exists.") from None
    doc["_id"] = result.inserted_id
    return _public(doc)


@router.get("")
async def list_vivas(
    request: Request,
    all: bool = False,
    subject_code: Optional[str] = None,
    category: Optional[Literal["technical", "non_technical"]] = None,
    limit: int = 100,
):
    """The signed-in lecturer's vivas, or everyone's with ?all=true."""
    col = await _vivas_col()
    query: Dict[str, Any] = {}
    if not all:
        query["examiner_email"] = _examiner(request)
    if subject_code and subject_code.strip():
        query["subject_code"] = subject_code.strip()
    if category:
        query["category"] = category
    safe_limit = max(1, min(limit, MAX_LIST_LIMIT))
    docs = await col.find(query).sort("created_at", -1).limit(safe_limit).to_list(length=safe_limit)

    counts: Dict[str, Dict[str, int]] = {}
    marks_col = db_instance.marks_col
    if docs and marks_col is not None:
        ids = [str(d["_id"]) for d in docs]
        async for row in marks_col.aggregate([
            {"$match": {"viva_id": {"$in": ids}}},
            {"$group": {
                "_id": "$viva_id",
                "total": {"$sum": 1},
                "published": {"$sum": {"$cond": [{"$eq": ["$published", True]}, 1, 0]}},
            }},
        ]):
            counts[row["_id"]] = {"total": row["total"], "published": row["published"]}

    items = []
    for doc in docs:
        item = _public(doc)
        stats = counts.get(item["viva_id"], {"total": 0, "published": 0})
        item["mark_count"] = stats["total"]
        item["published_count"] = stats["published"]
        items.append(item)
    return {"items": items, "count": len(items)}


@router.get("/{viva_id}")
async def get_viva(viva_id: str):
    col = await _vivas_col()
    doc = await col.find_one({"_id": _parse_id(viva_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Viva not found.")
    return _public(doc)
