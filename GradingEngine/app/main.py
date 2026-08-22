from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import os

from bson import ObjectId
from fastapi import BackgroundTasks, FastAPI, UploadFile, File, HTTPException, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from app.core.database import connect_to_mongo, close_mongo_connection, db_instance
from app.services.ai_service import parse_rubric_ai, AIServiceUnavailableError
from app.services.batch_upload import (
    count_student_folders,
    extract_zip_to_batch,
    resolve_batch_directory,
    resolve_effective_batch_root,
    write_multipart_files_to_batch,
)
from app.services.ocr_service import process_student_answer
from app.services.grading_manager import (
    create_batch_submission_stubs,
    list_ongoing_grading_jobs,
    regrade_submission,
    regrade_submission_question,
    run_batch_grading,
    summarize_batch_progress,
)
from app.services.roster_service import (
    apply_manual_ids,
    effective_paper_id,
    load_id_scan,
    parse_roster_excel,
    scan_batch_student_ids,
    validate_roster_against_papers,
)
from app.services.ai_model_route import router as ai_model_router
from app.services.ingest_manager import process_and_index_lecture
from app.services.rag_service import (
    delete_all_lecture_materials_for_course,
    delete_lecture_material,
    list_indexed_lectures,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(title="Project Grading API", lifespan=lifespan)

_cors_origins = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_model_router)


ALLOWED_SESSION_NAMES = {
    "Final Examination",
    "Mid Term Examination",
    "Tutorial Examination",
    "Quiz",
}


class RubricUpdatePayload(BaseModel):
    session_name: str | None = None
    subject_code: str | None = None
    subject_name: str | None = None
    year: int | None = None
    month: int | None = None
    semester: int | None = None
    questions: list[dict] = Field(default_factory=list)


class RubricSessionPayload(BaseModel):
    session_name: str | None = None
    subject_code: str | None = None
    subject_name: str | None = None
    year: int | None = None
    month: int | None = None
    semester: int | None = None


class BatchGradePayload(BaseModel):
    upload_path: str | None = None
    batch_id: str | None = None
    # When True (default), only grade roster-matched papers and block on hard issues.
    require_roster_validation: bool = True
    # Allow grading despite missing/extra papers (still blocks duplicates/unreadable).
    allow_soft_warnings: bool = False

    @model_validator(mode="after")
    def exactly_one_batch_source(self):
        u = (self.upload_path or "").strip()
        b = (self.batch_id or "").strip()
        if bool(u) == bool(b):
            raise ValueError("Provide exactly one of upload_path or batch_id")
        return self


class ManualIdOverridesPayload(BaseModel):
    overrides: dict[str, str] = Field(default_factory=dict)


class SubmissionUpdatePayload(BaseModel):
    status: str | None = None
    lecturer_note: str | None = None
    evaluation: dict | None = None
    manual_override: bool | None = None


class CourseCreatePayload(BaseModel):
    code: str = Field(..., min_length=1)
    name: str = Field(default="")
    description: str = Field(default="")


def _normalize_course_code(value: str) -> str:
    return " ".join((value or "").strip().upper().split())


def _normalize_session_name(value: str) -> str:
    text = " ".join((value or "").strip().split())
    if text not in ALLOWED_SESSION_NAMES:
        raise HTTPException(
            status_code=400,
            detail=(
                "session_name must be one of: Final Examination, Mid Term Examination, "
                "Tutorial Examination, Quiz"
            ),
        )
    return text


def _parse_year_month_semester(
    year: str | int | None,
    month: str | int | None,
    semester: str | int | None,
) -> tuple[int, int, int]:
    try:
        y = int(year) if year is not None and str(year).strip() != "" else 0
        m = int(month) if month is not None and str(month).strip() != "" else 0
        s = int(semester) if semester is not None and str(semester).strip() != "" else 0
    except (TypeError, ValueError) as err:
        raise HTTPException(
            status_code=400, detail="year, month, and semester must be integers."
        ) from err

    if y < 2000 or y > 2100:
        raise HTTPException(status_code=400, detail="year must be between 2000 and 2100.")
    if m < 1 or m > 12:
        raise HTTPException(status_code=400, detail="month must be between 1 and 12.")
    if s not in (1, 2):
        raise HTTPException(status_code=400, detail="semester must be 1 or 2.")
    return y, m, s


async def _resolve_subject_name(subject_code: str, provided_name: str | None = None) -> str:
    name = (provided_name or "").strip()
    if name:
        return name
    course = await db_instance.courses_col.find_one({"code": subject_code})
    if course and str(course.get("name") or "").strip():
        return str(course["name"]).strip()
    return subject_code


def _serialize_course_doc(course: dict) -> dict:
    course = dict(course)
    course["_id"] = str(course["_id"])
    return course


def _serialize_rubric_doc(rubric: dict) -> dict:
    rubric = dict(rubric)
    rubric["_id"] = str(rubric["_id"])
    return rubric


