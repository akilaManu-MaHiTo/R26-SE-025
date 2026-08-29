"""Load the sample_data_v2 JSON files into a new MongoDB database called gradingv2.

Run from the V2_QuestionExamPredictionEngine directory:
    python load_sample_v2.py
"""

import json
import re
from pathlib import Path

from pymongo import MongoClient

SAMPLE_DIR = Path(__file__).resolve().parent / "app" / "sample_data" / "sample_data_v2"
DB_NAME = "gradev2"
URI = "mongodb://127.0.0.1:27017"

# Map folder names -> collection names
COLLECTIONS = {
    "submissions": "submissions",
    "rubricCollection": "rubricCollection",
    "diagram_evaluation": "diagram_evaluation",
    "diagram_marking": "diagram_marking",
}


def convert_extended_json(obj):
    """Recursively convert MongoDB Extended JSON ($oid, $date) to native types."""
    if isinstance(obj, dict):
        if "$oid" in obj:
            from bson import ObjectId
            return ObjectId(obj["$oid"])
        if "$date" in obj:
            from datetime import datetime, timezone
            date_str = obj["$date"]
            # Handle ISO format with timezone
            if date_str.endswith("Z"):
                date_str = date_str[:-1] + "+00:00"
            return datetime.fromisoformat(date_str)
        return {k: convert_extended_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_extended_json(item) for item in obj]
    return obj


def main():
    client = MongoClient(URI)
    db = client[DB_NAME]

    print(f"Connected to MongoDB at {URI}")
    print(f"Target database: {DB_NAME}")

    for folder_name, collection_name in COLLECTIONS.items():
        json_path = SAMPLE_DIR / folder_name / f"{folder_name}.json"
        if not json_path.exists():
            print(f"  [SKIP] {json_path} not found")
            continue

        with open(json_path, encoding="utf-8") as f:
            documents = json.load(f)

        # Drop existing collection to start fresh
        db[collection_name].drop()

        # Convert Extended JSON to native BSON types
        docs = [convert_extended_json(doc) for doc in documents]

        if docs:
            result = db[collection_name].insert_many(docs)
            print(f"  [OK] {collection_name}: inserted {len(result.inserted_ids)} documents")
        else:
            print(f"  [EMPTY] {collection_name}: no documents to insert")

    # Print summary
    print(f"\nSummary of '{DB_NAME}' database:")
    for name in db.list_collection_names():
        count = db[name].count_documents({})
        print(f"  {name}: {count} documents")

    client.close()
    print(f"\nDone! Database '{DB_NAME}' created successfully.")


if __name__ == "__main__":
    main()
