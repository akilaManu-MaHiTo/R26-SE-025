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
    "exam_drafts",
    "users",
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
    "exam_drafts": [("draft_id", 1)],
    "users": [("email", 1)],
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
    }
    if year is not None:
        query["year"] = year
    if month is not None:
        query["month"] = month
    if semester is not None:
        query["semester"] = semester
    # Try exact match with year if provided, else fallback to most recent
    if year is not None or month is not None or semester is not None:
        doc = await db["submissions"].find_one(query, sort=[("_id", -1)])
        if doc is not None:
            return doc
        # fallback without year for legacy data
        query_no_year = {k: v for k, v in query.items() if k not in ("year", "month", "semester")}
        return await db["submissions"].find_one(query_no_year, sort=[("year", -1), ("_id", -1)])
    return await db["submissions"].find_one(query, sort=[("year", -1), ("_id", -1)])


async def find_graded_submissions_for_exam(
    db: AsyncIOMotorDatabase, course_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
) -> list[dict]:
    query: dict = {"subject_code": course_code, "session_name": session_name, "status": "graded"}
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


async def list_all_exams(db: AsyncIOMotorDatabase) -> list[dict]:
    """Return a list of available exams with basic stats from rubricCollection."""
    rubrics = await db["rubricCollection"].find(
        {}, {"_id": 0, "subject_code": 1, "subject_name": 1, "session_name": 1, "year": 1, "month": 1, "semester": 1, "questions": 1}
    ).to_list(length=100)

    result = []
    for rubric in rubrics:
        course_code = rubric.get("subject_code", "")
        session_name = rubric.get("session_name", "")
        year = rubric.get("year", 0)
        subject_name = rubric.get("subject_name", "")

        submissions = await db["submissions"].find(
            {"subject_code": course_code, "session_name": session_name, "status": "graded",
             "year": year, "month": rubric.get("month", 0), "semester": rubric.get("semester", 1)},
            {"_id": 0, "evaluation.total_score": 1, "evaluation.max_score": 1, "max_marks_paper_total": 1}
        ).to_list(length=500)

        # Also count diagram evaluations for this exam
        diagram_evals = await db["diagram_evaluation"].find(
            {"subject_code": course_code, "session_name": session_name,
             "year": year, "month": rubric.get("month", 0), "semester": rubric.get("semester", 1)},
            {"_id": 0, "evaluation_result.total_score": 1, "evaluation_result.max_score": 1}
        ).to_list(length=500)

        # Merge: use submissions if available, otherwise diagram_evals
        student_count = len(submissions) if submissions else len(diagram_evals)
        avg_score = 0.0
        avg_percentage = 0.0
        highest_score = 0.0
        lowest_score = 0.0
        pass_count = 0
        total_marks = 0.0

        if submissions:
            # Text submissions — use existing logic
            pass
        elif diagram_evals:
            # Diagram-only exam: compute stats from diagram evaluations
            percentages = []
            scores = []
            for de in diagram_evals:
                ev_result = de.get("evaluation_result") or {}
                obtained = float(ev_result.get("total_score", 0))
                maximum = float(ev_result.get("max_score", 20))
                pct = (obtained / maximum * 100.0) if maximum > 0 else 0.0
                percentages.append(pct)
                scores.append(obtained)
            if percentages:
                avg_percentage = round(sum(percentages) / len(percentages), 2)
                avg_score = round(sum(scores) / len(scores), 2)
                highest_score = round(max(scores), 2)
                lowest_score = round(min(scores), 2)
                pass_count = sum(1 for p in percentages if p >= 50.0)
        elif student_count > 0:
            percentages = []
            scores = []
            for sub in submissions:
                ev = sub.get("evaluation") or {}
                obtained = ev.get("total_score") or sub.get("max_marks_paper_total") or 0.0
                maximum = ev.get("max_score") or sub.get("max_marks_paper_total") or 1.0
                obtained = float(obtained)
                maximum = float(maximum) if float(maximum) > 0 else 1.0
                pct = (obtained / maximum) * 100.0
                percentages.append(pct)
                scores.append(obtained)

            avg_percentage = round(sum(percentages) / len(percentages), 2)
            avg_score = round(sum(scores) / len(scores), 2)
            highest_score = round(max(scores), 2)
            lowest_score = round(min(scores), 2)
            pass_count = sum(1 for p in percentages if p >= 50.0)

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
                else:
                    # fallback without year/month/semester (legacy docs)
                    snap_any = await db["analytics_snapshots"].find_one(
                        {"subject_code": course_code, "session_name": session_name},
                        {"_id": 0, "generated_at": 1},
                        sort=[("_id", -1)],
                    )
                    if snap_any:
                        analyzed = True
                        analyzed_at = snap_any.get("generated_at")
                    else:
                        ea_any = await db["examAnalytics"].find_one(
                            {"subject_code": course_code, "session_name": session_name},
                            {"_id": 0, "generated_at": 1},
                            sort=[("_id", -1)],
                        )
                        if ea_any:
                            analyzed = True
                            analyzed_at = ea_any.get("generated_at")

        result.append({
            "course_code": course_code,
            "subject_name": subject_name,
            "session_name": session_name,
            "year": year,
            "month": rubric.get("month", 0),
            "semester": rubric.get("semester", 1),
            "total_marks": total_marks,
            "question_count": len(questions),
            "student_count": student_count,
            "average_score": avg_score,
            "average_percentage": avg_percentage,
            "highest_score": highest_score,
            "lowest_score": lowest_score,
            "pass_rate": round((pass_count / student_count * 100.0) if student_count > 0 else 0.0, 2),
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
    cursor = db["submissions"].find({"student_id": student_id, "status": "graded"})
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
async def find_diagram_evaluations_for_exam(
    db: AsyncIOMotorDatabase, course_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
) -> list[dict]:
    """Return all diagram_evaluation documents matching an exam."""
    query: dict = {"subject_code": course_code, "session_name": session_name}
    if year is not None:
        query["year"] = year
    if month is not None:
        query["month"] = month
    if semester is not None:
        query["semester"] = semester
    cursor = db["diagram_evaluation"].find(query)
    docs = await cursor.to_list(length=None)
    for doc in docs:
        doc.pop("_id", None)
    return docs


async def find_diagram_markings_for_exam(
    db: AsyncIOMotorDatabase, course_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
) -> list[dict]:
    """Return all diagram_marking documents matching an exam."""
    query: dict = {"subject_code": course_code, "session_name": session_name}
    if year is not None:
        query["year"] = year
    if month is not None:
        query["month"] = month
    if semester is not None:
        query["semester"] = semester
    cursor = db["diagram_marking"].find(query)
    docs = await cursor.to_list(length=None)
    for doc in docs:
        doc.pop("_id", None)
    return docs
