import asyncio
import os
from datetime import datetime
from pathlib import Path

from bson import ObjectId

from app.core.database import db_instance as db
from app.services.answer_splitter import clean_ocr_transcript
from app.services.llm_service import generate_grading_report, regrade_single_question
from app.services.ocr_service import process_student_answer

OCR_PARALLELISM = max(1, int(os.getenv("OCR_PARALLELISM", "3")))


def _empty_progress(questions_total: int = 0) -> dict:
    return {
        "stage": "queued",
        "pages_done": 0,
        "pages_total": 0,
        "questions_done": 0,
        "questions_total": int(questions_total or 0),
        "current_question": None,
        "started_at": None,
        "updated_at": None,
    }


def _list_answer_files(student_folder_path: str) -> list[str]:
    files: list[str] = []
    try:
        names = sorted(os.listdir(student_folder_path))
    except OSError:
        return files
    for entry_name in names:
        lower = entry_name.lower()
        if lower.endswith((".png", ".jpg", ".jpeg", ".pdf")):
            file_path = os.path.join(student_folder_path, entry_name)
            if os.path.isfile(file_path):
                files.append(file_path)
    return files


async def _set_progress(stub_filter: dict, progress: dict) -> None:
    payload = dict(progress)
    payload["updated_at"] = datetime.utcnow().isoformat() + "Z"
    await db.submissions_col.update_one(
        stub_filter,
        {"$set": {"progress": payload, "updated_at": datetime.utcnow()}},
        upsert=False,
    )


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
        print(f"Database error fetching rubric: {e}")
        return None


def _list_paper_keys(upload_path: str, allow: set[str] | None) -> list[str]:
    keys: list[str] = []
    for paper_key in sorted(os.listdir(upload_path)):
        student_folder_path = os.path.join(upload_path, paper_key)
        if not os.path.isdir(student_folder_path):
            continue
        if paper_key.startswith(".") or paper_key.startswith("_"):
            continue
        if allow is not None and paper_key not in allow:
            continue
        keys.append(paper_key)
    return keys


async def create_batch_submission_stubs(
    upload_path: str,
    rubric_id: str,
    *,
    batch_job_id: str,
    paper_keys: list[str] | None = None,
    student_id_by_paper: dict[str, str] | None = None,
) -> list[str]:
    """
    Insert one not_started submission per paper so the dashboard can show live progress.
    Returns the paper_keys that were stubbed.
    """
    if not os.path.isdir(upload_path):
        raise Exception(f"Upload path not found: {upload_path}")

    rubric = await get_rubric_by_object_id(rubric_id)
    if not rubric:
        raise Exception("Rubric not found. Ensure the ID is correct in MongoDB.")

    session_name = (rubric.get("session_name") or "").strip()
    subject_code = (rubric.get("subject_code") or "").strip()
    subject_name = (rubric.get("subject_name") or "").strip() or subject_code

    year = rubric.get("year")
    month = rubric.get("month")
    semester = rubric.get("semester")
    try:
        year = int(year) if year is not None else None
        month = int(month) if month is not None else None
        semester = int(semester) if semester is not None else None
    except (TypeError, ValueError):
        year = month = semester = None

    max_marks_paper_total, max_marks_per_question = _marks_from_rubric_questions(rubric)
    allow = set(paper_keys) if paper_keys is not None else None
    id_map = {str(k): str(v) for k, v in (student_id_by_paper or {}).items()}
    keys = _list_paper_keys(upload_path, allow)

    if not keys:
        raise Exception("No paper folders found to grade.")

    rubric_oid = ObjectId(rubric_id)
    now = datetime.utcnow()

    # Preserve prior graded/failed papers for history — never hard-delete them.
    # Archive active finished results, then remove only unfinished stubs for these keys.
    await db.submissions_col.update_many(
        {
            "rubric_ref": rubric_oid,
            "paper_key": {"$in": keys},
            "archived_at": {"$exists": False},
            "status": {"$in": ["graded", "completed", "failed", "skipped"]},
        },
        {
            "$set": {
                "archived_at": now,
                "archived_reason": "superseded_by_new_batch",
                "updated_at": now,
            }
        },
    )
    await db.submissions_col.delete_many(
        {
            "rubric_ref": rubric_oid,
            "paper_key": {"$in": keys},
            "archived_at": {"$exists": False},
            "status": {"$in": ["not_started", "processing"]},
        }
    )

    questions_total = len(max_marks_per_question) if isinstance(max_marks_per_question, list) else 0
    docs = []
    for paper_key in keys:
        student_id = id_map.get(paper_key) or paper_key
        docs.append(
            {
                "rubric_ref": rubric_oid,
                "batch_job_id": batch_job_id,
                "session_name": session_name,
                "subject_code": subject_code,
                "subject_name": subject_name,
                "year": year,
                "month": month,
                "semester": semester,
                "student_id": student_id,
                "paper_key": paper_key,
                "max_marks_paper_total": max_marks_paper_total,
                "max_marks_per_question": max_marks_per_question,
                "raw_ocr_transcript": "",
                "evaluation": None,
                "status": "not_started",
                "error": None,
                "progress": _empty_progress(questions_total),
                "created_at": now,
                "updated_at": now,
            }
        )

    if docs:
        await db.submissions_col.insert_many(docs)
    print(f"Created {len(docs)} not_started submission stub(s) for job {batch_job_id}")
    return keys