def _serialize_submission_doc(submission: dict) -> dict:
    submission = dict(submission)
    submission["_id"] = str(submission["_id"])
    if isinstance(submission.get("rubric_ref"), ObjectId):
        submission["rubric_ref"] = str(submission["rubric_ref"])
    processed_at = submission.get("processed_at")
    if hasattr(processed_at, "isoformat"):
        submission["processed_at"] = processed_at.isoformat()
    return submission


@app.post("/upload-lecture-notes")
async def upload_lecture_notes(
    file: UploadFile = File(...),
    course_name: str = Form(...),
):
    lower_name = (file.filename or "").lower()
    if not file.filename or not lower_name.endswith((".pdf", ".pptx")):
        raise HTTPException(status_code=400, detail="Only PDF and PPTX files are supported.")

    temp_path = f"temp_{uuid4().hex}_{Path(file.filename).name}"
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        with open(temp_path, "wb") as buffer:
            buffer.write(file_bytes)

        indexed_items = process_and_index_lecture(temp_path, _normalize_course_code(course_name))
        if indexed_items == 0:
            raise HTTPException(
                status_code=400,
                detail="No extractable text found. Scanned/image-only pages or empty slides are skipped.",
            )

        return {
            "status": "success",
            "course_name": _normalize_course_code(course_name),
            "indexed_items": indexed_items,
            "indexed_pages": indexed_items,
            "filename": file.filename,
        }
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error during lecture notes upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/lecture-notes")
async def get_lecture_notes(course_name: str | None = Query(default=None)):
    try:
        items = list_indexed_lectures(course_name)
        return {"status": "success", "count": len(items), "items": items}
    except Exception as e:
        print(f"Error listing lecture notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/lecture-notes")
