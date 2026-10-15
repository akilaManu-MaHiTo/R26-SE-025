from app.analytics.diagram_analysis import compute_diagram_analysis
from app.analytics.exam_analytics import compute_exam_analytics_stats
from app.schemas.exam_analytics import DiagramAnalysis, TopicPerformanceSummary, TopicBloomCell


def test_old_calculation_snapshot_requires_rebuild():
    from app.api.lecturer import _is_complete_snapshot
    snapshot = {"analytics_version": "1.0", "canonical_topic_performance": [],
                "canonical_insights": [], "statistics": {}}
    assert not _is_complete_snapshot(snapshot)
    snapshot["analytics_version"] = "1.1"
    assert _is_complete_snapshot(snapshot)


def topic_students(question_count):
    return [{
        "overall": {"score": 0, "maximum": 10 * question_count, "percentage": 0},
        "topic_performance": [{"topic": "SQL", "score": 0, "max_score": 10 * question_count}],
        "bloom_performance": [],
        "question_performance": [{"question_no": str(q), "topic": "SQL", "bloom_level": "Apply",
                                  "score": 0, "max_score": 10} for q in range(question_count)],
    } for _ in range(10)]


def test_one_question_has_ten_responses_but_insufficient_topic_coverage():
    result = compute_exam_analytics_stats(topic_students(1), 0.5)
    topic = result["topic_performance"][0]
    assert (topic["student_count"], topic["attempt_count"], topic["question_count"]) == (10, 10, 1)
    assert topic["evidence_status"] == "insufficient_evidence"
    assert TopicPerformanceSummary.model_validate(topic).question_count == 1
    cell = result["topic_bloom_matrix"][0]
    assert (cell["attempt_count"], cell["question_count"]) == (10, 1)
    assert cell["evidence_status"] == "insufficient_evidence"
    assert TopicBloomCell.model_validate(cell).question_count == 1
    assert "1 questions" in result["insights"][0]


def test_two_questions_supply_independent_topic_coverage():
    result = compute_exam_analytics_stats(topic_students(2), 0.5)
    topic = result["topic_performance"][0]
    assert (topic["attempt_count"], topic["question_count"]) == (20, 2)
    assert topic["evidence_status"] == "confirmed_weakness"
    assert result["topic_bloom_matrix"][0]["evidence_status"] == "confirmed_weakness"
    assert "2 questions" in result["insights"][0]


def test_missing_question_records_do_not_invent_coverage_from_topic_totals():
    students = topic_students(1)
    for student in students:
        student["question_performance"] = []
    topic = compute_exam_analytics_stats(students, 0.5)["topic_performance"][0]
    assert (topic["attempt_count"], topic["question_count"]) == (0, 0)
    assert topic["evidence_status"] == "insufficient_evidence"


def test_duplicate_question_numbers_do_not_increase_distinct_coverage():
    students = topic_students(1)
    for student in students:
        student["question_performance"] *= 2
    topic = compute_exam_analytics_stats(students, 0.5)["topic_performance"][0]
    assert topic["question_count"] == 1
    assert topic["evidence_status"] == "insufficient_evidence"


def test_missing_criterion_maximum_is_unavailable_not_best_observed_score():
    rows = [{"student_id": "A", "evaluation_result": {
        "total_score": 2, "max_score": 5, "criteria_results": [
            {"criterion_id": 1, "criterion": "Keys", "awarded_marks": 2, "status": "partial"}]}}]
    result = compute_diagram_analysis(rows, [])
    criterion = result["criterion_performance"][0]
    assert criterion["max_marks"] is None
    assert criterion["average_percentage"] is None
    assert DiagramAnalysis.model_validate(result).criterion_performance[0].average_percentage is None


def test_criterion_percentage_weights_available_marks_and_requires_complete_maxima():
    rows = [{"student_id": str(i), "evaluation_result": {
        "total_score": earned, "max_score": maximum, "criteria_results": [
            {"criterion_id": 1, "criterion": "Keys", "awarded_marks": earned,
             "max_marks": maximum, "status": "partial"}]}}
            for i, (earned, maximum) in enumerate([(2, 5), (4, 10)])]
    criterion = compute_diagram_analysis(rows, [])["criterion_performance"][0]
    assert criterion["average_percentage"] == 40  # 6 earned / 15 available.
    assert criterion["max_marks"] == 7.5  # Mean available marks for the Avg/Max columns.
    del rows[1]["evaluation_result"]["criteria_results"][0]["max_marks"]
    criterion = compute_diagram_analysis(rows, [])["criterion_performance"][0]
    assert criterion["average_percentage"] is None
