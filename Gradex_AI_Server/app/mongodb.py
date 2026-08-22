from functools import lru_cache
from pathlib import Path
import importlib
import os
from typing import Any


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


def insert_diagram_evaluation(record: dict) -> str:
    result = get_diagram_evaluations_collection().insert_one(record)
    return str(result.inserted_id)


def list_diagram_evaluations(limit: int = 100):
    return list(get_diagram_evaluations_collection().find().sort("created_at", -1).limit(limit))