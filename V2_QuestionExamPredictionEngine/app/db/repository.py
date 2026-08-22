from copy import deepcopy

from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTIONS = (
    "courses",
    "exams",
    "questions",
    "rubrics",
    "rubricCollection",
    "submissions",
    "student_analytics",
    "studentExamAnalysis",
    "studentExamResults",
    "question_catalog",
    "question_attempts",
    "analytics_snapshots",
    "examAnalytics",
    "exam_recommendations",
    "analysis_runs",
    "generatedQuestions",
    "analyzedExams",
)

_UNIQUE_INDEXES = {
    "question_catalog": [("course_code", 1), ("exam_id", 1), ("question_number", 1), ("part", 1)],
    "question_attempts": [
        ("analysis_run_id", 1), ("exam_id", 1), ("student_key", 1), ("question_number", 1), ("part", 1),
    ],
    "analytics_snapshots": [("subject_code", 1), ("session_name", 1), ("analytics_version", 1)],
    "examAnalytics": [("subject_code", 1), ("session_name", 1), ("analytics_version", 1)],
    "analysis_runs": [("run_id", 1)],
    "analyzedExams": [("subject_code", 1), ("session_name", 1)],
    "student_analytics": [
        ("student_id", 1),
        ("subject_code", 1),
        ("session_name", 1),
    ],
    "studentExamAnalysis": [
        ("student_id", 1),
        ("subject_code", 1),
        ("session_name", 1),
    ],
    "studentExamResults": [
        ("student_id", 1),
        ("subject_code", 1),
        ("session_name", 1),
    ],
}


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    for collection, fields in _UNIQUE_INDEXES.items():
        name = f"uniq_{collection}"
        keys = [(k, v) for k, v in fields]
        existing = await db[collection].index_information()
        current = existing.get(name)
        if current is not None:
            if tuple(current["key"]) == tuple(keys):
                continue
            await db[collection].drop_index(name)
        await db[collection].create_index(keys, unique=True, name=name)


async def upsert_catalog(db: AsyncIOMotorDatabase, doc: dict) -> None:
    filter_doc = {k: doc[k] for k in ("course_code", "exam_id", "question_number", "part")}
    await db["question_catalog"].replace_one(filter_doc, doc, upsert=True)


async def insert_attempts(db: AsyncIOMotorDatabase, docs: list[dict]) -> int:
    if not docs:
        return 0
    for doc in docs:
        filter_doc = {
            k: doc[k]
            for k in ("analysis_run_id", "exam_id", "student_key", "question_number", "part")
        }
        await db["question_attempts"].replace_one(filter_doc, doc, upsert=True)
    return len(docs)


async def find_attempts(db: AsyncIOMotorDatabase, run_id: str) -> list[dict]:
    cursor = db["question_attempts"].find({"analysis_run_id": run_id})
    return await cursor.to_list(length=None)


async def save_snapshot(db: AsyncIOMotorDatabase, doc: dict) -> None:
    filter_doc = {k: doc[k] for k in ("course_code", "exam_id", "algorithm_version")}
    await db["analytics_snapshots"].replace_one(filter_doc, doc, upsert=True)


async def save_recommendations(db: AsyncIOMotorDatabase, docs: list[dict]) -> None:
    for doc in docs:
        await db["exam_recommendations"].replace_one({"recommendation_id": doc["recommendation_id"]}, doc, upsert=True)


async def find_recommendations(db: AsyncIOMotorDatabase, run_id: str) -> list[dict]:
    cursor = db["exam_recommendations"].find({"run_id": run_id}).sort("priority_score", -1)
    return await cursor.to_list(length=None)


async def save_run(db: AsyncIOMotorDatabase, doc: dict) -> None:
    await db["analysis_runs"].replace_one({"run_id": doc["run_id"]}, doc, upsert=True)


async def find_attempts_by_student(
    db: AsyncIOMotorDatabase, run_id: str, student_key: str
) -> list[dict]:
    cursor = db["question_attempts"].find(
        {"analysis_run_id": run_id, "student_key": student_key}
    )
    return await cursor.to_list(length=None)


