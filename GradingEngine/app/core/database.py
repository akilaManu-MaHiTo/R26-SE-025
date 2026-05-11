from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

class Database:
    client: AsyncIOMotorClient = None
    db = None
    # We define the collection here so it's easy to access everywhere
    rubric_col = None
    submissions_col = None

db_instance = Database()

async def connect_to_mongo():
    # We add a 10-second timeout to allow for slow DNS resolution
    db_instance.client = AsyncIOMotorClient(
        os.getenv("MONGODB_URL"),
        serverSelectionTimeoutMS=10000 
    )
    db_instance.db = db_instance.client[os.getenv("DATABASE_NAME")] 
    db_instance.rubric_col = db_instance.db["rubricCollection"]
    db_instance.submissions_col = db_instance.db["submissions"]
    print("Connected to MongoDB Atlas")

async def close_mongo_connection():
    db_instance.client.close()
    print("MongoDB connection closed.")