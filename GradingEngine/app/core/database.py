from motor.motor_asyncio import AsyncIOMotorClient
import os
from pathlib import Path
from dotenv import load_dotenv

_GRADING_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_GRADING_ROOT / ".env")

class Database:
    client: AsyncIOMotorClient = None
    db = None
    # We define the collection here so it's easy to access everywhere
    rubric_col = None
    submissions_col = None
    courses_col = None

db_instance = Database()


def _database_name() -> str:
    """Return a valid database name when DATABASE_NAME is omitted in deployment."""
    return (os.getenv("DATABASE_NAME") or "Grading").strip() or "Grading"


async def connect_to_mongo():
    # We add a 10-second timeout to allow for slow DNS resolution
    mongo_url = (os.getenv("MONGODB_URL") or "").strip()
    if not mongo_url:
        raise RuntimeError("MONGODB_URL is not set")

    db_instance.client = AsyncIOMotorClient(
        mongo_url,
        serverSelectionTimeoutMS=10000 
    )
    db_instance.db = db_instance.client[_database_name()]
    db_instance.rubric_col = db_instance.db["rubricCollection"]
    db_instance.submissions_col = db_instance.db["submissions"]
    db_instance.courses_col = db_instance.db["courses"]
    await db_instance.courses_col.create_index("code", unique=True)
    print("Connected to MongoDB Atlas")

async def close_mongo_connection():
    db_instance.client.close()
    print("MongoDB connection closed.")