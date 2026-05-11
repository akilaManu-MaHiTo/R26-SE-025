import asyncio
import os
import re

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv


def _normalize_question_no(value, fallback_idx: int) -> str:
    text = str(value or "").strip()
    if not text:
        return str(fallback_idx).zfill(2)
    match = re.search(r"(\d+)", text)
    if match:
        return match.group(1).zfill(2)
    return text


def _derive_question_text(question: dict, question_no: str) -> str:
    text = str(question.get("question_text") or question.get("question") or "").strip()
    if text:
        return text

    raw_no = str(question.get("question_no") or "").strip()
    if ":" in raw_no:
        candidate = raw_no.split(":", 1)[1].strip()
        if candidate:
            return candidate
    return f"Question {question_no}"


def _coerce_max_marks(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _normalize_criteria(raw_criteria, max_marks: float):
    if isinstance(raw_criteria, list):
        normalized = []
        total_marks = 0.0
        for item in raw_criteria:
            if isinstance(item, dict):
                point = str(
                    item.get("point")
                    or item.get("description")
                    or item.get("criterion")
                    or item.get("text")
                    or ""
                ).strip()
                marks = _coerce_max_marks(item.get("marks"))
            else:
                point = str(item).strip()
                marks = 0.0
            if not point:
                continue
            normalized.append({"point": point, "marks": marks})
            total_marks += marks
        if normalized:
            if total_marks == 0.0 and max_marks > 0:
                per_point = round(max_marks / len(normalized), 4)
                for entry in normalized:
                    entry["marks"] = per_point
            return normalized

    text = str(raw_criteria or "").strip() or "No criteria extracted"
    return [{"point": text, "marks": max_marks}]


async def main():
    load_dotenv()
    mongo_url = os.getenv("MONGODB_URL")
    db_name = os.getenv("DATABASE_NAME")
    if not mongo_url or not db_name:
        raise RuntimeError("MONGODB_URL and DATABASE_NAME must be set in .env")

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=10000)
    db = client[db_name]
    rubric_col = db["rubricCollection"]

    updated_count = 0
    async for doc in rubric_col.find({}):
        questions = doc.get("questions") or []
        if not isinstance(questions, list):
            continue

        new_questions = []
        for idx, question in enumerate(questions, start=1):
            if not isinstance(question, dict):
                continue
            max_marks = _coerce_max_marks(
                question.get("max_marks", question.get("max marks", question.get("marks")))
            )
            question_no = _normalize_question_no(question.get("question_no"), idx)
            question_text = _derive_question_text(question, question_no)
            criteria = _normalize_criteria(question.get("criteria"), max_marks)
            if max_marks == 0:
                max_marks = round(sum(_coerce_max_marks(c.get("marks")) for c in criteria), 4)

            new_questions.append(
                {
                    "question_no": question_no,
                    "question_text": question_text,
                    "criteria": criteria,
                    "max_marks": max_marks,
                }
            )

        if not new_questions:
            continue

        await rubric_col.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "questions": new_questions,
                    "schema_version": 2,
                }
            },
        )
        updated_count += 1

    client.close()
    print(f"Migration complete. Updated documents: {updated_count}")


if __name__ == "__main__":
    asyncio.run(main())