async def latest_run_id(db: AsyncIOMotorDatabase) -> str | None:
    doc = await db["analysis_runs"].find_one(sort=[("created_at", -1)])
    return doc["run_id"] if doc else None


async def find_graded_submissions(db: AsyncIOMotorDatabase) -> list[dict]:
    cursor = db["submissions"].find({"status": "graded"})
    return await cursor.to_list(length=None)


async def find_course_for_submission(
    db: AsyncIOMotorDatabase, submission: dict
) -> dict | None:
    course_code = submission.get("course_code") or submission.get("subject_code")
    if course_code:
        for field in ("course_code", "code"):
            course = await db["courses"].find_one({field: course_code})
            if course is not None:
                return course

    subject_code = submission.get("subject_code") or course_code
    session_name = submission.get("session_name")
    if subject_code and session_name:
        return await db["courses"].find_one(
            {"subject_code": subject_code, "session_name": session_name}
        )
    return None


def _is_usable_reference(value: object) -> bool:
    if value is None:
        return False
    if not isinstance(value, str):
        return True
    reference = value.strip()
    return bool(reference) and "..." not in reference


async def find_rubric_for_submission(
    db: AsyncIOMotorDatabase, submission: dict
) -> dict | None:
    rubric_ref = submission.get("rubric_ref")
    if _is_usable_reference(rubric_ref):
        rubric = await db["rubricCollection"].find_one({"_id": rubric_ref})
        if rubric is not None:
            return rubric

    subject_code = submission.get("subject_code") or submission.get("course_code")
    session_name = submission.get("session_name")
    if subject_code and session_name:
        return await db["rubricCollection"].find_one(
            {"subject_code": subject_code, "session_name": session_name}
        )
    return None


def _with_spec_aliases(document: dict) -> dict:
    """Return a copy enriched with spec aliases (exam_id, course, exam)."""
    enriched = deepcopy(document)
    subject_code = enriched.get("subject_code")
    subject_name = enriched.get("subject_name")
    session_name = enriched.get("session_name")
    if subject_code and "course" not in enriched:
        enriched["course"] = {"code": subject_code, "name": subject_name or subject_code}
    if subject_code and session_name and "exam_id" not in enriched:
        enriched["exam_id"] = f"{subject_code}@{session_name}"
    # exam field already present for exam analytics; ensure student docs also have exam alias
    if "exam_id" not in enriched and enriched.get("exam", {}).get("session_name"):
        enriched["exam_id"] = f"{subject_code}@{enriched['exam']['session_name']}"
    return enriched


async def upsert_student_analytics(
    db: AsyncIOMotorDatabase, document: dict
) -> None:
    identity = {
        "student_id": document["student_id"],
        "subject_code": document["subject_code"],
        "session_name": document["session_name"],
    }
    enriched = _with_spec_aliases(document)
    await db["student_analytics"].replace_one(
        identity, deepcopy(enriched), upsert=True
    )
    # Spec collection alias: studentExamAnalysis (13. Recommended)
    await db["studentExamAnalysis"].replace_one(
        identity, deepcopy(enriched), upsert=True
    )


async def find_student_analytics(
    db: AsyncIOMotorDatabase,
    student_id: str,
    course_code: str | None = None,
    session_name: str | None = None,
) -> dict | None:
    filters: dict[str, object] = {"student_id": student_id}
    if course_code is not None and session_name is not None:
        filters["subject_code"] = course_code
        filters["session_name"] = session_name
    elif course_code is not None:
        filters["subject_code"] = course_code

    document = await db["student_analytics"].find_one(
        filters, sort=[("_id", -1)]
    )
    # Fallback to spec collection name if legacy is empty (or vice versa)
    if document is None:
        document = await db["studentExamAnalysis"].find_one(
            filters, sort=[("_id", -1)]
        )
    if document is None:
        return None

    result = deepcopy(document)
    result.pop("_id", None)
    return _with_spec_aliases(result)


async def find_graded_submission(
    db: AsyncIOMotorDatabase,
    student_id: str,
    course_code: str,
    session_name: str,
) -> dict | None:
    return await db["submissions"].find_one(
        {
            "student_id": student_id,
            "subject_code": course_code,
            "session_name": session_name,
            "status": "graded",
        }
    )


