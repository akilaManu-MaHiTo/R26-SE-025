from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import os

from bson import ObjectId
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Query
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
from app.services.grading_manager import run_batch_grading
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


class RubricUpdatePayload(BaseModel):
    session_name: str | None = None
    subject_code: str | None = None
    questions: list[dict] = Field(default_factory=list)


class BatchGradePayload(BaseModel):
    upload_path: str | None = None
    batch_id: str | None = None

    @model_validator(mode="after")
    def exactly_one_batch_source(self):
        u = (self.upload_path or "").strip()
        b = (self.batch_id or "").strip()
        if bool(u) == bool(b):
            raise ValueError("Provide exactly one of upload_path or batch_id")
        return self


class SubmissionUpdatePayload(BaseModel):
    status: str | None = None
    lecturer_note: str | None = None
    evaluation: dict | None = None


class CourseCreatePayload(BaseModel):
    code: str = Field(..., min_length=1)
    name: str = Field(default="")
    description: str = Field(default="")


def _normalize_course_code(value: str) -> str:
    return " ".join((value or "").strip().upper().split())


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
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

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
            "session_name": session_name,
            "subject_code": _normalize_course_code(subject_code),
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
        update_fields["session_name"] = payload.session_name
    if payload.subject_code is not None:
        update_fields["subject_code"] = _normalize_course_code(payload.subject_code)

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
async def start_grading(rubric_id: str, payload: BatchGradePayload):
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

    try:
        await run_batch_grading(str(effective_path), rubric_id)
        return {
            "status": "success",
            "message": f"Grading complete for rubric {rubric_id}",
            "upload_path": str(effective_path),
            "batch_id": payload.batch_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/submissions")
async def list_submissions(
    rubric_id: str | None = Query(default=None),
    student_id: str | None = Query(default=None),
):
    query = {}
    if rubric_id:
        if not ObjectId.is_valid(rubric_id):
            raise HTTPException(status_code=400, detail="Invalid Rubric ID format")
        query["rubric_ref"] = ObjectId(rubric_id)
    if student_id:
        query["student_id"] = student_id

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


@app.patch("/submissions/{submission_id}")
async def update_submission(submission_id: str, payload: SubmissionUpdatePayload):
    if not ObjectId.is_valid(submission_id):
        raise HTTPException(status_code=400, detail="Invalid submission ID format")

    update_fields = {}
    if payload.status is not None:
        update_fields["status"] = payload.status
    if payload.lecturer_note is not None:
        update_fields["lecturer_note"] = payload.lecturer_note
    if payload.evaluation is not None:
        update_fields["evaluation"] = payload.evaluation

    if not update_fields:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    result = await db_instance.submissions_col.update_one(
        {"_id": ObjectId(submission_id)},
        {"$set": update_fields},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Submission not found")

    doc = await db_instance.submissions_col.find_one({"_id": ObjectId(submission_id)})
    return {"status": "success", "item": _serialize_submission_doc(doc)}