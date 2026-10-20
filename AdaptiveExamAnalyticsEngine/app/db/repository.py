import json as _json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path as _Path

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError


async def load_exam_paper_sources(db: AsyncIOMotorDatabase, exam_key: str) -> dict:
    """Read only one exam's candidates and referenced rubrics, preserving conflicts.

    Both essay-rubric spellings exist in this project/data. Read available
    collections explicitly; never rename, seed, index or repair them here.
    """
    from calendar import month_name
    from app.services.exam_paper import _identity

    sources = {name: [] for name in (
        "examkeys", "rubrics", "submissions", "diagram_evaluations", "diagram_marking")}
    sources["readStartedAt"] = datetime.now(timezone.utc).isoformat()
    exams = await db["examkeys"].find({"examKey": exam_key}).to_list(length=None)
    sources["examkeys"] = exams
    if len(exams) != 1:
        return sources
    subject, year, month, semester, session = _identity(exams[0], canonical=True)
    if None in (subject, year, month, semester, session):
        return sources
    session_names = ["Final", "Final Examination"] if session == "Final" else [session]
    metadata = {"subject_code": subject, "year": {"$in": [year, str(year)]},
                "month": {"$in": [month, str(month), month_name[month]]},
                "semester": {"$in": [semester, str(semester)]},
                "session_name": {"$in": session_names}}
    canonical_identity = {"subjectCode": subject, "examYear": {"$in": [year, str(year)]},
                          "examMonth": {"$in": [month, str(month), month_name[month]]},
                          "examSemester": {"$in": [semester, str(semester)]},
                          "session": {"$in": session_names}}
    sources["examkeys"] = await db["examkeys"].find({"$or": [
        {"examKey": exam_key}, canonical_identity]}).to_list(length=None)
    candidates = {"$or": [{"examKey": exam_key}, metadata]}
    for name in ("submissions", "diagram_evaluations"):
        sources[name] = await db[name].find(candidates, {"raw_ocr_transcript": 0}).to_list(length=None)

    def references(records, field):
        values = []
        for record in records:
            value = record.get(field)
            if value is None:
                continue
            for variant in (value, str(value)):
                if variant not in values:
                    values.append(variant)
            if ObjectId.is_valid(str(value)):
                oid = ObjectId(str(value))
                if oid not in values:
                    values.append(oid)
        return values

    rubric_refs = references(sources["submissions"], "rubric_ref")
    rubric_query = {"$or": [*candidates["$or"], {"_id": {"$in": rubric_refs}}]}
    available = await db.list_collection_names()
    for name in ("rubricCollection", "rubicCollection"):
        if name in available:
            rubrics = await db[name].find(rubric_query, {
                "exam_roster.students.name": 0, "exam_roster.students.date": 0,
            }).to_list(length=None)
            sources["rubrics"].extend({**r, "_source_collection": name} for r in rubrics)
    guideline_refs = references(sources["diagram_evaluations"], "guideline_object_id")
    if guideline_refs:
        sources["diagram_marking"] = await db["diagram_marking"].find({
            "_id": {"$in": guideline_refs},
        }).to_list(length=None)
    sources["readCompletedAt"] = datetime.now(timezone.utc).isoformat()
    return sources


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
    "exam_drafts",
    "users",
    "course_taxonomies",
)