async def run_batch_grading(
    upload_path: str,
    rubric_id: str,
    *,
    batch_job_id: str | None = None,
    paper_keys: list[str] | None = None,
    student_id_by_paper: dict[str, str] | None = None,
):
    if not os.path.isdir(upload_path):
        raise Exception(f"Upload path not found: {upload_path}")

    rubric = await get_rubric_by_object_id(rubric_id)
    if not rubric:
        raise Exception("Rubric not found. Ensure the ID is correct in MongoDB.")

    session_name = (rubric.get("session_name") or "").strip()
    subject_code = (rubric.get("subject_code") or "").strip()
    subject_name = (rubric.get("subject_name") or "").strip()
    if not subject_name and subject_code:
        course = await db.courses_col.find_one({"code": subject_code})
        if course:
            subject_name = str(course.get("name") or "").strip()
    if not subject_name:
        subject_name = subject_code

    year = rubric.get("year")
    month = rubric.get("month")
    semester = rubric.get("semester")
    try:
        year = int(year) if year is not None else None
        month = int(month) if month is not None else None
        semester = int(semester) if semester is not None else None
    except (TypeError, ValueError):
        year = month = semester = None

    max_marks_paper_total, max_marks_per_question = _marks_from_rubric_questions(rubric)
    questions_total = len(max_marks_per_question) if isinstance(max_marks_per_question, list) else 0
    allow = set(paper_keys) if paper_keys is not None else None
    id_map = {str(k): str(v) for k, v in (student_id_by_paper or {}).items()}
    keys = _list_paper_keys(upload_path, allow)
    rubric_oid = ObjectId(rubric_id)

    for paper_key in keys:
        student_folder_path = os.path.join(upload_path, paper_key)
        student_id = id_map.get(paper_key) or paper_key
        print(f"Processing paper={paper_key} as student_id={student_id}")

        stub_filter = {"rubric_ref": rubric_oid, "paper_key": paper_key}
        if batch_job_id:
            stub_filter["batch_job_id"] = batch_job_id

        started_at = datetime.utcnow().isoformat() + "Z"
        answer_files = _list_answer_files(student_folder_path)
        progress = {
            "stage": "ocr",
            "pages_done": 0,
            "pages_total": len(answer_files),
            "questions_done": 0,
            "questions_total": questions_total,
            "current_question": None,
            "started_at": started_at,
            "updated_at": started_at,
        }

        await db.submissions_col.update_one(
            stub_filter,
            {
                "$set": {
                    "status": "processing",
                    "student_id": student_id,
                    "progress": progress,
                    "updated_at": datetime.utcnow(),
                    "error": None,
                }
            },
            upsert=False,
        )

        full_transcript = ""
        try:
            page_texts = [""] * len(answer_files)
            if answer_files:
                sem = asyncio.Semaphore(OCR_PARALLELISM)
                done_count = 0
                lock = asyncio.Lock()

                async def _ocr_one(index: int, file_path: str):
                    nonlocal done_count
                    async with sem:
                        text, _ = await process_student_answer(file_path)
                    page_texts[index] = text or ""
                    async with lock:
                        done_count += 1
                        await _set_progress(
                            stub_filter,
                            {
                                **progress,
                                "stage": "ocr",
                                "pages_done": done_count,
                                "pages_total": len(answer_files),
                            },
                        )

                await asyncio.gather(
                    *[_ocr_one(i, path) for i, path in enumerate(answer_files)]
                )
                # Always concatenate every page slot in order (never drop empties silently).
                parts: list[str] = []
                for i, text in enumerate(page_texts):
                    label = f"--- Page {i + 1}: {Path(answer_files[i]).name} ---"
                    body = (text or "").strip()
                    if not body:
                        body = f"[OCR empty for {Path(answer_files[i]).name}]"
                        print(f"OCR warning: empty text for {answer_files[i]}")
                    elif body.startswith("OCR Failed:"):
                        print(f"OCR warning: {body[:160]}")
                    parts.append(f"{label}\n{body}")
                full_transcript = "\n\n".join(parts)
                print(
                    f"OCR concat for {paper_key}: {len(answer_files)} file(s), "
                    f"{len(full_transcript)} chars"
                )

            cleaned_transcript = clean_ocr_transcript(full_transcript)

            if not cleaned_transcript.strip():
                await db.submissions_col.update_one(
                    stub_filter,
                    {
                        "$set": {
                            "status": "skipped",
                            "raw_ocr_transcript": full_transcript,
                            "cleaned_ocr_transcript": cleaned_transcript,
                            "evaluation": None,
                            "error": "No text extracted from paper.",
                            "progress": {
                                **progress,
                                "stage": "done",
                                "pages_done": len(answer_files),
                                "pages_total": len(answer_files),
                                "current_question": None,
                            },
                            "updated_at": datetime.utcnow(),
                            "processed_at": datetime.utcnow(),
                        }
                    },
                )
                print(f"No text extracted for {paper_key}. Marked skipped.")
                continue

            progress = {
                **progress,
                "stage": "grading",
                "pages_done": len(answer_files),
                "pages_total": len(answer_files),
                "questions_done": 0,
                "current_question": None,
            }
            await _set_progress(stub_filter, progress)

            async def _on_question_progress(done, total, current_q):
                await _set_progress(
                    stub_filter,
                    {
                        **progress,
                        "stage": "grading",
                        "questions_done": int(done or 0),
                        "questions_total": int(total or questions_total),
                        "current_question": str(current_q) if current_q else None,
                    },
                )

            evaluation_json = await generate_grading_report(
                cleaned_transcript,
                rubric,
                on_progress=_on_question_progress,
            )
            await db.submissions_col.update_one(
                stub_filter,
                {
                    "$set": {
                        "session_name": session_name,
                        "subject_code": subject_code,
                        "subject_name": subject_name,
                        "year": year,
                        "month": month,
                        "semester": semester,
                        "student_id": student_id,
                        "paper_key": paper_key,
                        "max_marks_paper_total": max_marks_paper_total,
                        "max_marks_per_question": max_marks_per_question,
                        "raw_ocr_transcript": full_transcript,
                        "cleaned_ocr_transcript": cleaned_transcript,
                        "evaluation": evaluation_json,
                        "status": "graded",
                        "error": None,
                        "progress": {
                            "stage": "done",
                            "pages_done": len(answer_files),
                            "pages_total": len(answer_files),
                            "questions_done": questions_total,
                            "questions_total": questions_total,
                            "current_question": None,
                            "started_at": started_at,
                            "updated_at": datetime.utcnow().isoformat() + "Z",
                        },
                        "updated_at": datetime.utcnow(),
                        "processed_at": datetime.utcnow(),
                    }
                },
            )
            print(f"Grading complete for {student_id} (paper={paper_key})")
        except Exception as err:
            print(f"Grading failed for {paper_key}: {err}")
            await db.submissions_col.update_one(
                stub_filter,
                {
                    "$set": {
                        "status": "failed",
                        "error": str(err),
                        "progress": {
                            **progress,
                            "stage": "failed",
                        },
                        "updated_at": datetime.utcnow(),
                        "processed_at": datetime.utcnow(),
                    }
                },
            )


