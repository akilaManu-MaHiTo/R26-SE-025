import asyncio
import json
import sys
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.db.repository import create_indexes
from app.sample_data.loader import load_real
from app.services.analytics import run_analytics

RUN_ID = f"sample-{uuid4().hex[:6]}"


async def main(db_name: str) -> None:
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[db_name]
    await create_indexes(db)
    print(f"writing to db='{db_name}'  uri={settings.mongodb_uri}")

    course, papers, submissions = load_real()
    run = await run_analytics(
        db,
        run_id=RUN_ID,
        course=course,
        papers=papers,
        submissions=submissions,
    )
    print(f"run.status = {run.status}  run_id={RUN_ID}")
    print(f"  catalog={run.data_counts['catalog']}  attempts={run.data_counts['attempts']}")

    catalog = await db["question_catalog"].find({}).to_list(length=None)
    print("\n--- question_catalog ---")
    for doc in catalog:
        print(
            f"  {doc['exam_id']}-{doc['question_number']}{doc['part']}  "
            f"{doc['bloom_level']:10s} {doc['question_type']:15s}  "
            f"model_output={json.dumps(doc.get('model_output'))}"
        )

    snapshot = await db["analytics_snapshots"].find_one({"run_id": RUN_ID})
    print(f"\nsnapshot: students={snapshot['cohort_metrics']['student_count']} "
          f"evidence={snapshot['evidence_statuses']}")

    recs = await db["exam_recommendations"].find({"run_id": RUN_ID}).to_list(length=None)
    print(f"\n--- top recommendations ({len(recs)}) ---")
    for r in recs[:3]:
        print(f"  {r['topic']} / {r['bloom_level']} priority={r['priority_score']}")

    client.close()


if __name__ == "__main__":
    db_name = sys.argv[1] if len(sys.argv) > 1 else "dbms_analytics_test"
    asyncio.run(main(db_name))