_UNIQUE_INDEXES = {
    "question_catalog": [("course_code", 1), ("exam_id", 1), ("question_number", 1), ("part", 1)],
    "question_attempts": [
        ("analysis_run_id", 1), ("exam_id", 1), ("student_key", 1), ("question_number", 1), ("part", 1),
    ],
    "analytics_snapshots": [("subject_code", 1), ("session_name", 1), ("year", 1), ("month", 1), ("semester", 1), ("analytics_version", 1)],
    "examAnalytics": [("subject_code", 1), ("session_name", 1), ("year", 1), ("month", 1), ("semester", 1), ("analytics_version", 1)],
    "analysis_runs": [("run_id", 1)],
    "analyzedExams": [("subject_code", 1), ("session_name", 1), ("year", 1), ("month", 1), ("semester", 1)],
    "student_analytics": [
        ("student_id", 1),
        ("subject_code", 1),
        ("session_name", 1),
        ("year", 1), ("month", 1), ("semester", 1),
    ],
    "studentExamAnalysis": [
        ("student_id", 1),
        ("subject_code", 1),
        ("session_name", 1),
        ("year", 1), ("month", 1), ("semester", 1),
    ],
    "studentExamResults": [
        ("student_id", 1),
        ("subject_code", 1),
        ("session_name", 1),
        ("year", 1), ("month", 1), ("semester", 1),
    ],
    "exam_drafts": [("draft_id", 1)],
    "users": [("email", 1)],
    "course_taxonomies": [("course_code", 1)],
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
    # Extra unique index for users.student_id (separate from email)
    try:
        users_indexes = await db["users"].index_information()
        if "uniq_users_student_id" not in users_indexes:
            await db["users"].create_index([("student_id", 1)], unique=True, name="uniq_users_student_id")
        else:
            # ensure correct key
            if tuple(users_indexes["uniq_users_student_id"]["key"]) != (("student_id", 1),):
                await db["users"].drop_index("uniq_users_student_id")
                await db["users"].create_index([("student_id", 1)], unique=True, name="uniq_users_student_id")
    except Exception:
        # collection may not exist yet; ignore
        pass


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
    cursor = db["submissions"].find({"status": "graded", "archived_at": None,
                                      "archived_reason": {"$ne": "superseded_by_new_batch"}})
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
    from app.services.exam_paper import _identity

    rubric_ref = submission.get("rubric_ref")
    if rubric_ref is not None and not isinstance(rubric_ref, (str, ObjectId)):
        return None
    explicit = _is_usable_reference(rubric_ref)
    if explicit:
        references = [rubric_ref]
        if ObjectId.is_valid(str(rubric_ref)):
            references.extend([ObjectId(str(rubric_ref)), str(rubric_ref)])
        query = {"_id": {"$in": references}}
    else:
        fields = ("subject_code", "year", "month", "semester", "session_name")
        identity = _identity(submission)
        if None in identity:
            return None
        from calendar import month_name
        subject, year, month, semester, session = identity
        query = dict(zip(fields, (subject, {"$in": [year, str(year)]},
            {"$in": [month, str(month), month_name[month]]}, {"$in": [semester, str(semester)]},
            {"$in": ["Final", "Final Examination"] if session == "Final" else [session]})))
    available = await db.list_collection_names()
    candidates = []
    for name in ("rubricCollection", "rubicCollection"):
        if name in available:
            candidates.extend(await db[name].find(query).to_list(length=2))
    if len(candidates) != 1:
        return None
    rubric = candidates[0]
    expected, actual = _identity(submission), _identity(rubric)
    if any(a is not None and b is not None and a != b for a, b in zip(expected, actual)):
        return None
    if submission.get("examKey") and rubric.get("examKey") and submission["examKey"] != rubric["examKey"]:
        return None
    return rubric


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
        **{key: document.get(key) for key in ("year", "month", "semester")},
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
    year: int | None = None,
    month: int | None = None,
    semester: int | None = None,
) -> dict | None:
    filters: dict[str, object] = {"student_id": student_id}
    if course_code is not None and session_name is not None:
        filters["subject_code"] = course_code
        filters["session_name"] = session_name
    elif course_code is not None:
        filters["subject_code"] = course_code
    if year is not None:
        filters["year"] = year
    if month is not None:
        filters["month"] = month
    if semester is not None:
        filters["semester"] = semester

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
    year: int | None = None,
    month: int | None = None,
    semester: int | None = None,
) -> dict | None:
    query: dict = {
        "student_id": student_id,
        "subject_code": course_code,
        "session_name": session_name,
        "status": "graded",
        "archived_at": None,
        "archived_reason": {"$ne": "superseded_by_new_batch"},
    }
    if year is not None:
        query["year"] = year
    if month is not None:
        query["month"] = month
    if semester is not None:
        query["semester"] = semester
    documents = await db["submissions"].find(query).to_list(length=2)
    if len(documents) > 1:
        from app.ingestion.student_data import StudentDataError
        raise StudentDataError("Ambiguous active student submissions; select an exact exam and resolve duplicate attempts")
    return documents[0] if documents else None