async def remove_lecture_notes(
    course_name: str = Query(...),
    filename: str = Query(...),
):
    try:
        deleted_chunks = delete_lecture_material(course_name, filename)
        if deleted_chunks == 0:
            raise HTTPException(status_code=404, detail="Lecture material not found.")
        return {
            "status": "success",
            "course_name": course_name.strip(),
            "filename": filename.strip(),
            "deleted_chunks": deleted_chunks,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting lecture notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/courses")
async def list_courses():
    docs = await db_instance.courses_col.find({}).sort("code", 1).to_list(length=500)
    return {
        "status": "success",
        "count": len(docs),
        "items": [_serialize_course_doc(doc) for doc in docs],
    }


@app.post("/courses")
async def create_course(payload: CourseCreatePayload):
    code = _normalize_course_code(payload.code)
    if not code:
        raise HTTPException(status_code=400, detail="Course code is required.")

    name = (payload.name or "").strip() or code
    description = (payload.description or "").strip()

    existing = await db_instance.courses_col.find_one({"code": code})
    if existing:
        raise HTTPException(status_code=409, detail=f"Course '{code}' already exists.")

    doc = {
        "code": code,
        "name": name,
        "description": description,
    }
    result = await db_instance.courses_col.insert_one(doc)
    created = await db_instance.courses_col.find_one({"_id": result.inserted_id})
    return {"status": "success", "item": _serialize_course_doc(created)}


@app.delete("/courses/{course_code}")
async def delete_course(
    course_code: str,
    purge_materials: bool = Query(default=True),
):
    code = _normalize_course_code(course_code)
    existing = await db_instance.courses_col.find_one({"code": code})
    if not existing:
        raise HTTPException(status_code=404, detail="Course not found.")

    await db_instance.courses_col.delete_one({"code": code})
    deleted_chunks = 0
    if purge_materials:
        # Match both stored code and any legacy casing variants via exact code used at upload.
        deleted_chunks = delete_all_lecture_materials_for_course(code)
        # Also try original casing from the document if different
        legacy = str(existing.get("code") or "").strip()
        if legacy and legacy != code:
            deleted_chunks += delete_all_lecture_materials_for_course(legacy)

    return {
        "status": "success",
        "code": code,
        "deleted_chunks": deleted_chunks,
    }


@app.get("/")
async def root():
    return {
        "message": "Project Grading Backend is Running",
        "database": "Connected to MongoDB Atlas",
        "status": "Healthy",
    }


@app.post("/upload-rubric")
async def upload_rubric(
    file: UploadFile = File(...),
    session_name: str = Form(...),
    subject_code: str = Form(...),
    subject_name: str = Form(default=""),
    year: str = Form(...),
    month: str = Form(...),
    semester: str = Form(...),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    normalized_session = _normalize_session_name(session_name)
    normalized_code = _normalize_course_code(subject_code)
    if not normalized_code:
        raise HTTPException(status_code=400, detail="subject_code is required.")
    y, m, s = _parse_year_month_semester(year, month, semester)
    resolved_name = await _resolve_subject_name(normalized_code, subject_name)

    temp_path = f"temp_{uuid4().hex}_{Path(file.filename).name}"

    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

        with open(temp_path, "wb") as buffer:
            buffer.write(file_bytes)

        structured_data = await parse_rubric_ai(temp_path)
        if not structured_data:
            raise HTTPException(status_code=500, detail="AI failed to parse the rubric structure.")

        rubric_document = {
            "session_name": normalized_session,
            "subject_code": normalized_code,
            "subject_name": resolved_name,
            "year": y,
            "month": m,
            "semester": s,
            "filename": file.filename,
            "parsed_at": os.path.getmtime(temp_path),
            "questions": structured_data,
        }

        result = await db_instance.rubric_col.insert_one(rubric_document)

        return {
            "status": "success",
            "mongodb_id": str(result.inserted_id),
            "extracted_questions_count": len(structured_data),
            "preview": structured_data,
            "item": _serialize_rubric_doc({**rubric_document, "_id": result.inserted_id}),
        }
    except HTTPException:
        raise
    except AIServiceUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        print(f"Error during rubric upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/rubric/{rubric_id}")
async def get_rubric(rubric_id: str):
    if not ObjectId.is_valid(rubric_id):
        raise HTTPException(status_code=400, detail="Invalid Rubric ID format")

    rubric = await db_instance.rubric_col.find_one({"_id": ObjectId(rubric_id)})
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")

    return _serialize_rubric_doc(rubric)


@app.get("/rubrics")
async def list_rubrics(
    session_name: str | None = Query(default=None),
    subject_code: str | None = Query(default=None),
):
    query = {}
    if session_name:
        query["session_name"] = session_name
    if subject_code:
        query["subject_code"] = subject_code

    docs = await db_instance.rubric_col.find(query).sort("parsed_at", -1).to_list(length=200)
    return {"status": "success", "count": len(docs), "items": [_serialize_rubric_doc(doc) for doc in docs]}


def _history_date_str(value) -> str | None:
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    if isinstance(value, (int, float)):
        from datetime import datetime as _dt

        try:
            return _dt.utcfromtimestamp(value).date().isoformat()
        except (OSError, OverflowError, ValueError):
            return None
    text = str(value or "").strip()
    return text[:10] if text else None


def _history_iso_ts(value) -> str | None:
    """Normalize created/updated timestamps to a sortable ISO string."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (int, float)):
        from datetime import datetime as _dt

        try:
            return _dt.utcfromtimestamp(value).isoformat() + "Z"
        except (OSError, OverflowError, ValueError):
            return None
    text = str(value).strip()
    return text or None


def _history_item_from_subs(rubric: dict, batch_job_id: str | None, subs: list[dict]) -> dict:
    counts = {
        "not_started": 0,
        "processing": 0,
        "graded": 0,
        "failed": 0,
        "skipped": 0,
    }
    score_pcts: list[float] = []
    archived = False
    latest_ts = None
    for doc in subs:
        if doc.get("archived_at") is not None:
            archived = True
        for ts_key in ("updated_at", "created_at", "processed_at", "archived_at"):
            ts = doc.get(ts_key)
            if ts is None:
                continue
            try:
                if latest_ts is None or ts > latest_ts:
                    latest_ts = ts
            except TypeError:
                continue
        st = str(doc.get("status") or "not_started")
        if st == "completed":
            st = "graded"
        if st in counts:
            counts[st] += 1
        else:
            counts["failed"] += 1

        if st == "graded":
            evaluation = doc.get("evaluation") if isinstance(doc.get("evaluation"), dict) else {}
            total = evaluation.get("total_score")
            max_marks = doc.get("max_marks_paper_total")
            if max_marks is None:
                max_marks = evaluation.get("max_score")
            try:
                total_f = float(total)
                max_f = float(max_marks)
                if max_f > 0:
                    score_pcts.append((total_f / max_f) * 100.0)
            except (TypeError, ValueError):
                pass

    submission_count = len(subs)
    if archived and counts["processing"] == 0 and counts["not_started"] == 0:
        status = "Archived"
    elif counts["processing"] > 0 or counts["not_started"] > 0:
        status = "Running"
    elif submission_count == 0:
        status = "Draft"
    elif counts["failed"] > 0 or counts["skipped"] > 0:
        status = "Alerts"
    else:
        status = "Completed"

    avg_score = round(sum(score_pcts) / len(score_pcts), 1) if score_pcts else None
    sort_at = _history_iso_ts(latest_ts) or _history_iso_ts(rubric.get("parsed_at"))
    date_str = _history_date_str(latest_ts) or _history_date_str(rubric.get("parsed_at"))
    rid = str(rubric.get("_id") or "")
    job = (batch_job_id or "").strip() or None

    return {
        **_serialize_rubric_doc(rubric),
        "batch_job_id": job,
        "history_key": f"{rid}:{job or 'draft'}",
        "archived": archived,
        "submission_count": submission_count,
        "graded_count": counts["graded"],
        "counts": counts,
        "avg_score": avg_score,
        "status": status,
        "date": date_str,
        "sort_at": sort_at,
    }


@app.get("/grading-history")
async def grading_history(limit: int = Query(default=50, ge=1, le=200)):
    """
    One history row per grading batch (including archived prior runs), plus draft rubrics.
    """
    rubrics = await db_instance.rubric_col.find({}).to_list(length=500)
    rubric_by_id = {doc["_id"]: doc for doc in rubrics}

    # Projection only — avoid pulling full OCR/evaluation payloads for the history list.
    subs = await db_instance.submissions_col.find(
        {},
        {
            "rubric_ref": 1,
            "batch_job_id": 1,
            "status": 1,
            "archived_at": 1,
            "updated_at": 1,
            "created_at": 1,
            "processed_at": 1,
            "max_marks_paper_total": 1,
            "evaluation.total_score": 1,
            "evaluation.max_score": 1,
            "session_name": 1,
            "subject_code": 1,
            "subject_name": 1,
            "year": 1,
            "month": 1,
            "semester": 1,
        },
    ).to_list(length=20000)
    groups: dict[tuple, list[dict]] = {}
    rubrics_with_batches: set = set()
    for doc in subs:
        rid = doc.get("rubric_ref")
        if rid is None:
            continue
        job = str(doc.get("batch_job_id") or "").strip() or None
        key = (rid, job)
        groups.setdefault(key, []).append(doc)
        rubrics_with_batches.add(rid)

    items: list[dict] = []
    for (rid, job), group_docs in groups.items():
        rubric = rubric_by_id.get(rid)
        if not rubric:
            # Orphan submissions: still show a minimal history row.
            rubric = {
                "_id": rid,
                "session_name": group_docs[0].get("session_name") or "Unknown session",
                "subject_code": group_docs[0].get("subject_code") or "",
                "subject_name": group_docs[0].get("subject_name") or "",
                "year": group_docs[0].get("year"),
                "month": group_docs[0].get("month"),
                "semester": group_docs[0].get("semester"),
                "parsed_at": group_docs[0].get("created_at"),
            }
        items.append(_history_item_from_subs(rubric, job, group_docs))

    for rid, rubric in rubric_by_id.items():
        if rid in rubrics_with_batches:
            continue
        items.append(_history_item_from_subs(rubric, None, []))

    def _sort_key(item: dict):
        return (
            item.get("sort_at") or "",
            item.get("date") or "",
            item.get("history_key") or "",
        )

    items.sort(key=_sort_key, reverse=True)
    items = items[:limit]
    return {"status": "success", "count": len(items), "items": items}


@app.patch("/rubric/{rubric_id}/session")
async def patch_rubric_session(rubric_id: str, payload: RubricSessionPayload):
    if not ObjectId.is_valid(rubric_id):
        raise HTTPException(status_code=400, detail="Invalid Rubric ID format")

    existing = await db_instance.rubric_col.find_one({"_id": ObjectId(rubric_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Rubric not found")

    update_fields: dict = {}
    if payload.session_name is not None:
        update_fields["session_name"] = _normalize_session_name(payload.session_name)
    if payload.subject_code is not None:
        code = _normalize_course_code(payload.subject_code)
        update_fields["subject_code"] = code
        update_fields["subject_name"] = await _resolve_subject_name(
            code, payload.subject_name
        )
    elif payload.subject_name is not None:
        update_fields["subject_name"] = payload.subject_name.strip()

    if payload.year is not None or payload.month is not None or payload.semester is not None:
        y, m, s = _parse_year_month_semester(
            payload.year if payload.year is not None else existing.get("year"),
            payload.month if payload.month is not None else existing.get("month"),
            payload.semester if payload.semester is not None else existing.get("semester"),
        )
        update_fields["year"] = y
        update_fields["month"] = m
        update_fields["semester"] = s

    if not update_fields:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    await db_instance.rubric_col.update_one(
        {"_id": ObjectId(rubric_id)},
        {"$set": update_fields},
    )
    updated = await db_instance.rubric_col.find_one({"_id": ObjectId(rubric_id)})
    return {"status": "success", "item": _serialize_rubric_doc(updated)}


@app.delete("/rubric/{rubric_id}")
async def delete_rubric(
    rubric_id: str,
    purge_submissions: bool = Query(default=True),
    batch_job_id: str | None = Query(
        default=None,
        description="When set, delete only this grading batch's submissions (keep other runs).",
    ),
):
    if not ObjectId.is_valid(rubric_id):
        raise HTTPException(status_code=400, detail="Invalid Rubric ID format")

    oid = ObjectId(rubric_id)
    existing = await db_instance.rubric_col.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Rubric not found")

    deleted_subs = 0
    job = (batch_job_id or "").strip() or None
    if purge_submissions:
        query: dict = {"rubric_ref": oid}
        if job:
            query["batch_job_id"] = job
        result = await db_instance.submissions_col.delete_many(query)
        deleted_subs = int(result.deleted_count or 0)

    remaining = await db_instance.submissions_col.count_documents({"rubric_ref": oid})
    deleted_rubric = False
    # Delete the rubric only when removing the whole session, or when no batches remain.
    if not job or remaining == 0:
        await db_instance.rubric_col.delete_one({"_id": oid})
        deleted_rubric = True

    return {
        "status": "success",
        "rubric_id": rubric_id,
        "batch_job_id": job,
        "deleted_submissions": deleted_subs,
        "deleted_rubric": deleted_rubric,
    }


@app.put("/rubric/{rubric_id}")
async def update_rubric(rubric_id: str, payload: RubricUpdatePayload):
    if not ObjectId.is_valid(rubric_id):
        raise HTTPException(status_code=400, detail="Invalid Rubric ID format")
    if not payload.questions:
        raise HTTPException(status_code=400, detail="questions array is required")

    update_fields = {
        "questions": payload.questions,
    }
    if payload.session_name is not None:
        update_fields["session_name"] = _normalize_session_name(payload.session_name)
    if payload.subject_code is not None:
        code = _normalize_course_code(payload.subject_code)
        update_fields["subject_code"] = code
        update_fields["subject_name"] = await _resolve_subject_name(
            code, payload.subject_name
        )
    elif payload.subject_name is not None:
        update_fields["subject_name"] = payload.subject_name.strip()

    if payload.year is not None or payload.month is not None or payload.semester is not None:
        existing = await db_instance.rubric_col.find_one({"_id": ObjectId(rubric_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="Rubric not found")
        y, m, s = _parse_year_month_semester(
            payload.year if payload.year is not None else existing.get("year"),
            payload.month if payload.month is not None else existing.get("month"),
            payload.semester if payload.semester is not None else existing.get("semester"),
        )
        update_fields["year"] = y
        update_fields["month"] = m
        update_fields["semester"] = s

    result = await db_instance.rubric_col.update_one(
        {"_id": ObjectId(rubric_id)},
        {"$set": update_fields},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Rubric not found")

    updated = await db_instance.rubric_col.find_one({"_id": ObjectId(rubric_id)})
    return {"status": "success", "item": _serialize_rubric_doc(updated)}


@app.post("/process-answer")
async def process_answer(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required.")

    temp_name = f"temp_{uuid4().hex}_{Path(file.filename).name}"
    lower_name = file.filename.lower()
    if not (lower_name.endswith(".pdf") or lower_name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"))):
        raise HTTPException(status_code=400, detail="Only PDF or image files are supported.")

    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        with open(temp_name, "wb") as buffer:
            buffer.write(file_bytes)

        extracted_text, pages_processed = await process_student_answer(temp_name)
        if lower_name.endswith(".pdf") and pages_processed == 0:
            raise HTTPException(status_code=400, detail="PDF contains no pages.")

        return {
            "status": "success",
            "extracted_text": extracted_text,
            "dip_applied": True,
            "pages_processed": pages_processed,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during answer processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_name):
            os.remove(temp_name)


@app.post("/rubric/{rubric_id}/roster")
async def upload_exam_roster(
    rubric_id: str,
    file: UploadFile = File(...),
):
    if not ObjectId.is_valid(rubric_id):
        raise HTTPException(status_code=400, detail="Invalid Rubric ID format")
    name = (file.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Upload an Excel .xlsx roster file.")

    rubric = await db_instance.rubric_col.find_one({"_id": ObjectId(rubric_id)})
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")

    body = await file.read()
    if not body:
        raise HTTPException(status_code=400, detail="Empty Excel file.")

    try:
        roster = parse_roster_excel(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel: {e}") from e

    if not roster.get("students"):
        raise HTTPException(status_code=400, detail="No student IDs found in the Excel sheet.")

    await db_instance.rubric_col.update_one(
        {"_id": ObjectId(rubric_id)},
        {"$set": {"exam_roster": roster}},
    )
    return {
        "status": "success",
        "row_count": roster.get("row_count", 0),
        "duplicate_roster_ids": roster.get("duplicate_roster_ids") or [],
        "roster": roster,
    }


@app.get("/rubric/{rubric_id}/roster")
async def get_exam_roster(rubric_id: str):
    if not ObjectId.is_valid(rubric_id):
        raise HTTPException(status_code=400, detail="Invalid Rubric ID format")
    rubric = await db_instance.rubric_col.find_one({"_id": ObjectId(rubric_id)})
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")
    roster = rubric.get("exam_roster") or {}
    return {"status": "success", "roster": roster}


@app.post("/batches/{batch_id}/scan-ids")
async def scan_batch_ids(batch_id: str):
    try:
        batch_dir = resolve_batch_directory(batch_id.strip())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Batch not found. Upload again.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        scan = await scan_batch_student_ids(batch_dir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ID scan failed: {e}") from e

    return {"status": "success", "scan": scan}


@app.get("/batches/{batch_id}/scan-ids")
async def get_batch_id_scan(batch_id: str):
    try:
        batch_dir = resolve_batch_directory(batch_id.strip())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Batch not found. Upload again.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    root = resolve_effective_batch_root(batch_dir)
    return {"status": "success", "scan": load_id_scan(root)}


@app.patch("/batches/{batch_id}/paper-ids")
async def patch_batch_paper_ids(batch_id: str, payload: ManualIdOverridesPayload):
    try:
        batch_dir = resolve_batch_directory(batch_id.strip())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Batch not found. Upload again.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not payload.overrides:
        raise HTTPException(status_code=400, detail="overrides map is required.")

    scan = apply_manual_ids(batch_dir, payload.overrides)
    return {"status": "success", "scan": scan}


@app.post("/batches/{batch_id}/validate-roster")
async def validate_batch_roster(batch_id: str, rubric_id: str = Query(...)):
    if not ObjectId.is_valid(rubric_id):
        raise HTTPException(status_code=400, detail="Invalid Rubric ID format")

    try:
        batch_dir = resolve_batch_directory(batch_id.strip())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Batch not found. Upload again.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rubric = await db_instance.rubric_col.find_one({"_id": ObjectId(rubric_id)})
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")

    roster = rubric.get("exam_roster")
    if not roster or not roster.get("students"):
        raise HTTPException(
            status_code=400,
            detail="No exam roster on this rubric. Upload an Excel attendance sheet first.",
        )

    root = resolve_effective_batch_root(batch_dir)
    scan = load_id_scan(root)
    if not scan.get("papers"):
        raise HTTPException(
            status_code=400,
            detail="No scanned paper IDs yet. Run scan-ids first.",
        )

    report = validate_roster_against_papers(roster, scan)
    return {"status": "success", "report": report}


@app.post("/upload-student-batch/zip")
async def upload_student_batch_zip(archive: UploadFile = File(...)):
    if not archive.filename or not archive.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Expected a .zip file.")

    batch_id = uuid4().hex
    body = await archive.read()
    if not body:
        raise HTTPException(status_code=400, detail="Empty zip file.")

    try:
        batch_dir = extract_zip_to_batch(body, batch_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    effective = resolve_effective_batch_root(batch_dir)
    n = count_student_folders(effective)
    return {
        "status": "success",
        "batch_id": batch_id,
        "student_folder_count": n,
    }


@app.post("/upload-student-batch/files")
async def upload_student_batch_files(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    batch_id = uuid4().hex
    try:
        batch_dir = await write_multipart_files_to_batch(files, batch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    effective = resolve_effective_batch_root(batch_dir)
    n = count_student_folders(effective)
    return {
        "status": "success",
        "batch_id": batch_id,
        "student_folder_count": n,
    }


@app.post("/grade-batch/{rubric_id}")
async def start_grading(
    rubric_id: str,
    payload: BatchGradePayload,
    background_tasks: BackgroundTasks,
):
    if not ObjectId.is_valid(rubric_id):
        raise HTTPException(status_code=400, detail="Invalid Rubric ID format")

    if payload.batch_id:
        try:
            batch_dir = resolve_batch_directory(payload.batch_id.strip())
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Batch not found. Upload again.")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        raw_path = batch_dir
    else:
        upload_path = (payload.upload_path or "").strip()
        if not upload_path or not os.path.isdir(upload_path):
            raise HTTPException(status_code=400, detail="Invalid upload_path.")
        raw_path = Path(upload_path)

    effective_path = resolve_effective_batch_root(raw_path)

    paper_keys: list[str] | None = None
    student_id_by_paper: dict[str, str] | None = None
    validation_report = None

    if payload.require_roster_validation:
        rubric = await db_instance.rubric_col.find_one({"_id": ObjectId(rubric_id)})
        if not rubric:
            raise HTTPException(status_code=404, detail="Rubric not found")
        roster = rubric.get("exam_roster")
        if not roster or not roster.get("students"):
            raise HTTPException(
                status_code=400,
                detail="Upload an exam roster Excel before grading (or disable require_roster_validation).",
            )
        scan = load_id_scan(effective_path)
        if not scan.get("papers"):
            raise HTTPException(
                status_code=400,
                detail="Scan paper IDs before grading (POST /batches/{id}/scan-ids).",
            )
        validation_report = validate_roster_against_papers(roster, scan)
        if validation_report["hard_blockers"] > 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "Roster validation blocked grading "
                        "(duplicates or unreadable IDs). Fix them first."
                    ),
                    "report": validation_report,
                },
            )
        if validation_report["soft_warnings"] > 0 and not payload.allow_soft_warnings:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "Roster has missing/extra papers. "
                        "Set allow_soft_warnings=true to grade matched papers only."
                    ),
                    "report": validation_report,
                },
            )
        if not validation_report["matched_paper_keys"]:
            raise HTTPException(status_code=400, detail="No matched papers to grade.")

        paper_keys = list(validation_report["matched_paper_keys"])
        student_id_by_paper = {}
        for paper in scan.get("papers") or []:
            if not isinstance(paper, dict):
                continue
            key = str(paper.get("paper_key") or "")
            if key in paper_keys:
                eid = effective_paper_id(paper)
                if eid:
                    student_id_by_paper[key] = eid

    batch_job_id = uuid4().hex
    try:
        stubbed_keys = await create_batch_submission_stubs(
            str(effective_path),
            rubric_id,
            batch_job_id=batch_job_id,
            paper_keys=paper_keys,
            student_id_by_paper=student_id_by_paper,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    async def _run_job():
        try:
            await run_batch_grading(
                str(effective_path),
                rubric_id,
                batch_job_id=batch_job_id,
                paper_keys=stubbed_keys,
                student_id_by_paper=student_id_by_paper,
            )
            print(f"Background grading job {batch_job_id} finished.")
        except Exception as err:
            print(f"Background grading job {batch_job_id} failed: {err}")
            await db_instance.submissions_col.update_many(
                {
                    "batch_job_id": batch_job_id,
                    "status": {"$in": ["not_started", "processing"]},
                },
                {
                    "$set": {
                        "status": "failed",
                        "error": str(err),
                    }
                },
            )

    # In-process background job. LLM calls use asyncio.to_thread so the API loop
    # is not blocked. Later: a real queue (RQ/Celery/ARQ) and a worker process.
    background_tasks.add_task(_run_job)

    return {
        "status": "started",
        "message": f"Grading started for rubric {rubric_id}",
        "upload_path": str(effective_path),
        "batch_id": payload.batch_id,
        "batch_job_id": batch_job_id,
        "graded_paper_keys": stubbed_keys,
        "submission_count": len(stubbed_keys),
        "validation": validation_report,
    }


@app.get("/grade-batch/{rubric_id}/progress")
async def grade_batch_progress(
    rubric_id: str,
    batch_job_id: str | None = Query(default=None),
):
    if not ObjectId.is_valid(rubric_id):
        raise HTTPException(status_code=400, detail="Invalid Rubric ID format")

    query: dict = {
        "rubric_ref": ObjectId(rubric_id),
        "archived_at": {"$exists": False},
    }
    if batch_job_id:
        query["batch_job_id"] = batch_job_id.strip()
        # Specific job may be an archived prior run — include it.
        del query["archived_at"]

    docs = await db_instance.submissions_col.find(query).to_list(length=2000)
    progress = summarize_batch_progress(docs)
    return {
        "status": "success",
        "rubric_id": rubric_id,
        "batch_job_id": batch_job_id,
        "progress": progress,
    }


@app.get("/grading-jobs/ongoing")
async def grading_jobs_ongoing():
    """Sessions that still have at least one paper in ``processing``."""
    items = await list_ongoing_grading_jobs()
    return {"status": "success", "count": len(items), "items": items}


@app.get("/submissions")
async def list_submissions(
    rubric_id: str | None = Query(default=None),
    student_id: str | None = Query(default=None),
    batch_job_id: str | None = Query(default=None),
    include_archived: bool = Query(
        default=False,
        description="Include superseded (archived) submissions from prior batches.",
    ),
):
    query: dict = {}
    if rubric_id:
        if not ObjectId.is_valid(rubric_id):
            raise HTTPException(status_code=400, detail="Invalid Rubric ID format")
        query["rubric_ref"] = ObjectId(rubric_id)
    if student_id:
        query["student_id"] = student_id
    job = (batch_job_id or "").strip() or None
    if job:
        query["batch_job_id"] = job
    elif not include_archived:
        # Default dashboard view: only the live (non-archived) batch papers.
        query["archived_at"] = {"$exists": False}

    docs = await db_instance.submissions_col.find(query).sort("processed_at", -1).to_list(length=1000)
    return {"status": "success", "count": len(docs), "items": [_serialize_submission_doc(doc) for doc in docs]}


@app.get("/submissions/{submission_id}")
async def get_submission(submission_id: str):
    if not ObjectId.is_valid(submission_id):
        raise HTTPException(status_code=400, detail="Invalid submission ID format")

    doc = await db_instance.submissions_col.find_one({"_id": ObjectId(submission_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Submission not found")
    return _serialize_submission_doc(doc)


@app.post("/submissions/{submission_id}/regrade")
async def regrade_one_submission(submission_id: str):
    """Re-grade all questions for one student using stored OCR text."""
    try:
        doc = await regrade_submission(submission_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"status": "success", "item": _serialize_submission_doc(doc)}


@app.post("/submissions/{submission_id}/regrade-question")
async def regrade_one_question(
    submission_id: str,
    question_no: str = Query(..., description="Question number, e.g. 2 or 02"),
):
    """Re-grade a single question for one student."""
    try:
        doc = await regrade_submission_question(submission_id, question_no)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"status": "success", "item": _serialize_submission_doc(doc)}


@app.patch("/submissions/{submission_id}")
async def update_submission(submission_id: str, payload: SubmissionUpdatePayload):
    if not ObjectId.is_valid(submission_id):
        raise HTTPException(status_code=400, detail="Invalid submission ID format")

    existing = await db_instance.submissions_col.find_one({"_id": ObjectId(submission_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Submission not found")

    update_fields: dict = {"updated_at": datetime.utcnow()}
    if payload.status is not None:
        update_fields["status"] = payload.status
    if payload.lecturer_note is not None:
        update_fields["lecturer_note"] = payload.lecturer_note
    if payload.evaluation is not None:
        evaluation = dict(payload.evaluation)
        results = evaluation.get("results")
        max_by_q: dict[str, float] = {}
        for item in existing.get("max_marks_per_question") or []:
            if not isinstance(item, dict):
                continue
            qn = str(item.get("question_no") or "").strip()
            try:
                mm = float(item.get("max_marks") or 0)
            except (TypeError, ValueError):
                continue
            if qn:
                max_by_q[qn] = mm
                max_by_q[qn.lstrip("0") or "0"] = mm
                max_by_q[qn.zfill(2)] = mm
        if isinstance(results, list):
            existing_eval = existing.get("evaluation") if isinstance(existing.get("evaluation"), dict) else {}
            prior_rows = existing_eval.get("results") if isinstance(existing_eval.get("results"), list) else []
            prior_by_q: dict[str, dict] = {}
            for idx, prior in enumerate(prior_rows):
                if not isinstance(prior, dict):
                    continue
                qn = str(prior.get("q_no") or prior.get("question_no") or "").strip()
                if qn:
                    prior_by_q[qn] = prior
                    prior_by_q[qn.lstrip("0") or "0"] = prior
                    prior_by_q[qn.zfill(2)] = prior
                prior_by_q[f"#{idx}"] = prior

            total = 0.0
            ai_total = 0.0
            cleaned_results = []
            for idx, row in enumerate(results):
                if not isinstance(row, dict):
                    cleaned_results.append(row)
                    continue
                next_row = dict(row)
                try:
                    score = float(next_row.get("score") or 0)
                except (TypeError, ValueError):
                    score = 0.0
                if score < 0:
                    score = 0.0
                q_raw = str(next_row.get("q_no") or next_row.get("question_no") or "").strip()
                cap = max_by_q.get(q_raw)
                if cap is None and q_raw:
                    cap = max_by_q.get(q_raw.lstrip("0") or "0") or max_by_q.get(q_raw.zfill(2))
                if cap is not None and score > cap:
                    score = cap
                next_row["score"] = round(score, 4)

                # Freeze original AI score once; never overwrite on later overrides.
                prior = (
                    prior_by_q.get(q_raw)
                    or prior_by_q.get(q_raw.lstrip("0") or "0")
                    or prior_by_q.get(q_raw.zfill(2))
                    or prior_by_q.get(f"#{idx}")
                )
                ai_score = None
                if isinstance(prior, dict) and prior.get("ai_score") is not None:
                    try:
                        ai_score = float(prior.get("ai_score"))
                    except (TypeError, ValueError):
                        ai_score = None
                if ai_score is None and next_row.get("ai_score") is not None:
                    try:
                        ai_score = float(next_row.get("ai_score"))
                    except (TypeError, ValueError):
                        ai_score = None
                if ai_score is None and isinstance(prior, dict) and prior.get("score") is not None:
                    # First override: keep the previously stored (AI) score.
                    try:
                        ai_score = float(prior.get("score") or 0)
                    except (TypeError, ValueError):
                        ai_score = 0.0
                if ai_score is None:
                    ai_score = score
                if ai_score < 0:
                    ai_score = 0.0
                if cap is not None and ai_score > cap:
                    ai_score = cap
                next_row["ai_score"] = round(ai_score, 4)

                if payload.manual_override is False:
                    next_row["manually_overridden"] = False
                    # Official mark returns to frozen AI value.
                    next_row["score"] = round(ai_score, 4)
                    score = ai_score
                elif payload.manual_override is not False:
                    next_row["manually_overridden"] = True
                cleaned_results.append(next_row)
                total += score
                ai_total += ai_score
            evaluation["results"] = cleaned_results
            evaluation["total_score"] = round(total, 4)
            if existing_eval.get("ai_total_score") is not None:
                try:
                    evaluation["ai_total_score"] = round(float(existing_eval["ai_total_score"]), 4)
                except (TypeError, ValueError):
                    evaluation["ai_total_score"] = round(ai_total, 4)
            else:
                evaluation["ai_total_score"] = round(ai_total, 4)
        if payload.manual_override is False:
            evaluation["manual_override"] = False
            evaluation.pop("overridden_at", None)
        elif payload.manual_override is not False:
            evaluation["manual_override"] = True
            evaluation["overridden_at"] = datetime.utcnow().isoformat() + "Z"
        update_fields["evaluation"] = evaluation
        if payload.status is None:
            update_fields["status"] = existing.get("status") or "graded"
    if payload.manual_override is not None:
        update_fields["manual_override"] = bool(payload.manual_override)

    meaningful = {k: v for k, v in update_fields.items() if k != "updated_at"}
    if not meaningful:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    await db_instance.submissions_col.update_one(
        {"_id": ObjectId(submission_id)},
        {"$set": update_fields},
    )
    doc = await db_instance.submissions_col.find_one({"_id": ObjectId(submission_id)})
    return {"status": "success", "item": _serialize_submission_doc(doc)}