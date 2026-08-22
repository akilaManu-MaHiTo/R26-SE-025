import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

TEST_DB_NAME = "dbms_analytics_test"


@pytest.fixture(scope="session")
async def test_db():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[TEST_DB_NAME]
    yield db
    await client.drop_database(TEST_DB_NAME)
    client.close()