async def find_graded_submissions_for_exam(
    db: AsyncIOMotorDatabase, course_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
) -> list[dict]:
    # Regrading archives old papers while keeping their status graded.
    query: dict = {"subject_code": course_code, "session_name": session_name, "status": "graded", "archived_at": None,
                   "archived_reason": {"$ne": "superseded_by_new_batch"}}
    if year is not None:
        query["year"] = year
    if month is not None:
        query["month"] = month
    if semester is not None:
        query["semester"] = semester
    cursor = db["submissions"].find(query)
    return await cursor.to_list(length=None)


async def upsert_exam_analytics(db: AsyncIOMotorDatabase, document: dict) -> None:
    identity = {
        "subject_code": document["subject_code"],
        "session_name": document["session_name"],
        "year": document.get("year", 0),
        "month": document.get("month", 0),
        "semester": document.get("semester", 0),
        "analytics_version": document["analytics_version"],
    }
    enriched = _with_spec_aliases(document)
    await db["analytics_snapshots"].replace_one(identity, deepcopy(enriched), upsert=True)
    # Spec collection alias: examAnalytics
    await db["examAnalytics"].replace_one(identity, deepcopy(enriched), upsert=True)


async def find_exam_analytics(
    db: AsyncIOMotorDatabase, course_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
) -> dict | None:
    query: dict = {"subject_code": course_code, "session_name": session_name}
    if year is not None:
        query["year"] = year
    if month is not None:
        query["month"] = month
    if semester is not None:
        query["semester"] = semester

    document = await db["analytics_snapshots"].find_one(query, sort=[("_id", -1)])
    if document is None:
        document = await db["examAnalytics"].find_one(query, sort=[("_id", -1)])
    if document is None:
        return None
    result = deepcopy(document)
    result.pop("_id", None)
    return _with_spec_aliases(result)


async def upsert_exam_analysis_status(db: AsyncIOMotorDatabase, document: dict) -> None:
    identity = {
        "subject_code": document["subject_code"],
        "session_name": document["session_name"],
        "year": document.get("year", 0),
        "month": document.get("month", 0),
        "semester": document.get("semester", 0),
    }
    await db["analyzedExams"].replace_one(identity, deepcopy(document), upsert=True)


async def find_exam_analysis_status(
    db: AsyncIOMotorDatabase, subject_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
) -> dict | None:
    query: dict = {"subject_code": subject_code, "session_name": session_name}
    if year is not None:
        query["year"] = year
    if month is not None:
        query["month"] = month
    if semester is not None:
        query["semester"] = semester
    document = await db["analyzedExams"].find_one(query)
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
        **{key: document.get(key) for key in ("year", "month", "semester")},
    }
    if not all(identity.get(k) for k in ("student_id", "subject_code", "session_name")):
        raise ValueError("Missing student exam result identity")
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


