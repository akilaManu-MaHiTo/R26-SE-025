from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.config import settings
from app.schemas.student import StudentAnalyticsDocument
from app.services import student_pipeline
from app.services.student_pipeline import materialize_student_analytics


COURSE = {
    "course_code": "IT2040",
    "course_name": "Database Management Systems",
}

RUBRIC = {
    "_id": "rubric-1",
    "subject_code": "IT2040",
    "session_name": "Final Examination",
    "questions": [
        {
            "question_no": "02",
            "question_text": "Explain an unfamiliar database concept.",
            "criteria": [{"point": "Explains the concept", "marks": 5}],
        },
        {
            "question_no": "01",
            "question_text": "Apply SELECT and JOIN to retrieve rows.",
            "criteria": [{"point": "Uses the correct query", "marks": 5}],
        },
    ],
}


def submission(student_id: str, *, first_score: float = 3, second_score: float = 3) -> dict:
    return {
        "student_id": student_id,
        "rubric_ref": "rubric-1",
        "subject_code": "IT2040",
        "session_name": "Final Examination",
        "status": "graded",
        "evaluation": {
            "grading_source": "colab",
            "rag_context_used": True,
            "results": [
                {
                    "q_no": "02",
                    "score": second_score,
                    "criteria_breakdown": [
                        {
                            "point": "Explains the concept",
                            "marks": 5,
                            "earned": second_score,
                        }
                    ],
                },
                {
                    "q_no": "01",
                    "score": first_score,
                    "criteria_breakdown": [
                        {
                            "point": "Uses the correct query",
                            "marks": 5,
                            "earned": first_score,
                        }
                    ],
                },
            ],
        },
    }


def ok_semantics(question: str = "") -> dict:
    if "SELECT" in question:
        semantics = {
            "level": "Apply",
            "topic": "SQL",
            "subtopic": "Joins",
            "confidence": 0.95,
            "reason": "The question asks the student to apply a query.",
        }
    else:
        semantics = {
            "level": "Understand",
            "topic": "Database Concepts",
            "subtopic": "Concept Explanation",
            "confidence": 0.9,
            "reason": "The question asks the student to explain a concept.",
        }
    return {"status": "ok", "semantics": semantics}


def install_repository_boundaries(monkeypatch, submissions: list[dict]):
    db = SimpleNamespace(saved=[])

    async def find_submissions(_db):
        return submissions

    async def find_course(_db, _submission):
        return deepcopy(COURSE)

    async def find_rubric(_db, _submission):
        return deepcopy(RUBRIC)

    async def upsert(_db, document):
        db.saved.append(deepcopy(document))

    monkeypatch.setattr(student_pipeline, "find_graded_submissions", find_submissions)
    monkeypatch.setattr(student_pipeline, "find_course_for_submission", find_course)
    monkeypatch.setattr(student_pipeline, "find_rubric_for_submission", find_rubric)
    monkeypatch.setattr(student_pipeline, "upsert_student_analytics", upsert)
    return db


async def test_pipeline_reuses_question_classification_across_students(monkeypatch):
    db = install_repository_boundaries(
        monkeypatch,
        [submission("student-b"), submission("student-a")],
    )
    calls = 0

    async def classify(_course, question, _criteria):
        nonlocal calls
        calls += 1
        return ok_semantics(question)

    monkeypatch.setattr(student_pipeline, "classify_question_semantics", classify)
    monkeypatch.setattr(
        student_pipeline,
        "generate_student_insights",
        AsyncMock(return_value={"status": "degraded", "reason": "ollama_unavailable"}),
    )

    result = await materialize_student_analytics(db)

    assert result.saved == ["student-b", "student-a"]
    assert result.failures == []
    assert calls == 2
    assert [item["student_id"] for item in db.saved] == ["student-b", "student-a"]
    assert [item["question_no"] for item in db.saved[0]["question_analysis"]] == [
        "01",
        "02",
    ]
    for document in db.saved:
        StudentAnalyticsDocument.model_validate(document)


async def test_pipeline_uses_deterministic_fallback_when_qwen_is_down(monkeypatch):
    db = install_repository_boundaries(monkeypatch, [submission("IT22145976")])
    monkeypatch.setattr(
        student_pipeline,
        "classify_question_semantics",
        AsyncMock(return_value={"status": "degraded", "reason": "ollama_unavailable"}),
    )
    monkeypatch.setattr(
        student_pipeline,
        "generate_student_insights",
        AsyncMock(return_value={"status": "degraded", "reason": "ollama_unavailable"}),
    )

    result = await materialize_student_analytics(db)

    assert result.saved == ["IT22145976"]
    assert result.failures == []
    saved = db.saved[0]
    assert saved["assessment"]["percentage"] == 60.0
    assert saved["question_analysis"][0]["bloom_analysis"]["confidence"] == 0.85
    assert saved["question_analysis"][0]["subtopic"] == "SQL"
    assert "rule-based fallback" in saved["question_analysis"][0]["bloom_analysis"][
        "reason"
    ]
    assert saved["learning_analysis"]["learning_gaps"] == [
        "Review Uses the correct query in SQL.",
        "Review Explains the concept in Introduction to DBMS and Conceptual Database Design.",
    ]
    assert saved["recommendations"][0]["priority"] == "High"
    assert saved["next_question_generation"]["number_of_questions"] == 5
    StudentAnalyticsDocument.model_validate(saved)


