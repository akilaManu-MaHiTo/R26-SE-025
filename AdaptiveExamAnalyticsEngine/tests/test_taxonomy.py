import pytest
from unittest.mock import AsyncMock, MagicMock

from app.analytics.taxonomy import (
    BLOOM_LEVELS,
    DEFAULT_PRIORITY_WEIGHTS,
    QUESTION_TYPES,
    TOPICS,
)


# ── Task 2 TDD: per-course taxonomy ──────────────────────────────────

@pytest.mark.asyncio
async def test_load_taxonomy_per_course_db_first():
    from app.taxonomy import normalizer
    # ensure clean cache for CS3010
    try:
        await normalizer.invalidate_taxonomy_cache("CS3010")
    except Exception:
        pass
    mock_db = MagicMock()
    topics = {"sched": {"canonical_topic": "Scheduling", "aliases": ["Sched"], "subtopics": []}}
    doc = {"course_code": "CS3010", "topics": topics, "version": 1}
    # patch repository.get_course_taxonomy
    original = None
    try:
        from app.db import repository as _repo
        original = _repo.get_course_taxonomy
        _repo.get_course_taxonomy = AsyncMock(return_value=doc)
        result = await normalizer.load_taxonomy(mock_db, "CS3010")
        assert "sched" in result
        assert result["sched"]["canonical_topic"] == "Scheduling"
    finally:
        if original is not None:
            from app.db import repository as _repo2
            _repo2.get_course_taxonomy = original
        try:
            await normalizer.invalidate_taxonomy_cache("CS3010")
        except Exception:
            pass


def test_slugify():
    from app.taxonomy.normalizer import slugify_topic
    assert slugify_topic("Structured Query Language (SQL)") == "structured_query_language_sql"
    # edge: empty/None? spec says "topic" fallback for empty after processing
    assert slugify_topic("") == "topic"
    assert slugify_topic("   ") == "topic"
    assert slugify_topic("___") == "topic"
    # truncation
    long_topic = "A" * 100
    assert len(slugify_topic(long_topic)) <= 64


@pytest.mark.asyncio
async def test_normalize_topic_per_course():
    from app.taxonomy import normalizer
    try:
        await normalizer.invalidate_taxonomy_cache("CS3010")
    except Exception:
        pass
    mock_db = MagicMock()
    topics = {"sched": {"canonical_topic": "Scheduling", "aliases": ["Sched"], "subtopics": []}}
    doc = {"course_code": "CS3010", "topics": topics, "version": 1}
    try:
        from app.db import repository as _repo
        original = _repo.get_course_taxonomy
        _repo.get_course_taxonomy = AsyncMock(return_value=doc)
        # also mock seed to avoid fallback path
        orig_seed = _repo.seed_it2040_if_empty
        _repo.seed_it2040_if_empty = AsyncMock(return_value=None)
        result = await normalizer.normalize_topic("Scheduling", mock_db, "CS3010")
        assert result == "sched"
        # alias case-insensitive
        result2 = await normalizer.normalize_topic("sched", mock_db, "CS3010")
        assert result2 == "sched"
        unknown = await normalizer.normalize_topic("Unknown", mock_db, "CS3010")
        assert unknown is None
        unknown2 = await normalizer.normalize_topic(None, mock_db, "CS3010")
        assert unknown2 is None
    finally:
        from app.db import repository as _repo2
        _repo2.get_course_taxonomy = original
        _repo2.seed_it2040_if_empty = orig_seed
        try:
            await normalizer.invalidate_taxonomy_cache("CS3010")
        except Exception:
            pass


@pytest.mark.asyncio
async def test_it2040_seed_fallback():
    from app.taxonomy import normalizer
    try:
        await normalizer.invalidate_taxonomy_cache("IT2040")
    except Exception:
        pass
    mock_db = MagicMock()
    # simulate DB miss then seed populates IT2040 with file content containing sql
    try:
        from app.db import repository as _repo
        orig_get = _repo.get_course_taxonomy
        orig_seed = _repo.seed_it2040_if_empty
        # first call returns None, second after seed returns topics with sql
        file_topics = {"sql": {"canonical_topic": "Structured Query Language (SQL)", "aliases": ["SQL"], "subtopics": []}}
        seed_doc = {"course_code": "IT2040", "topics": file_topics, "version": 1}
        call_count = {"n": 0}
        async def fake_get(db, code):
            # first call before seed -> None, after seed -> seed_doc
            if call_count["n"] == 0:
                return None
            return seed_doc
        async def fake_seed(db):
            call_count["n"] += 1
            return seed_doc
        _repo.get_course_taxonomy = fake_get
        _repo.seed_it2040_if_empty = fake_seed
        result = await normalizer.load_taxonomy(mock_db, "IT2040")
        assert "sql" in result
        assert result["sql"]["canonical_topic"] == "Structured Query Language (SQL)"
        # non-IT2040 missing should return {}
        await normalizer.invalidate_taxonomy_cache("CS9999")
        _repo.get_course_taxonomy = AsyncMock(return_value=None)
        _repo.seed_it2040_if_empty = AsyncMock(return_value=None)
        result2 = await normalizer.load_taxonomy(mock_db, "CS9999")
        assert result2 == {}
    finally:
        from app.db import repository as _repo2
        _repo2.get_course_taxonomy = orig_get
        _repo2.seed_it2040_if_empty = orig_seed
        try:
            await normalizer.invalidate_taxonomy_cache("IT2040")
            await normalizer.invalidate_taxonomy_cache("CS9999")
        except Exception:
            pass


def test_eight_dbms_topics_exact_strings():
    # Phase 2: expanded from 8 to 11 to split overloaded Database Utilities
    # (Indexes / Transactions / Recovery were aliased into one, breaking scoring)
    assert TOPICS == [
        "Introduction to DBMS & Conceptual Database Design",
        "Logical Database Design",
        "Schema Refinement",
        "Structured Query Language (SQL)",
        "Database Programming",
        "Java Database Connectivity (JDBC)",
        "Database Indexes and Storage Structures",
        "Database Transaction Management and Concurrency Control",
        "Database Recovery and Log Management",
        "Database Utilities",
        "Database Security",
    ]


def test_six_revised_bloom_levels():
    assert BLOOM_LEVELS == [
        "Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create",
    ]


def test_question_types_include_problem_solving():
    assert "problem_solving" in QUESTION_TYPES


def test_priority_weights_sum_to_one():
    assert sum(DEFAULT_PRIORITY_WEIGHTS.values()) == 1.0