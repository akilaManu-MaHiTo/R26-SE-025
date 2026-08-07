TOPICS: list[str] = [
    "Introduction to DBMS and Conceptual Database Design",
    "Logical Database Design",
    "Schema Refinement",
    "SQL",
    "Database Programming",
    "Java Database Connectivity (JDBC)",
    "Database Utilities",
    "Database Security",
]

BLOOM_LEVELS: list[str] = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create",
]

QUESTION_TYPES: list[str] = [
    "multiple_choice",
    "short_answer",
    "essay",
    "problem_solving",
    "design",
    "coding",
]

DEFAULT_PRIORITY_WEIGHTS: dict[str, float] = {
    "weakness": 0.40,
    "coverage_gap": 0.25,
    "bloom_gap": 0.20,
    "topic_importance": 0.15,
}