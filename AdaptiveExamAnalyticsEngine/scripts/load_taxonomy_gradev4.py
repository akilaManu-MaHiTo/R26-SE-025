"""Insert the IT2040 course taxonomy into the gradev4 database."""

import json
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
URI = "mongodb://127.0.0.1:27017"
DATABASE = "gradev4"
COURSE_CODE = "IT2040"
OUT_PATH = Path(r"C:\Users\liyan\AppData\Local\Temp\opencode\it2040_taxonomy.json")

# config/topic_taxonomy.json holds exactly the topic map (top level == topics),
# matching what app.db.repository.seed_it2040_if_empty passes as `topics`.
topics = json.loads((ROOT / "config" / "topic_taxonomy.json").read_text(encoding="utf-8"))

document = {
    "_id": ObjectId(),
    "course_code": COURSE_CODE,
    "topics": topics,
    "version": 1,
    "created_at": "2026-09-16T15:41:19.793769+00:00",
    "updated_at": "2026-09-16T15:41:19.793769+00:00",
    "updated_by": "system:seed",
    # app.db.repository.upsert_course_taxonomy always writes this key, so seed it
    # here too and keep the version history behaviour identical.
    "history": [],
}

client = MongoClient(URI, serverSelectionTimeoutMS=5_000)
client.admin.command("ping")
db = client[DATABASE]

db["course_taxonomies"].delete_many({"course_code": COURSE_CODE})
db["course_taxonomies"].insert_one(document)
print(f"inserted course_taxonomies/{COURSE_CODE} _id={document['_id']} version={document['version']}")

# Create the same unique index the app creates.
db["course_taxonomies"].create_index([("course_code", 1)], unique=True, name="uniq_course_taxonomies")

OUT_PATH.write_text(
    json.dumps(
        {
            **document,
            "_id": {"$oid": str(document["_id"])},
        },
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
client.close()
print(f"snapshot written to {OUT_PATH}")