async def test_pipeline_uses_rule_key_concept_as_fallback_subtopic(monkeypatch):
    db = install_repository_boundaries(monkeypatch, [submission("student-17")])
    monkeypatch.setattr(
        student_pipeline,
        "classify_question_semantics",
        AsyncMock(return_value={"status": "degraded", "reason": "schema_failure"}),
    )
    monkeypatch.setattr(
        student_pipeline,
        "classify_by_rules",
        lambda _question: SimpleNamespace(
            bloom_level="Analyze",
            topic_assignments=[SimpleNamespace(topic="Transactions", weight=1.0)],
            key_concepts=["Two-Phase Locking"],
            confidence="medium",
        ),
    )
    monkeypatch.setattr(
        student_pipeline,
        "generate_student_insights",
        AsyncMock(return_value={"status": "degraded", "reason": "schema_failure"}),
    )

    result = await materialize_student_analytics(db)

    assert result.saved == ["student-17"]
    assert {item["subtopic"] for item in db.saved[0]["question_analysis"]} == {
        "Two-Phase Locking"
    }
    assert {
        item["bloom_analysis"]["confidence"]
        for item in db.saved[0]["question_analysis"]
    } == {0.65}
    assert all(
        "schema_failure" in item["bloom_analysis"]["reason"]
        for item in db.saved[0]["question_analysis"]
    )


async def test_qwen_insights_replace_only_semantic_fallback_fields(monkeypatch):
    db = install_repository_boundaries(monkeypatch, [submission("student-17")])
    monkeypatch.setattr(
        student_pipeline,
        "classify_question_semantics",
        AsyncMock(side_effect=lambda _course, question, _criteria: ok_semantics(question)),
    )
    monkeypatch.setattr(
        student_pipeline,
        "generate_student_insights",
        AsyncMock(
            return_value={
                "status": "ok",
                "learning_gaps": ["Trace joins before writing SQL."],
                "recommendations": [
                    {
                        "priority": "Medium",
                        "topic": "SQL",
                        "bloom_level": "Analyze",
                        "action": "Compare inner and outer joins.",
                    }
                ],
                "generation_target": {
                    "recommended_bloom_level": "Analyze",
                    "recommended_difficulty": "Hard",
                    "recommended_topics": ["Joins"],
                    "number_of_questions": 99,
                },
                "assessment": {"percentage": 99.0},
                "learning_analysis": {
                    "overall_performance": "Strong",
                    "weak_topics": [],
                },
            }
        ),
    )

    result = await materialize_student_analytics(db)

    assert result.saved == ["student-17"]
    saved = db.saved[0]
    assert saved["assessment"] == {
        "session_name": "Final Examination",
        "rubric_ref": "rubric-1",
        "total_score": 6.0,
        "max_score": 10.0,
        "percentage": 60.0,
    }
    assert saved["learning_analysis"]["overall_performance"] == "Needs Improvement"
    assert saved["learning_analysis"]["weak_topics"] == ["SQL", "Database Concepts"]
    assert saved["learning_analysis"]["learning_gaps"] == [
        "Trace joins before writing SQL."
    ]
    assert saved["recommendations"][0]["action"] == "Compare inner and outer joins."
    assert saved["next_question_generation"] == {
        "recommended_bloom_level": "Analyze",
        "recommended_difficulty": "Hard",
        "recommended_topics": ["Joins"],
        "number_of_questions": 5,
    }
    assert saved["model_metadata"] == {
        "bloom_model": settings.ollama_model,
        "bloom_model_type": "base",
        "grading_source": "colab",
        "rag_context_used": True,
    }
    assert all(
        set(item) == {
            "topic",
            "questions_attempted",
            "score",
            "max_score",
            "percentage",
            "status",
        }
        for item in saved["topic_performance"]
    )
    assert all(
        set(item) == {"level", "questions_attempted", "average_score", "status"}
        for item in saved["bloom_performance"]
    )
    StudentAnalyticsDocument.model_validate(saved)


async def test_pipeline_isolates_invalid_submission(monkeypatch):
    invalid = submission("invalid-student", first_score=6)
    valid = submission("valid-student")
    db = install_repository_boundaries(monkeypatch, [invalid, valid])
    monkeypatch.setattr(
        student_pipeline,
        "classify_question_semantics",
        AsyncMock(side_effect=lambda _course, question, _criteria: ok_semantics(question)),
    )
    monkeypatch.setattr(
        student_pipeline,
        "generate_student_insights",
        AsyncMock(return_value={"status": "degraded", "reason": "schema_failure"}),
    )

    result = await materialize_student_analytics(db)

    assert result.saved == ["valid-student"]
    assert len(result.failures) == 1
    assert result.failures[0].student_id == "invalid-student"
    assert "exceeds" in result.failures[0].reason
    assert [document["student_id"] for document in db.saved] == ["valid-student"]


async def test_explicit_submissions_are_processed_without_repository_batch_read(
    monkeypatch,
):
    db = install_repository_boundaries(monkeypatch, [])
    batch_read = AsyncMock(side_effect=AssertionError("batch reader must not be called"))
    monkeypatch.setattr(student_pipeline, "find_graded_submissions", batch_read)
    monkeypatch.setattr(
        student_pipeline,
        "classify_question_semantics",
        AsyncMock(side_effect=lambda _course, question, _criteria: ok_semantics(question)),
    )
    monkeypatch.setattr(
        student_pipeline,
        "generate_student_insights",
        AsyncMock(return_value={"status": "degraded", "reason": "schema_failure"}),
    )

    result = await materialize_student_analytics(db, [submission("explicit-student")])

    assert result.saved == ["explicit-student"]
    assert result.failures == []
    batch_read.assert_not_awaited()
