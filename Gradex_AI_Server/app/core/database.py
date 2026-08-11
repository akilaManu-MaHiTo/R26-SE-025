from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
import os
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

db_instance = Database()

async def connect_to_mongo():
    # 10-second timeout to allow for slow DNS resolution (same as GradingEngine).
    db_instance.client = AsyncIOMotorClient(
        os.getenv("MONGODB_URL"),
        serverSelectionTimeoutMS=10000
    )
    db_instance.db = db_instance.client[os.getenv("DATABASE_NAME")]
    db_instance.marks_col = db_instance.db["marks"]
    print("Connected to MongoDB Atlas")

async def close_mongo_connection():
    db_instance.client.close()
    print("MongoDB connection closed.")
