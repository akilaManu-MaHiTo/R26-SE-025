"""Load app/sample_data/sample_data_v3 into the local gradev3 MongoDB database.

Run from the repository root:
    python load_sample_v3.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient


SAMPLE_DIR = Path(__file__).resolve().parent / "app" / "sample_data" / "sample_data_v3"
MONGODB_URI = "mongodb://127.0.0.1:27017"
DATABASE_NAME = "gradev3"
COLLECTION_FILES = {
    "courses": SAMPLE_DIR / "courses" / "courses.json",
    "rubricCollection": SAMPLE_DIR / "rubricCollection" / "rubricCollection.json",
    "submissions": SAMPLE_DIR / "submissions" / "submissions.json",
    "diagram_evaluation": SAMPLE_DIR / "diagram_evaluation" / "diagram_evaluation.json",
    "diagram_marking": SAMPLE_DIR / "diagram_marking" / "diagram_marking.json",
}


def convert_extended_json(value):
    """Convert the Extended JSON values used by the sample files to BSON values."""
    if isinstance(value, dict):
        if set(value) == {"$oid"}:
            return ObjectId(value["$oid"])
        if set(value) == {"$date"}:
            date_text = value["$date"]
            if date_text.endswith("Z"):
                date_text = date_text[:-1] + "+00:00"
            return datetime.fromisoformat(date_text)
        return {key: convert_extended_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [convert_extended_json(item) for item in value]
    return value


def load_documents(path: Path) -> list[dict]:
    documents = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(documents, dict):
        documents = [documents]
    if not isinstance(documents, list) or not all(isinstance(doc, dict) for doc in documents):
        raise ValueError(f"{path} must contain a JSON document or an array of documents")
    return [convert_extended_json(document) for document in documents]


def main() -> None:
    missing = [str(path) for path in COLLECTION_FILES.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing sample file(s): " + ", ".join(missing))

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5_000)
    client.admin.command("ping")
    database = client[DATABASE_NAME]

    for collection_name, path in COLLECTION_FILES.items():
        documents = load_documents(path)
        collection = database[collection_name]
        collection.drop()
        if documents:
            collection.insert_many(documents)
        print(f"{collection_name}: inserted {len(documents)} documents")

    print(f"Loaded sample_data_v3 into MongoDB database '{DATABASE_NAME}'.")
    client.close()


if __name__ == "__main__":
    main()