async def list_all_exams(db: AsyncIOMotorDatabase) -> list[dict]:
    """Return available exams using the latest uploaded rubric per examKey."""
    rubrics = await db["rubricCollection"].find(
        {}, {"_id": 1, "examKey": 1, "parsed_at": 1, "subject_code": 1, "subject_name": 1, "session_name": 1, "year": 1, "month": 1, "semester": 1, "questions": 1}
    ).to_list(length=None)
    rubrics.sort(key=lambda r: (r.get("parsed_at") or 0, str(r.get("_id", ""))), reverse=True)

    result = []
    seen_exam_keys = set()
    for rubric in rubrics:
        exam_key = rubric.get("examKey")
        if exam_key:
            if exam_key in seen_exam_keys:
                continue
            seen_exam_keys.add(exam_key)
        course_code = rubric.get("subject_code", "")
        session_name = rubric.get("session_name", "")
        year = rubric.get("year", 0)
        subject_name = rubric.get("subject_name", "")

        submissions = await db["submissions"].find(
            {"subject_code": course_code, "session_name": session_name, "status": "graded",
             "year": year, "month": rubric.get("month", 0), "semester": rubric.get("semester", 1), "archived_at": None,
             "archived_reason": {"$ne": "superseded_by_new_batch"}},
            {"_id": 0, "evaluation.total_score": 1, "evaluation.max_score": 1, "max_marks_paper_total": 1}
        ).to_list(length=500)

        diagram_evals, grading_warning = [], None
        if not submissions:
            try:
                diagram_evals = await find_diagram_evaluations_for_exam(
                    db, course_code, session_name, year, rubric.get("month", 0), rubric.get("semester", 1))
            except ValueError as exc:
                # Keep invalid grades unavailable without blocking the exam inventory.
                grading_warning = str(exc)

        # Merge: use submissions if available, otherwise diagram_evals
        student_count = len(submissions) if submissions else len(diagram_evals)
        from app.ingestion.student_data import saved_total_score
        evidence = submissions if submissions else [
            {"evaluation": de.get("evaluation_result")} for de in diagram_evals]
        valid_scores = [saved_total_score(sub) for sub in evidence]
        valid_scores = [score for score in valid_scores if score["percentage"] is not None]
        scores = [score["obtained"] for score in valid_scores]
        percentages = [score["percentage"] for score in valid_scores]
        avg_score = round(sum(scores) / len(scores), 2) if scores else None
        avg_percentage = round(sum(percentages) / len(percentages), 2) if percentages else None
        highest_score = max(scores) if scores else None
        lowest_score = min(scores) if scores else None
        pass_count = sum(p >= 50 for p in percentages)

        questions = rubric.get("questions") or []
        total_marks = sum(float(q.get("max_marks", 0)) for q in questions)

        # Check analyzed status across all analytics collections (analytics_snapshots, examAnalytics, analyzedExams)
        analyzed = False
        analyzed_at = None
        # 1) analytics_snapshots (primary)
        analytics = await db["analytics_snapshots"].find_one(
            {"subject_code": course_code, "session_name": session_name, "year": year, "month": rubric.get("month", 0), "semester": rubric.get("semester", 1)},
            {"_id": 0, "generated_at": 1, "analytics_version": 1},
            sort=[("_id", -1)],
        )
        if analytics is not None:
            analyzed = True
            analyzed_at = analytics.get("generated_at")
        else:
            # 2) examAnalytics (spec alias)
            ea = await db["examAnalytics"].find_one(
                {"subject_code": course_code, "session_name": session_name, "year": year, "month": rubric.get("month", 0), "semester": rubric.get("semester", 1)},
                {"_id": 0, "generated_at": 1},
                sort=[("_id", -1)],
            )
            if ea is not None:
                analyzed = True
                analyzed_at = ea.get("generated_at")
            else:
                # 3) analyzedExams
                ae = await db["analyzedExams"].find_one(
                    {"subject_code": course_code, "session_name": session_name, "year": year, "month": rubric.get("month", 0), "semester": rubric.get("semester", 1)},
                    {"_id": 0, "analyzed_at": 1, "generated_at": 1, "analyzed": 1},
                )
                if ae is not None and (ae.get("analyzed") == "done" or ae.get("analyzed") is True or ae.get("generated_at") or ae.get("analyzed_at")):
                    analyzed = True
                    analyzed_at = ae.get("analyzed_at") or ae.get("generated_at")

        result.append({
            "course_code": course_code,
            "subject_name": subject_name,
            "session_name": session_name,
            "year": year,
            "month": rubric.get("month", 0),
            "semester": rubric.get("semester", 1),
            "total_marks": total_marks,
            "question_count": len(questions),
            "student_count": student_count if grading_warning is None else None,
            "average_score": avg_score,
            "average_percentage": avg_percentage,
            "highest_score": highest_score,
            "lowest_score": lowest_score,
            "pass_rate": round(pass_count / len(valid_scores) * 100, 2) if valid_scores else None,
            "graded_student_count": len(valid_scores) if grading_warning is None else None,
            "grading_warning": grading_warning,
            "score_basis": "Essay" if submissions else "Diagram",
            "analyzed": analyzed,
            "analyzed_at": analyzed_at,
        })

    result.sort(key=lambda x: (x["year"], x["session_name"]), reverse=True)
    return result