def summarize_batch_progress(docs: list[dict]) -> dict:
    total = len(docs)
    counts = {
        "not_started": 0,
        "processing": 0,
        "graded": 0,
        "failed": 0,
        "skipped": 0,
    }
    for doc in docs:
        st = str(doc.get("status") or "not_started")
        if st in counts:
            counts[st] += 1
        elif st == "completed":
            counts["graded"] += 1
        else:
            counts["failed"] += 1

    finished = counts["graded"] + counts["failed"] + counts["skipped"]
    percent = round((finished / total) * 100, 1) if total else 0.0
    running = counts["not_started"] > 0 or counts["processing"] > 0
    return {
        "total": total,
        "finished": finished,
        "percent": percent,
        "running": running,
        "counts": counts,
    }


async def list_ongoing_grading_jobs() -> list[dict]:
    """
    Sessions/jobs that still have papers queued (not_started) or in processing.
    Groups by batch_job_id when present, otherwise by rubric_ref.
    """
    active = await db.submissions_col.find(
        {
            "status": {"$in": ["processing", "not_started"]},
            "archived_at": {"$exists": False},
        },
        {
            "batch_job_id": 1,
            "rubric_ref": 1,
            "student_id": 1,
            "status": 1,
            "progress": 1,
            "updated_at": 1,
            "session_name": 1,
            "subject_code": 1,
            "subject_name": 1,
            "year": 1,
            "month": 1,
            "semester": 1,
        },
    ).to_list(length=2000)

    if not active:
        return []

    groups: dict[str, dict] = {}
    for doc in active:
        job_id = str(doc.get("batch_job_id") or "").strip()
        rubric_oid = doc.get("rubric_ref")
        rubric_id = str(rubric_oid) if rubric_oid is not None else ""
        key = f"job:{job_id}" if job_id else f"rubric:{rubric_id}"
        if key not in groups:
            groups[key] = {
                "batch_job_id": job_id or None,
                "rubric_id": rubric_id,
                "sample": doc,
            }

    items: list[dict] = []
    for group in groups.values():
        job_id = group["batch_job_id"]
        rubric_id = group["rubric_id"]
        query: dict = {"archived_at": {"$exists": False}}
        if job_id:
            query["batch_job_id"] = job_id
        elif rubric_id and ObjectId.is_valid(rubric_id):
            query["rubric_ref"] = ObjectId(rubric_id)
        else:
            continue

        docs = await db.submissions_col.find(query).to_list(length=2000)
        if not docs:
            continue

        if not any(str(d.get("status")) in {"processing", "not_started"} for d in docs):
            continue

        progress = summarize_batch_progress(docs)
        sample = group["sample"]
        meta = docs[0]
        current = next(
            (d for d in docs if str(d.get("status")) == "processing"),
            next((d for d in docs if str(d.get("status")) == "not_started"), sample),
        )
        current_progress = (
            current.get("progress") if isinstance(current.get("progress"), dict) else {}
        )

        updated_at = current.get("updated_at") or meta.get("updated_at")
        if hasattr(updated_at, "isoformat"):
            updated_at = updated_at.isoformat() + "Z"

        stage = str(current_progress.get("stage") or "").strip()
        if not stage:
            stage = "queued" if str(current.get("status")) == "not_started" else "processing"

        items.append(
            {
                "rubric_id": rubric_id or str(meta.get("rubric_ref") or ""),
                "batch_job_id": job_id,
                "session_name": str(meta.get("session_name") or "").strip() or "Grading session",
                "subject_code": str(meta.get("subject_code") or "").strip(),
                "subject_name": str(meta.get("subject_name") or "").strip(),
                "year": meta.get("year"),
                "month": meta.get("month"),
                "semester": meta.get("semester"),
                "current_student_id": str(current.get("student_id") or ""),
                "current_stage": stage,
                "progress": progress,
                "updated_at": updated_at,
            }
        )

    items.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    return items


