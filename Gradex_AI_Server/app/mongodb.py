from functools import lru_cache
from pathlib import Path
import importlib
import os
from typing import Any

from bson import ObjectId


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().with_name(".env")
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


@lru_cache(maxsize=1)
def get_mongo_client() -> Any:
    mongo_url = os.getenv("MONGODB_URL")
    if not mongo_url:
        raise RuntimeError("MONGODB_URL is not configured.")
    mongo_client_module = importlib.import_module("pymongo")
    return mongo_client_module.MongoClient(mongo_url)


@lru_cache(maxsize=1)
def get_diagram_evaluations_collection():
    client = get_mongo_client()
    database = client.get_default_database()
    if database is None:
        database = client["Grading"]
    return database["diagram_evaluations"]

@lru_cache(maxsize=1)
def get_diagram_evaluation_guidelines_collection():
    client = get_mongo_client()
    database = client.get_default_database()
    if database is None:
        database = client["Grading"]
    return database["diagram_marking"]

def insert_diagram_evaluation(record: dict) -> str:
    result = get_diagram_evaluations_collection().insert_one(record)
    return str(result.inserted_id)


def list_diagram_evaluations(limit: int = 100):
    return list(get_diagram_evaluations_collection().find().sort("created_at", -1).limit(limit))

def list_diagram_evaluation_guidelines(limit: int = 100):
    return list(get_diagram_evaluation_guidelines_collection().find().sort("created_at", -1).limit(limit))


def get_diagram_evaluation_guideline(guideline_object_id: str):
    try:
        object_id = ObjectId(guideline_object_id)
    except Exception as exc:
        raise ValueError("Invalid guideline object id.") from exc

    return get_diagram_evaluation_guidelines_collection().find_one({"_id": object_id})

def upsert_diagram_evaluation_guideline(document: dict) -> tuple[str, bool]:
    """Store a guideline document under its examCode.

    Re-uploading the same examCode replaces its criteria in place rather than
    leaving two documents the lecturer would have to choose between on the
    grading page. Returns (object_id, created).
    """
    collection = get_diagram_evaluation_guidelines_collection()
    exam_code = document["examCode"]

    existing = collection.find_one({"examCode": exam_code}, {"_id": 1, "created_at": 1})
    if existing is None:
        return str(collection.insert_one(document).inserted_id), True

    update = {key: value for key, value in document.items() if key != "created_at"}
    collection.update_one({"_id": existing["_id"]}, {"$set": update})
    return str(existing["_id"]), False


def delete_diagram_evaluation_guideline(guideline_object_id: str) -> bool:
    try:
        object_id = ObjectId(guideline_object_id)
    except Exception as exc:
        raise ValueError("Invalid guideline object id.") from exc

    return get_diagram_evaluation_guidelines_collection().delete_one({"_id": object_id}).deleted_count > 0
