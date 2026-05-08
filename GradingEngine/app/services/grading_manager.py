import os
from datetime import datetime
from bson import ObjectId
from app.core.database import db_instance as db
from app.services.ocr_service import process_student_answer
from app.services.llm_service import generate_grading_report


def _coerce_max_marks(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _marks_from_rubric_questions(rubric: dict):
    """
    Full-paper total and per-question caps from rubric['questions'].
    """
    questions = rubric.get("questions") or []
    if not isinstance(questions, list):
        return 0.0, []

    per_question = []
    total = 0.0
    for idx, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            continue
        q_no = str(q.get("question_no", "") or "").strip() or str(idx)
        mm = _coerce_max_marks(
            q.get("max_marks", q.get("max marks", q.get("marks")))
        )
        per_question.append({"question_no": q_no, "max_marks": mm})
        total += mm

    return total, per_question


async def get_rubric_by_object_id(rubric_id_str: str):
    try:
        rubric = await db.rubric_col.find_one({"_id": ObjectId(rubric_id_str)})
        return rubric
    except Exception as e:
        print(f"❌ Database error fetching rubric: {e}")
        return None


async def run_batch_grading(upload_path: str, rubric_id: str):
    if not os.path.isdir(upload_path):
        raise Exception(f"Upload path not found: {upload_path}")

    # 1. Grab the rubric using the Object ID
    rubric = await get_rubric_by_object_id(rubric_id)
    if not rubric:
        raise Exception("Rubric not found. Ensure the ID is correct in MongoDB.")

    session_name = (rubric.get("session_name") or "").strip()
    subject_code = (rubric.get("subject_code") or "").strip()
    max_marks_paper_total, max_marks_per_question = _marks_from_rubric_questions(rubric)

    # 2. Loop through folders (Student IDs)
    for student_id in os.listdir(upload_path):
        student_folder_path = os.path.join(upload_path, student_id)

        if os.path.isdir(student_folder_path):
            print(f"🔄 Processing student: {student_id}")
            full_transcript = ""

            # 3. OCR each page image
            for image_name in sorted(os.listdir(student_folder_path)):
                if image_name.lower().endswith((".png", ".jpg", ".jpeg")):
                    img_path = os.path.join(student_folder_path, image_name)
                    page_text, _ = await process_student_answer(img_path)
                    full_transcript += f"\n{page_text}"

            # 4. Send transcript + rubric to LLM, then store result
            if full_transcript.strip():
                evaluation_json = await generate_grading_report(full_transcript, rubric)
                submission_document = {
                    "rubric_ref": ObjectId(rubric_id),
                    "session_name": session_name,
                    "subject_code": subject_code,
                    "student_id": student_id,
                    "max_marks_paper_total": max_marks_paper_total,
                    "max_marks_per_question": max_marks_per_question,
                    "raw_ocr_transcript": full_transcript,
                    "evaluation": evaluation_json,
                    "status": "graded",
                    "processed_at": datetime.utcnow(),
                }
                await db.submissions_col.insert_one(submission_document)
                print(f"✅ Grading complete for {student_id}")
            else:
                print(f"⚠️ No text extracted for {student_id}. Skipping LLM.")