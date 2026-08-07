from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTIONS = (
    "question_catalog",
    "question_attempts",
    "analytics_snapshots",
    "exam_recommendations",
    "analysis_runs",
)

_UNIQUE_INDEXES = {
    "question_catalog": [("course_code", 1), ("exam_id", 1), ("question_number", 1), ("part", 1)],
    "question_attempts": [
        ("analysis_run_id", 1), ("exam_id", 1), ("student_key", 1), ("question_number", 1), ("part", 1),
    ],
    "analytics_snapshots": [("course_code", 1), ("exam_id", 1), ("algorithm_version", 1)],
    "analysis_runs": [("run_id", 1)],
}


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    for collection, fields in _UNIQUE_INDEXES.items():
        await db[collection].create_index(
            [(k, v) for k, v in fields], unique=True, name=f"uniq_{collection}"
        )


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