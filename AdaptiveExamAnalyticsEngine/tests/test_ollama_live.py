import os

import pytest

from app.services.llm_service import classify_question

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_OLLAMA_TESTS") != "1",
    reason="live Ollama test; set RUN_OLLAMA_TESTS=1",
)


def test_live_classify_sql(monkeypatch):
    monkeypatch.delenv("EMBEDDING_AVAILABLE", raising=False)
    result = classify_question("Write a SQL SELECT that joins two tables.")
    assert result["status"] in ("rules", "qwen", "qwen_review")
    assert "rules" in result