def _transcript_for_regrade(submission: dict) -> str:
    cleaned = str(submission.get("cleaned_ocr_transcript") or "").strip()
    if cleaned:
        return cleaned
    raw = str(submission.get("raw_ocr_transcript") or "").strip()
    return clean_ocr_transcript(raw)


async def regrade_submission(submission_id: str) -> dict:
    """Re-run full AI grading for one submission using stored OCR text."""
    if not ObjectId.is_valid(submission_id):
        raise ValueError("Invalid submission ID")

    doc = await db.submissions_col.find_one({"_id": ObjectId(submission_id)})
    if not doc:
        raise ValueError("Submission not found")

    rubric_ref = doc.get("rubric_ref")
    if not rubric_ref:
        raise ValueError("Submission has no rubric reference")

    rubric = await db.rubric_col.find_one({"_id": rubric_ref})
    if not rubric:
        raise ValueError("Rubric not found")

    transcript = _transcript_for_regrade(doc)
    if not transcript:
        raise ValueError("No OCR transcript available to re-grade. Run batch grading first.")

    questions_total = len([q for q in (rubric.get("questions") or []) if isinstance(q, dict)])
    started_at = datetime.utcnow().isoformat() + "Z"
    stub_filter = {"_id": ObjectId(submission_id)}
    await db.submissions_col.update_one(
        stub_filter,
        {
            "$set": {
                "status": "processing",
                "error": None,
                "progress": {
                    "stage": "grading",
                    "pages_done": 0,
                    "pages_total": 0,
                    "questions_done": 0,
                    "questions_total": questions_total,
                    "current_question": None,
                    "started_at": started_at,
                    "updated_at": started_at,
                },
                "updated_at": datetime.utcnow(),
            }
        },
    )

    async def _on_question_progress(done, total, current_q):
        await _set_progress(
            stub_filter,
            {
                "stage": "grading",
                "pages_done": 0,
                "pages_total": 0,
                "questions_done": int(done or 0),
                "questions_total": int(total or questions_total),
                "current_question": str(current_q) if current_q else None,
                "started_at": started_at,
            },
        )

    try:
        evaluation_json = await generate_grading_report(
            transcript,
            rubric,
            on_progress=_on_question_progress,
        )
        await db.submissions_col.update_one(
            stub_filter,
            {
                "$set": {
                    "cleaned_ocr_transcript": transcript,
                    "evaluation": evaluation_json,
                    "status": "graded",
                    "error": None,
                    "progress": {
                        "stage": "done",
                        "pages_done": 0,
                        "pages_total": 0,
                        "questions_done": questions_total,
                        "questions_total": questions_total,
                        "current_question": None,
                        "started_at": started_at,
                        "updated_at": datetime.utcnow().isoformat() + "Z",
                    },
                    "updated_at": datetime.utcnow(),
                    "processed_at": datetime.utcnow(),
                }
            },
        )
    except Exception as err:
        await db.submissions_col.update_one(
            stub_filter,
            {
                "$set": {
                    "status": "failed",
                    "error": str(err),
                    "progress": {
                        "stage": "failed",
                        "questions_total": questions_total,
                        "started_at": started_at,
                        "updated_at": datetime.utcnow().isoformat() + "Z",
                    },
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        raise

    updated = await db.submissions_col.find_one(stub_filter)
    return updated or doc


async def regrade_submission_question(submission_id: str, question_no: str) -> dict:
    """Re-run AI grading for a single question on an existing submission."""
    if not ObjectId.is_valid(submission_id):
        raise ValueError("Invalid submission ID")

    doc = await db.submissions_col.find_one({"_id": ObjectId(submission_id)})
    if not doc:
        raise ValueError("Submission not found")

    rubric_ref = doc.get("rubric_ref")
    if not rubric_ref:
        raise ValueError("Submission has no rubric reference")
    rubric = await db.rubric_col.find_one({"_id": rubric_ref})
    if not rubric:
        raise ValueError("Rubric not found")

    transcript = _transcript_for_regrade(doc)
    if not transcript:
        raise ValueError("No OCR transcript available to re-grade.")

    evaluation = await regrade_single_question(
        transcript,
        rubric,
        doc.get("evaluation") if isinstance(doc.get("evaluation"), dict) else {},
        question_no,
    )
    await db.submissions_col.update_one(
        {"_id": ObjectId(submission_id)},
        {
            "$set": {
                "cleaned_ocr_transcript": transcript,
                "evaluation": evaluation,
                "status": "graded",
                "error": None,
                "updated_at": datetime.utcnow(),
                "processed_at": datetime.utcnow(),
            }
        },
    )
    updated = await db.submissions_col.find_one({"_id": ObjectId(submission_id)})
    return updated or doc