# ─── Exam Drafts (ExamCreator cloud save) ─────────────────────────────
async def upsert_exam_draft(db, draft: dict) -> None:
    await db["exam_drafts"].replace_one({"draft_id": draft["draft_id"]}, deepcopy(draft), upsert=True)


async def list_exam_drafts(db, course_code: str | None = None) -> list[dict]:
    query: dict = {}
    if course_code:
        query["subject_code"] = course_code
    cursor = db["exam_drafts"].find(query, {"_id": 0}).sort("updated_at", -1)
    return await cursor.to_list(length=100)


async def find_exam_draft(db, draft_id: str) -> dict | None:
    doc = await db["exam_drafts"].find_one({"draft_id": draft_id}, {"_id": 0})
    if doc is None:
        return None
    return deepcopy(doc)


async def delete_exam_draft(db, draft_id: str) -> bool:
    res = await db["exam_drafts"].delete_one({"draft_id": draft_id})
    return res.deleted_count > 0


async def find_graded_submissions_for_student(
    db: AsyncIOMotorDatabase, student_id: str
) -> list[dict]:
    cursor = db["submissions"].find({"student_id": student_id, "status": "graded", "archived_at": None,
                                      "archived_reason": {"$ne": "superseded_by_new_batch"}})
    return await cursor.to_list(length=None)


async def list_exams_for_student(
    db: AsyncIOMotorDatabase, student_id: str
) -> list[dict]:
    submissions = await find_graded_submissions_for_student(db, student_id)
    seen: dict[tuple, dict] = {}
    for sub in submissions:
        key = (sub.get("subject_code"), sub.get("session_name"), sub.get("year"), sub.get("month"), sub.get("semester"))
        if key in seen:
            continue
        rubric = await db["rubricCollection"].find_one(
            {"subject_code": sub.get("subject_code"), "session_name": sub.get("session_name")},
            {"subject_name": 1, "year": 1, "month": 1, "semester": 1, "questions": 1},
        )
        year = sub.get("year") or (rubric or {}).get("year") or 0
        month = sub.get("month") or (rubric or {}).get("month") or 0
        semester = sub.get("semester") or (rubric or {}).get("semester") or 0
        subject_code = sub.get("subject_code")
        session_name = sub.get("session_name")
        # Check if lecturer has analyzed this exam (analyzedExams or analytics_snapshots)
        analyzed = False
        analyzed_at = None
        try:
            status = await db["analyzedExams"].find_one(
                {"subject_code": subject_code, "session_name": session_name, "year": year, "month": month, "semester": semester},
                {"analyzed": 1, "analyzed_at": 1},
            )
            if status and status.get("analyzed") == "done":
                analyzed = True
                analyzed_at = status.get("analyzed_at")
            else:
                # fallback to analytics_snapshots
                snap = await db["analytics_snapshots"].find_one(
                    {"subject_code": subject_code, "session_name": session_name, "year": year, "month": month, "semester": semester},
                    {"generated_at": 1},
                )
                if snap:
                    analyzed = True
                    analyzed_at = snap.get("generated_at")
        except Exception:
            pass
        seen[key] = {
            "subject_code": subject_code,
            "subject_name": (rubric or {}).get("subject_name") or subject_code,
            "session_name": session_name,
            "year": year,
            "month": month,
            "semester": semester,
            "question_count": len((rubric or {}).get("questions") or []),
            "analyzed": analyzed,
            "analyzed_at": analyzed_at,
        }
    # Return sorted by year/month descending (most recent first) — matches frontend expectation
    result = list(seen.values())
    result.sort(key=lambda x: (x["year"], x["month"], x["semester"]), reverse=True)
    return result


# ─── Users — student accounts provisioned on exam analysis ───────────────
async def find_user_by_email(db, email: str) -> dict | None:
    doc = await db["users"].find_one({"email": email})
    if doc is None:
        return None
    result = deepcopy(doc)
    result.pop("_id", None)
    return result


async def find_user_by_student_id(db, student_id: str) -> dict | None:
    doc = await db["users"].find_one({"student_id": student_id})
    if doc is None:
        return None
    result = deepcopy(doc)
    result.pop("_id", None)
    return result


async def upsert_user(db, doc: dict) -> None:
    await db["users"].replace_one({"email": doc["email"]}, deepcopy(doc), upsert=True)