async def find_graded_submissions_for_exam(
    db: AsyncIOMotorDatabase, course_code: str, session_name: str
) -> list[dict]:
    cursor = db["submissions"].find(
        {"subject_code": course_code, "session_name": session_name, "status": "graded"}
    )
    return await cursor.to_list(length=None)


async def upsert_exam_analytics(db: AsyncIOMotorDatabase, document: dict) -> None:
    identity = {
        "subject_code": document["subject_code"],
        "session_name": document["session_name"],
        "analytics_version": document["analytics_version"],
    }
    enriched = _with_spec_aliases(document)
    await db["analytics_snapshots"].replace_one(identity, deepcopy(enriched), upsert=True)
    # Spec collection alias: examAnalytics
    await db["examAnalytics"].replace_one(identity, deepcopy(enriched), upsert=True)


async def find_exam_analytics(
    db: AsyncIOMotorDatabase, course_code: str, session_name: str
) -> dict | None:
    document = await db["analytics_snapshots"].find_one(
        {"subject_code": course_code, "session_name": session_name}, sort=[("_id", -1)]
    )
    if document is None:
        document = await db["examAnalytics"].find_one(
            {"subject_code": course_code, "session_name": session_name}, sort=[("_id", -1)]
        )
    if document is None:
        return None
    result = deepcopy(document)
    result.pop("_id", None)
    return _with_spec_aliases(result)


async def upsert_exam_analysis_status(db: AsyncIOMotorDatabase, document: dict) -> None:
    identity = {
        "subject_code": document["subject_code"],
        "session_name": document["session_name"],
    }
    await db["analyzedExams"].replace_one(identity, deepcopy(document), upsert=True)


async def find_exam_analysis_status(
    db: AsyncIOMotorDatabase, subject_code: str, session_name: str
) -> dict | None:
    document = await db["analyzedExams"].find_one(
        {"subject_code": subject_code, "session_name": session_name}
    )
    if document is None:
        return None
    result = deepcopy(document)
    result.pop("_id", None)
    return result


async def upsert_generated_questions(
    db: AsyncIOMotorDatabase, document: dict
) -> None:
    identity = {
        "student_id": document["student_id"],
        "exam_id": document["exam_id"],
        "generation_version": document["generation_version"],
    }
    await db["generatedQuestions"].replace_one(
        identity, deepcopy(document), upsert=True
    )


async def find_generated_questions(
    db: AsyncIOMotorDatabase, student_id: str, exam_id: str
) -> dict | None:
    document = await db["generatedQuestions"].find_one(
        {"student_id": student_id, "exam_id": exam_id}, sort=[("_id", -1)]
    )
    if document is None:
        return None
    result = deepcopy(document)
    result.pop("_id", None)
    return result


# ─── Spec §5: studentExamResults — lightweight per-student exam summary ─────
async def upsert_student_exam_result(
    db: AsyncIOMotorDatabase, document: dict
) -> None:
    identity = {
        "student_id": document["student_id"],
        "subject_code": document.get("subject_code") or document.get("course", {}).get("code"),
        "session_name": document.get("session_name") or document.get("exam", {}).get("session_name"),
    }
    # Filter out None keys to avoid collision
    identity = {k: v for k, v in identity.items() if v}
    await db["studentExamResults"].replace_one(identity, deepcopy(document), upsert=True)


async def find_student_exam_results(
    db: AsyncIOMotorDatabase, course_code: str, session_name: str
) -> list[dict]:
    cursor = db["studentExamResults"].find(
        {"subject_code": course_code, "session_name": session_name}
    )
    docs = await cursor.to_list(length=None)
    # Fallback to legacy derived path if spec collection empty
    if docs:
        cleaned = []
        for doc in docs:
            copy = deepcopy(doc)
            copy.pop("_id", None)
            cleaned.append(copy)
        return cleaned
    return []


async def list_exams_with_status(db: AsyncIOMotorDatabase) -> list[dict]:
    cursor = db["analyzedExams"].find({}, {"_id": 0}).sort(
        [("year", -1), ("session_name", 1)]
    )
    return await cursor.to_list(length=100)
