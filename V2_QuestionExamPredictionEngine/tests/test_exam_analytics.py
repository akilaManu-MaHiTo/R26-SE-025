from app.analytics.exam_analytics import compute_exam_analytics_stats
from app.schemas.exam_analytics import ExamAnalyticsDocument


def exam_document() -> dict:
    return {
        "exam_id": "IT2040@Final Examination 2021",
        "course": {"code": "IT2040", "name": "Database Management Systems"},
        "exam": {"session_name": "Final Examination 2021", "total_marks": 100.0, "question_count": 11},
        "statistics": {"total_students": 5, "attempted_students": 5, "average_score": 67.4,
                       "average_percentage": 67.4, "pass_rate": 80.0, "highest_score": 94.0, "lowest_score": 31.0},
        "topic_performance": [{"topic": "JDBC", "average_percentage": 76.0, "status": "Strong"}],
        "bloom_performance": [{"level": "Remember", "average_percentage": 83.0}],
        "question_performance": [{"question_id": "Q01", "question_no": "01", "topic": "DBMS Design",
                                  "bloom_level": "Understand", "average_percentage": 75.0}],
        "attention_areas": [{"type": "topic", "name": "SQL", "average_percentage": 33.0, "priority": "Critical"}],
        "insights": ["SQL is the weakest topic across the class."],
        "generated_at": "2026-08-12T00:00:00Z",
        "analytics_version": "1.0",
    }


def test_exam_analytics_serializes_exact_top_level_contract():
    document = ExamAnalyticsDocument(**exam_document())
    assert set(document.model_dump(mode="json")) == {
        "exam_id", "course", "exam", "statistics", "topic_performance",
        "bloom_performance", "question_performance", "attention_areas",
        "insights", "generated_at", "analytics_version",
    }


def _student_docs():
    return [
        {
            "overall": {"score": 80.0, "maximum": 100.0, "percentage": 80.0},
            "topic_performance": [{"topic": "JDBC", "score": 20.0, "max_score": 25.0}],
            "bloom_performance": [{"level": "Remember", "average_score": 80.0}],
            "question_performance": [{"question_no": "01", "topic": "JDBC", "bloom_level": "Remember", "score": 8.0, "max_score": 10.0}],
        },
        {
            "overall": {"score": 40.0, "maximum": 100.0, "percentage": 40.0},
            "topic_performance": [{"topic": "JDBC", "score": 5.0, "max_score": 25.0}],
            "bloom_performance": [{"level": "Remember", "average_score": 40.0}],
            "question_performance": [{"question_no": "01", "topic": "JDBC", "bloom_level": "Remember", "score": 4.0, "max_score": 10.0}],
        },
    ]


def test_class_statistics_are_computed_from_all_students():
    stats = compute_exam_analytics_stats(_student_docs(), pass_threshold=0.5)
    assert stats["statistics"]["total_students"] == 2
    assert stats["statistics"]["average_percentage"] == 60.0
    assert stats["statistics"]["pass_rate"] == 50.0
    assert stats["statistics"]["highest_score"] == 80.0
    assert stats["statistics"]["lowest_score"] == 40.0
    assert stats["topic_performance"][0]["average_percentage"] == 50.0  # 25/50
    assert stats["topic_performance"][0]["status"] == "Needs Improvement"


def test_attention_areas_derive_from_bottom_topics():
    stats = compute_exam_analytics_stats(_student_docs(), pass_threshold=0.5)
    assert stats["attention_areas"][0]["name"] == "JDBC"
    assert stats["attention_areas"][0]["priority"] == "High"


def test_insights_are_deterministic():
    stats = compute_exam_analytics_stats(_student_docs(), pass_threshold=0.5)
    assert any("weakest topic" in insight for insight in stats["insights"])
