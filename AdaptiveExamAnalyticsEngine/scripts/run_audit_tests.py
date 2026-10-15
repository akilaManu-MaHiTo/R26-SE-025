"""Run the audit's offline test selection without credentials or external services."""
import os
import inspect
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    # Avoid loading the project's credential file, including during conftest import.
    from pydantic_settings import DotEnvSettingsSource
    DotEnvSettingsSource._read_env_files = lambda self: {}

    import motor.motor_asyncio
    def no_database(*args, **kwargs):
        raise RuntimeError("Audit runner forbids database connections")
    motor.motor_asyncio.AsyncIOMotorClient.__init__ = no_database

    import httpx
    async def no_async_http(*args, **kwargs):
        raise RuntimeError("Audit runner forbids external HTTP requests")
    def no_http(*args, **kwargs):
        raise RuntimeError("Audit runner forbids external HTTP requests")
    httpx.AsyncHTTPTransport.handle_async_request = no_async_http
    httpx.HTTPTransport.handle_request = no_http

    import pytest
    class OfflineSelection:
        def pytest_collection_modifyitems(self, items):
            for item in items:
                if inspect.iscoroutinefunction(item.obj):
                    item.add_marker(pytest.mark.skip(reason="Windows asyncio setup unavailable in this audit environment"))
                if "tmp_path" in item.fixturenames:
                    item.add_marker(pytest.mark.skip(reason="pytest temporary-path setup unavailable in this audit environment"))
    names = [
        "test_exam_analytics", "test_exam_analytics_additional",
        "test_student_document_analytics", "test_student_data_ingestion",
        "test_recommendation_engine", "test_evaluation",
        "test_llm_student_analysis", "test_llm_practice_questions",
        "test_practice_questions", "test_model_cleanup",
        "test_independent_equation_audit", "test_independent_recommendation_audit",
        "test_independent_dashboard_audit", "test_bloom_evidence_audit",
        "test_assessment_evidence_counts",
        "test_recommendation_evidence", "test_exam_creator",
    ]
    paths = [f"tests/{name}.py" for name in names if (root / f"tests/{name}.py").exists()]
    assert len(paths) == len(names), "Audit selection is incomplete: a required test file is missing"
    # Optional CLI arguments are passed to pytest (for example -k or -vv).
    return pytest.main(paths + ["-q", "--tb=short", "-rxs"] + sys.argv[1:], plugins=[OfflineSelection()])


if __name__ == "__main__":
    raise SystemExit(main())
