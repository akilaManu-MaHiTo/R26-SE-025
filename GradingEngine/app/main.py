from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import os

from bson import ObjectId
from fastapi import FastAPI, UploadFile, File, HTTPException, Form

from app.core.database import connect_to_mongo, close_mongo_connection, db_instance
from app.services.ai_service import parse_rubric_ai, AIServiceUnavailableError
from app.services.ocr_service import process_student_answer
from app.services.grading_manager import run_batch_grading


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(title="Project Grading API", lifespan=lifespan)


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
            "subject_code": subject_code,
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

    rubric["_id"] = str(rubric["_id"])
    return rubric


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


@app.post("/grade-batch/{rubric_id}")
async def start_grading(rubric_id: str):
    # This is where your folder is located
    upload_path = "C:/Users/harit/Desktop/grading-backend/uploads/batch_1"

    try:
        await run_batch_grading(upload_path, rubric_id)
        return {"status": "success", "message": f"Grading complete for rubric {rubric_id}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}