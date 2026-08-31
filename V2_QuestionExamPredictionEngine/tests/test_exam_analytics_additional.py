"""Contract tests for new optional dispersion and evidence fields (Task 9)."""

from app.schemas.exam_analytics import ExamAnalyticsDocument
from tests.test_exam_analytics import exam_document


def test_exam_analytics_document_has_new_optional_fields():
    doc = exam_document()
    doc["statistics"].update(
        {
            "median_percentage": 60,
            "std_percentage": 10,
            "iqr_percentage": 5,
            "grade_distribution": {"A": 1, "B": 0, "C": 0, "D": 0, "F": 0},
        }
    )
    validated = ExamAnalyticsDocument.model_validate(doc)
    assert validated.statistics.median_percentage == 60
    assert validated.statistics.std_percentage == 10
    assert validated.statistics.iqr_percentage == 5
    assert validated.statistics.grade_distribution["A"] == 1


def test_exam_analytics_document_has_full_dispersion_defaults():
    doc = exam_document()
    doc["statistics"].update(
        {
            "median_score": 55.0,
            "median_percentage": 55.0,
            "std_score": 12.5,
            "std_percentage": 12.5,
            "iqr_percentage": 8.0,
            "grade_distribution": {"A": 2, "B": 1, "C": 1, "D": 0, "F": 1},
        }
    )
    validated = ExamAnalyticsDocument.model_validate(doc)
    assert validated.statistics.median_score == 55.0
    assert validated.statistics.std_score == 12.5
    assert validated.statistics.grade_distribution["F"] == 1


def test_exam_analytics_document_accepts_evidence_and_matrix_fields():
    doc = exam_document()
    doc["topic_performance"] = [
        {
            "topic": "SQL",
            "average_percentage": 42.0,
            "status": "Needs Improvement",
            "evidence_status": "confirmed_weakness",
            "student_count": 12,
            "attempt_count": 5,
        }
    ]
    doc["question_performance"] = [
        {
            "question_id": "Q01",
            "question_no": "01",
            "topic": "SQL",
            "bloom_level": "Apply",
            "average_percentage": 42.0,
            "evidence_status": "insufficient_evidence",
            "student_count": 5,
            "attempt_count": 1,
            "p_value": 42.0,
            "discrimination": 0.65,
            "missed_criterion_rate": 0.3,
        }
    ]
    doc["topic_bloom_matrix"] = [
        {
            "topic": "SQL",
            "bloom_level": "Apply",
            "average_percentage": 42.0,
            "student_count": 5,
            "attempt_count": 1,
            "evidence_status": "insufficient_evidence",
        }
    ]
    validated = ExamAnalyticsDocument.model_validate(doc)
    assert validated.topic_performance[0].evidence_status == "confirmed_weakness"
    assert validated.question_performance[0].discrimination == 0.65
    assert validated.topic_bloom_matrix[0].topic == "SQL"
