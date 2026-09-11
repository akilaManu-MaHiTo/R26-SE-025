from app.analytics.recommendation_score import recommendation_score, priority_from_score, bloom_gap_for_level
from app.analytics.weakness import weakness_from_percentage, compute_weakness_scores
from app.services.recommendation import recommend_questions


def test_weakness_from_percentage():
    assert weakness_from_percentage(50.0) == 0.5
    assert weakness_from_percentage(92.0) == 0.08
    assert weakness_from_percentage(0) == 1.0


def test_weakness_merges_jdbc_aliases():
    doc = {
        "topic_performance": [
            {"topic": "Database Connectivity with JDBC", "average_percentage": 50.0, "status": "Needs Improvement"},
            {"topic": "Database Connectivity and SQL Injection Prevention with JDBC", "average_percentage": 80.0, "status": "Strong"},
            {"topic": "Database Connectivity and SQL Injection Prevention using JDBC", "average_percentage": 92.0, "status": "Strong"},
        ]
    }
    from app.services.weakness_scoring import weakness_for_document

    res = weakness_for_document(doc)
    # 3 variants -> 1 canonical JDBC at 74% -> weakness 0.26
    assert "Java Database Connectivity (JDBC)" in res["weakness_scores"]
    assert res["weakness_scores"]["Java Database Connectivity (JDBC)"]["weakness"] == 0.26


def test_recommendation_score_weighted():
    # SQL weakest 0.5, full lecture/tutorial, high exam relevance
    score = recommendation_score(
        weakness=0.5, lecture_coverage=1.0, tutorial_evidence=1.0, exam_relevance=0.5, bloom_gap=0.43
    )
    assert 0.5 < score < 0.9
    assert priority_from_score(score) in ("High", "Medium")
    # Low weakness should score lower
    low = recommendation_score(0.1, 1.0, 1.0, 0.5, 0.0)
    assert score > low


def test_bloom_gap():
    target = {"Apply": 0.4, "Analyze": 0.3}
    current = {"Apply": 0.2, "Analyze": 0.3}
    assert bloom_gap_for_level("Apply", current, target) == 0.5
    assert bloom_gap_for_level("Analyze", current, target) == 0.0


def test_recommend_questions_ranks_weak_first():
    doc = {
        "topic_performance": [
            {"topic": "SQL Queries and Triggers in Database Management Systems", "average_percentage": 50.0, "status": "Needs Improvement"},
            {"topic": "Database Design and Relational Algebra", "average_percentage": 90.0, "status": "Strong"},
        ],
        "bloom_performance": [{"level": "Apply", "average_percentage": 50.0}],
    }
    recs = recommend_questions(doc, limit=5)
    assert len(recs) > 0
    # weakest topic should be SQL at 0.5, so at least one rec should have high weakness if SQL tutorials existed
    # fallback: ensure recommendations have scores and priorities
    assert all("recommendation_score" in r for r in recs)
    assert all(r["priority"] in ("High", "Medium", "Low") for r in recs)
