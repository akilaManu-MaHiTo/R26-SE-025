from pathlib import Path
import os

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Unlike GradingEngine (run from its own directory), this server is run from
# the repo root (see ../main.py / ../../CLAUDE.md), so a bare load_dotenv()
# would search upward from the repo root and miss this app/.env entirely.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")


class Database:
    client: AsyncIOMotorClient = None
    db = None
    # Stores one document per completed viva analysis (see app/viva_service.py).
    marks_col = None
    last_error: str | None = None

db_instance = Database()


def _mongo_url() -> str:
    raw = (os.getenv("MONGODB_URL") or "").strip().strip('"').strip("'")
    return raw


async def connect_to_mongo():
    db_instance.client = None
    db_instance.db = None
    db_instance.marks_col = None
    db_instance.last_error = None

    url = _mongo_url()
    db_name = (os.getenv("DATABASE_NAME") or "").strip()
    if not url or not db_name:
        db_instance.last_error = "MONGODB_URL or DATABASE_NAME is missing."
        print(f"[MONGO] Skipped: {db_instance.last_error}")
        return

    try:
        db_instance.client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=10000)
        await db_instance.client.admin.command("ping")
        db_instance.db = db_instance.client[db_name]
        db_instance.marks_col = db_instance.db["marks"]
        print("Connected to MongoDB Atlas")
    except Exception as exc:
        db_instance.last_error = type(exc).__name__
        if db_instance.client is not None:
            try:
                db_instance.client.close()
            except Exception:
                pass
        db_instance.client = None
        db_instance.db = None
        db_instance.marks_col = None
        print(f"[MONGO] Unavailable ({db_instance.last_error}). Marks will not persist; publish is disabled.")


async def close_mongo_connection():
    if db_instance.client is not None:
        db_instance.client.close()
        print("MongoDB connection closed.")
    db_instance.client = None
    db_instance.db = None
    db_instance.marks_col = None
