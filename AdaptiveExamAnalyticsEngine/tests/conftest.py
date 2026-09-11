import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings


@pytest.fixture(autouse=True)
def _disable_bloom_for_tests(monkeypatch):
    """Option B hybrid: disable ModernBERT bloom during tests to preserve LLM/rules baseline expectations."""
    monkeypatch.setattr(settings, "bloom_enabled", False)
    yield

TEST_DB_NAME = "dbms_analytics_test"


@pytest.fixture(scope="session")
async def test_db():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[TEST_DB_NAME]
    yield db
    await client.drop_database(TEST_DB_NAME)
    client.close()