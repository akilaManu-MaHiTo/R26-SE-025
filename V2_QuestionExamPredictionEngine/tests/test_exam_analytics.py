from app.analytics.exam_analytics import compute_exam_analytics_stats
from app.schemas.exam_analytics import ExamAnalyticsDocument


def exam_document() -> dict:
    return {
        "subject_code": "IT2040",
        "subject_name": "Database Management Systems",
        "year": 2022,
        "month": 7,
        "semester": 1,
        "session_name": "Final Examination",
        "exam": {"session_name": "Final Examination", "total_marks": 100.0, "question_count": 11},
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
        "subject_code", "subject_name", "year", "month", "semester",
        "session_name", "exam", "statistics", "topic_performance",
        "bloom_performance", "question_performance", "topic_bloom_matrix", "attention_areas",
        "insights", "canonical_topic_performance", "canonical_attention_areas",
        "canonical_insights", "unmapped_topics", "generated_at", "analytics_version",
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


def test_bloom_performance_is_marks_weighted_not_count_averaged():
    # Two students, same Bloom "Apply" but different max_score
    docs = [
        {"overall": {"score": 9, "maximum": 10, "percentage": 90.0},
         "topic_performance": [],
         "bloom_performance": [],
         "question_performance": [
             {"question_no": "01", "topic": "SQL", "bloom_level": "Apply", "score": 9.0, "max_score": 10.0},
         ]},
        {"overall": {"score": 0, "maximum": 10, "percentage": 0.0},
         "topic_performance": [],
         "bloom_performance": [],
         "question_performance": [
             {"question_no": "01", "topic": "SQL", "bloom_level": "Apply", "score": 0.0, "max_score": 10.0},
             {"question_no": "02", "topic": "SQL", "bloom_level": "Apply", "score": 0.0, "max_score": 90.0},
         ]},
    ]
    # Current bug: averages student Bloom averages (90+0)/2=45%
    # Correct marks-weighted: total score 9 / total max 110 = 8.18%
    # We test via question_performance aggregation path which should be used
    from app.analytics.exam_analytics import compute_exam_analytics_stats
    stats = compute_exam_analytics_stats(docs, pass_threshold=0.5)
    bloom = next(b for b in stats["bloom_performance"] if b["level"]=="Apply")
    assert bloom["average_percentage"] < 20, f"bug: count-averaged {bloom['average_percentage']} should be marks-weighted ~8.18"


def test_statistics_include_dispersion_and_grade_distribution():
    stats = compute_exam_analytics_stats(_student_docs(), pass_threshold=0.5)
    s = stats["statistics"]
    assert "median_percentage" in s
    assert "std_percentage" in s
    assert "grade_distribution" in s
    assert s["median_percentage"] == 60.0  # (80+40)/2 median avg 60
    assert s["grade_distribution"]["A"] == 1  # 80% -> A/B threshold per config


def test_topic_evidence_status_insufficient_vs_confirmed():
    # 2 students, 1 question part -> insufficient (needs 10 students / 2 parts per spec default)
    docs = _student_docs()  # 2 students
    stats = compute_exam_analytics_stats(docs, pass_threshold=0.5)
    assert stats["topic_performance"][0]["evidence_status"] == "insufficient_evidence"
    # Confirmed weakness: create 12 students all failing topic
    many = [docs[1]]*12
    stats2 = compute_exam_analytics_stats(many, pass_threshold=0.5)
    assert stats2["topic_performance"][0]["evidence_status"] in ("possible_weakness","confirmed_weakness")


def test_topic_bloom_matrix_computed():
    stats = compute_exam_analytics_stats(_student_docs(), pass_threshold=0.5)
    assert "topic_bloom_matrix" in stats
    assert any(c["topic"]=="JDBC" and c["bloom_level"]=="Remember" for c in stats["topic_bloom_matrix"])


def test_question_discrimination_and_p_value():
    # 4 students: high scorers get Q01 right, low scorers wrong => positive discrimination
    docs = [
        {"overall": {"score":90,"maximum":100,"percentage":90},"topic_performance":[],"bloom_performance":[],"question_performance":[{"question_no":"01","topic":"SQL","bloom_level":"Apply","score":10,"max_score":10}]},
        {"overall": {"score":85,"maximum":100,"percentage":85},"topic_performance":[],"bloom_performance":[],"question_performance":[{"question_no":"01","topic":"SQL","bloom_level":"Apply","score":10,"max_score":10}]},
        {"overall": {"score":30,"maximum":100,"percentage":30},"topic_performance":[],"bloom_performance":[],"question_performance":[{"question_no":"01","topic":"SQL","bloom_level":"Apply","score":0,"max_score":10}]},
        {"overall": {"score":20,"maximum":100,"percentage":20},"topic_performance":[],"bloom_performance":[],"question_performance":[{"question_no":"01","topic":"SQL","bloom_level":"Apply","score":0,"max_score":10}]},
    ]
    stats = compute_exam_analytics_stats(docs, pass_threshold=0.5)
    qp = stats["question_performance"][0]
    assert "discrimination" in qp
    assert qp["discrimination"] > 0.5


def test_insights_include_sample_size_and_bloom_context():
    stats = compute_exam_analytics_stats(_student_docs(), pass_threshold=0.5)
    assert any("n=" in s or "students" in s for s in stats["insights"])
    assert any("Bloom" in s or "Apply" in s for s in stats["insights"])
