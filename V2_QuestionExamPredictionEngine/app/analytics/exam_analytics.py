"""Pure, deterministic class-level math for exam analytics documents.

Aggregates per-student numeric analysis (produced by ``build_numeric_analysis``)
into lecturer-facing statistics. No model calls: every value is computed from
the supplied normalized evidence.
"""

from app.analytics.student_document import performance_status

_ATTENTION_PRIORITY = {
    "Critical": "Critical",
    "Needs Improvement": "High",
    "Developing": "Medium",
}


def build_insights(
    statistics: dict, topic_performance: list[dict], question_performance: list[dict]
) -> list[str]:
    """Return deterministic template-string insights about the cohort."""
    insights: list[str] = []
    if topic_performance:
        weakest = min(topic_performance, key=lambda item: item["average_percentage"])
        insights.append(f"{weakest['topic']} is the weakest topic across the class.")
        strongest = max(topic_performance, key=lambda item: item["average_percentage"])
        insights.append(f"{strongest['topic']} is the strongest topic across the class.")
    if question_performance:
        lowest = min(
            question_performance, key=lambda item: item["average_percentage"]
        )
        insights.append(
            f"Question Q{lowest['question_no']} was the lowest-performing question."
        )
    return insights


def compute_exam_analytics_stats(normalized_students: list[dict], pass_threshold: float) -> dict:
    totals = [student["overall"] for student in normalized_students]
    percentages = [total["percentage"] for total in totals]
    average_percentage = sum(percentages) / len(percentages) if percentages else 0.0
    pass_rate = (
        sum(1 for p in percentages if p >= pass_threshold * 100.0) / len(percentages) * 100.0
        if percentages else 0.0
    )
    statistics = {
        "total_students": len(totals),
        "attempted_students": len([t for t in totals if t["maximum"] > 0]),
        "average_score": round(sum(t["score"] for t in totals) / len(totals), 2) if totals else 0.0,
        "average_percentage": round(average_percentage, 2),
        "pass_rate": round(pass_rate, 2),
        "highest_score": max(t["score"] for t in totals) if totals else 0.0,
        "lowest_score": min(t["score"] for t in totals) if totals else 0.0,
    }

    # Marks-weighted topic aggregation across all students
    topic_score: dict[str, float] = {}
    topic_max: dict[str, float] = {}
    for student in normalized_students:
        for topic in student["topic_performance"]:
            topic_score[topic["topic"]] = topic_score.get(topic["topic"], 0.0) + topic["score"]
            topic_max[topic["topic"]] = topic_max.get(topic["topic"], 0.0) + topic["max_score"]
    topic_performance = [
        {
            "topic": name,
            "average_percentage": round(score / topic_max[name] * 100.0, 2),
            "status": performance_status(score / topic_max[name] * 100.0),
        }
        for name, score in sorted(
            topic_score.items(), key=lambda item: item[1] / topic_max[item[0]]
        )
    ]

    # Marks-weighted bloom aggregation via question_performance (single source of truth)
    bloom_score: dict[str, float] = {}
    bloom_max: dict[str, float] = {}
    for student in normalized_students:
        for q in student.get("question_performance", []):
            lvl = q["bloom_level"]
            bloom_score[lvl] = bloom_score.get(lvl, 0.0) + q["score"]
            bloom_max[lvl] = bloom_max.get(lvl, 0.0) + q["max_score"]
    if bloom_score:
        bloom_performance = [
            {"level": level, "average_percentage": round(bloom_score[level] / bloom_max[level] * 100 if bloom_max[level] > 0 else 0.0, 2)}
            for level in sorted(bloom_score)
        ]
    else:
        # Fallback: if question_performance empty, keep old path to avoid break
        bloom_score = {}
        bloom_count: dict[str, int] = {}
        for student in normalized_students:
            for bloom in student.get("bloom_performance", []):
                bloom_score[bloom["level"]] = bloom_score.get(bloom["level"], 0.0) + bloom["average_score"]
                bloom_count[bloom["level"]] = bloom_count.get(bloom["level"], 0) + 1
        bloom_performance = [
            {"level": level, "average_percentage": round(total / bloom_count[level], 2)}
            for level, total in sorted(bloom_score.items())
        ]

    question_score: dict[str, dict] = {}
    for student in normalized_students:
        for question in student.get("question_performance", []):
            entry = question_score.setdefault(
                question["question_no"],
                {"question_id": f"Q{question['question_no']}", "question_no": question["question_no"],
                 "topic": question["topic"], "bloom_level": question["bloom_level"],
                 "score": 0.0, "max_score": 0.0},
            )
            entry["score"] += question["score"]
            entry["max_score"] += question["max_score"]
    question_performance = [
        {
            "question_id": entry["question_id"],
            "question_no": entry["question_no"],
            "topic": entry["topic"],
            "bloom_level": entry["bloom_level"],
            "average_percentage": round(entry["score"] / entry["max_score"] * 100 if entry["max_score"] > 0 else 0.0, 2),
        }
        for entry in sorted(question_score.values(), key=lambda item: item["question_no"])
    ]

    attention_areas = [
        {"type": "topic", "name": topic["topic"], "average_percentage": topic["average_percentage"],
         "priority": _ATTENTION_PRIORITY[topic["status"]]}
        for topic in topic_performance
        if topic["status"] in _ATTENTION_PRIORITY
    ]
    insights = build_insights(statistics, topic_performance, question_performance)
    return {
        "statistics": statistics,
        "topic_performance": topic_performance,
        "bloom_performance": bloom_performance,
        "question_performance": question_performance,
        "attention_areas": attention_areas,
        "insights": insights,
    }