# ─── Diagram Evaluation & Marking ────────────────────────────────────────
async def _read_diagram_evaluations(db, query):
    from calendar import month_name
    from app.services.exam_paper import _identity

    docs = await db["diagram_evaluations"].find(query).to_list(length=None)
    if not docs:
        return []
    identities = {_identity(d) for d in docs}
    if len(identities) != 1:
        raise ValueError("Ambiguous diagram exam identity; select year, month and semester")
    identity = next(iter(identities))
    keys = {d["examKey"] for d in docs if isinstance(d.get("examKey"), str) and d["examKey"]}
    if keys:
        subject, year, month, semester, session = identity
        if None in identity:
            raise ValueError("Incomplete diagram exam metadata")
        exams = await db["examkeys"].find({"subjectCode": subject, "examYear": year,
            "examMonth": month_name[month], "examSemester": semester, "session": session}).to_list(length=2)
        if len(exams) != 1 or keys != {exams[0].get("examKey")}:
            raise ValueError("Conflicting or ambiguous diagram exam key")
    students = [d.get("student_id") for d in docs]
    if any(not isinstance(s, str) or not s.strip() or s.strip().upper() == "UNKNOWN" for s in students):
        raise ValueError("Missing diagram student identity")
    if len(students) != len(set(students)):
        raise ValueError("Duplicate diagram evaluations for a student and exam")
    return docs


async def _find_diagram_guideline(db, reference):
    if not isinstance(reference, (str, ObjectId)) or not str(reference).strip():
        return None
    refs = [reference]
    if isinstance(reference, str) and ObjectId.is_valid(reference):
        refs.append(ObjectId(reference))
    elif isinstance(reference, ObjectId):
        refs.append(str(reference))
    docs = await db["diagram_marking"].find({"_id": {"$in": refs}}).to_list(length=2)
    if len(docs) > 1:
        raise ValueError("Ambiguous diagram guideline reference")
    return docs[0] if docs else None


async def find_diagram_evaluation_for_student(
    db: AsyncIOMotorDatabase, student_id: str, course_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
) -> dict | None:
    """Return one exact-exam diagram evaluation in the dashboard response format."""
    query: dict = {"student_id": student_id, "subject_code": course_code, "session_name": session_name}
    if year is not None:
        query["year"] = year
    if month is not None:
        query["month"] = month
    if semester is not None:
        query["semester"] = semester
    docs = await _read_diagram_evaluations(db, query)
    if not docs:
        return None
    from app.ingestion.diagram_data import normalize_diagram_evaluation
    doc = docs[0]
    guideline = await _find_diagram_guideline(db, doc.get("guideline_object_id"))
    doc = normalize_diagram_evaluation(doc, guideline)
    doc.pop("_id", None)
    return doc


async def find_diagram_marking_for_student(
    db: AsyncIOMotorDatabase, student_id: str, course_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
) -> dict | None:
    """Resolve the rubric through the saved evaluation, never by student metadata."""
    evaluation = await find_diagram_evaluation_for_student(db, student_id, course_code, session_name, year, month, semester)
    if evaluation is None:
        return None
    doc = await _find_diagram_guideline(db, evaluation.get("guideline_object_id"))
    if doc is not None:
        doc["_id"] = str(doc["_id"])
    return doc


async def find_diagram_evaluations_for_exam(
    db: AsyncIOMotorDatabase, course_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
) -> list[dict]:
    """Read saved diagram agent grades for the exact exam, without regrading."""
    query: dict = {"subject_code": course_code, "session_name": session_name}
    if year is not None:
        query["year"] = year
    if month is not None:
        query["month"] = month
    if semester is not None:
        query["semester"] = semester
    docs = await _read_diagram_evaluations(db, query)
    from app.ingestion.diagram_data import normalize_diagram_evaluation
    guidelines, normalized, seen = {}, [], set()
    for doc in docs:
        key = (doc.get("student_id"), str(doc.get("guideline_object_id")))
        if key in seen:
            raise ValueError("Duplicate diagram evaluation for student and rubric")
        seen.add(key)
        gid = str(doc.get("guideline_object_id"))
        if gid not in guidelines:
            guidelines[gid] = await _find_diagram_guideline(db, doc.get("guideline_object_id"))
        doc = normalize_diagram_evaluation(doc, guidelines[gid])
        doc.pop("_id", None)
        normalized.append(doc)
    return normalized


