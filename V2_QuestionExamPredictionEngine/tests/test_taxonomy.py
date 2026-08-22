from app.analytics.taxonomy import (
    BLOOM_LEVELS,
    DEFAULT_PRIORITY_WEIGHTS,
    QUESTION_TYPES,
    TOPICS,
)


def test_eight_dbms_topics_exact_strings():
    assert TOPICS == [
        "Introduction to DBMS and Conceptual Database Design",
        "Logical Database Design",
        "Schema Refinement",
        "SQL",
        "Database Programming",
        "Java Database Connectivity (JDBC)",
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