async def find_diagram_markings_for_exam(
    db: AsyncIOMotorDatabase, course_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
) -> list[dict]:
    """Return only guidelines referenced by this exam's saved evaluations."""
    evaluations = await find_diagram_evaluations_for_exam(db, course_code, session_name, year, month, semester)
    docs, seen = [], set()
    for evaluation in evaluations:
        reference = evaluation.get("guideline_object_id")
        if str(reference) not in seen:
            seen.add(str(reference))
            doc = await _find_diagram_guideline(db, reference)
            if doc is not None:
                doc["_id"] = str(doc["_id"])
                docs.append(doc)
    return docs


async def get_course_taxonomy(db, course_code: str) -> dict | None:
    course_code = course_code.strip().upper()
    doc = await db["course_taxonomies"].find_one({"course_code": course_code}, {"_id": 0})
    return doc


class TaxonomyVersionConflict(Exception):
    pass


async def upsert_course_taxonomy(db, course_code: str, topics: dict, updated_by: str = "system", expected_version: int | None = None) -> dict:
    course_code = course_code.strip().upper()
    now = datetime.now(timezone.utc).isoformat()
    existing = await db["course_taxonomies"].find_one({"course_code": course_code})
    current_version = int(existing.get("version", 0)) if existing else 0
    if expected_version is not None and current_version != expected_version:
        raise TaxonomyVersionConflict("Version conflict, refresh and retry")
    version = current_version + 1
    created_at = existing.get("created_at") if existing else now
    doc = {"course_code": course_code, "topics": topics, "version": version, "created_at": created_at, "updated_at": now, "updated_by": updated_by}
    # shortcut: embedded history shares MongoDB's 16 MB limit; split history out if it approaches that size.
    doc["history"] = list(existing.get("history", [])) if existing else []
    if existing:
        doc["history"].append({k: deepcopy(v) for k, v in existing.items() if k not in ("_id", "history")})
        query = {"course_code": course_code, "version": existing.get("version", {"$exists": False})}
        result = await db["course_taxonomies"].replace_one(query, doc)
        if not result.matched_count:
            raise TaxonomyVersionConflict("Version conflict, refresh and retry")
    else:
        try:
            await db["course_taxonomies"].insert_one({"_id": course_code, **doc})
        except DuplicateKeyError as exc:
            raise TaxonomyVersionConflict("Version conflict, refresh and retry") from exc
    await db["courses"].update_one({"code": course_code}, {"$set": {"taxonomy_version": version, "taxonomy_updated_at": now}})
    return doc


async def seed_it2040_if_empty(db) -> dict | None:
    existing = await db["course_taxonomies"].find_one({"course_code": "IT2040"})
    if existing:
        return None
    path = _Path(__file__).resolve().parents[2] / "config" / "topic_taxonomy.json"
    if not path.exists():
        path = _Path(__file__).resolve().parents[2] / "datasets" / "bloom_dataset" / "taxonomy_v2.json"
    data = _json.loads(path.read_text(encoding="utf-8"))
    try:
        return await upsert_course_taxonomy(db, "IT2040", data, updated_by="system:seed", expected_version=0)
    except TaxonomyVersionConflict:
        return await get_course_taxonomy(db, "IT2040")


async def find_taxonomy_usage_count(db, course_code: str, canonical_id: str) -> int:
    course_code = course_code.strip().upper()
    canonical_norm = canonical_id.strip().casefold() if isinstance(canonical_id, str) else ""
    docs = await db["examAnalytics"].find({"subject_code": course_code}).to_list(length=20)
    cnt = 0
    for d in docs:
        topics = d.get("canonical_topic_performance") or []
        if not isinstance(topics, list):
            continue
        for t in topics:
            if not isinstance(t, dict):
                continue
            topic_val = t.get("topic")
            if not isinstance(topic_val, str):
                continue
            if topic_val.strip().casefold() == canonical_norm:
                cnt += 1
    return cnt
