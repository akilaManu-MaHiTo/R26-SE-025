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


def _load_evidence_thresholds() -> tuple[int, int]:
    """Load evidence thresholds from config/thresholds.json with safe defaults."""
    try:
        import json
        from pathlib import Path

        cfg = Path(__file__).resolve().parents[2] / "config" / "thresholds.json"
        if cfg.exists():
            data = json.loads(cfg.read_text(encoding="utf-8"))
            min_students = int(data.get("low_sample_threshold", data.get("min_students", 10)))
            if "min_attempts" in data:
                min_attempts = int(data["min_attempts"])
            elif isinstance(data.get("evidence"), dict) and "min_attempts" in data["evidence"]:
                min_attempts = int(data["evidence"]["min_attempts"])
            else:
                min_attempts = 2
            return min_students, min_attempts
    except Exception:
        pass
    return 10, 2


def _evidence_status(
    avg_pct: float, student_count: int, attempt_count: int, min_students: int, min_attempts: int
) -> str:
    if attempt_count < min_attempts or student_count < min_students:
        return "insufficient_evidence"
    if avg_pct >= 60:
        return "strength" if student_count >= min_students else "possible_weakness"
    return (
        "confirmed_weakness"
        if student_count >= min_students and attempt_count >= min_attempts
        else "possible_weakness"
    )


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
    import statistics as _stats
    median_pct = _stats.median(percentages) if percentages else 0.0
    median_score_val = _stats.median([t["score"] for t in totals]) if totals else 0.0
    std_pct = round(_stats.pstdev(percentages), 2) if len(percentages) > 1 else 0.0
    std_score = round(_stats.pstdev([t["score"] for t in totals]), 2) if len(totals) > 1 else 0.0
    try:
        qs = _stats.quantiles(sorted(percentages), n=4) if len(percentages) >= 4 else [0, 0, 0]
        iqr = round(qs[2] - qs[0], 2) if len(qs) >= 3 else 0.0
    except Exception:
        iqr = 0.0
    def grade_for(p): return "A" if p >= 80 else "B" if p >= 65 else "C" if p >= 50 else "D" if p >= 40 else "F"
    grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for p in percentages:
        grade_dist[grade_for(p)] += 1
    statistics = {
        "total_students": len(totals),
        "attempted_students": len([t for t in totals if t["maximum"] > 0]),
        "average_score": round(sum(t["score"] for t in totals) / len(totals), 2) if totals else 0.0,
        "average_percentage": round(average_percentage, 2),
        "pass_rate": round(pass_rate, 2),
        "highest_score": max(t["score"] for t in totals) if totals else 0.0,
        "lowest_score": min(t["score"] for t in totals) if totals else 0.0,
        "median_score": float(median_score_val),
        "median_percentage": float(median_pct),
        "std_score": float(std_score),
        "std_percentage": float(std_pct),
        "iqr_percentage": float(iqr),
        "grade_distribution": grade_dist,
    }

    # Marks-weighted topic aggregation across all students
    min_students, min_attempts = _load_evidence_thresholds()
    topic_score: dict[str, float] = {}
    topic_max: dict[str, float] = {}
    topic_students: dict[str, set[int]] = {}
    topic_attempts: dict[str, int] = {}
    for idx, student in enumerate(normalized_students):
        for topic in student["topic_performance"]:
            name = topic["topic"]
            topic_score[name] = topic_score.get(name, 0.0) + topic["score"]
            topic_max[name] = topic_max.get(name, 0.0) + topic["max_score"]
            topic_students.setdefault(name, set()).add(idx)
            topic_attempts[name] = topic_attempts.get(name, 0) + 1
    topic_performance = []
    for name, score in sorted(
        topic_score.items(), key=lambda item: item[1] / topic_max[item[0]]
    ):
        avg_pct = round(score / topic_max[name] * 100.0, 2) if topic_max[name] else 0.0
        sc = len(topic_students.get(name, set()))
        ac = topic_attempts.get(name, 0)
        topic_performance.append(
            {
                "topic": name,
                "average_percentage": avg_pct,
                "status": performance_status(score / topic_max[name] * 100.0 if topic_max[name] else 0.0),
                "evidence_status": _evidence_status(avg_pct, sc, ac, min_students, min_attempts),
                "student_count": sc,
                "attempt_count": ac,
            }
        )

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
    question_students: dict[str, set[int]] = {}
    question_attempts: dict[str, int] = {}
    question_pairs: dict[str, list[tuple[float, float]]] = {}
    question_criteria_missed: dict[str, int] = {}
    question_criteria_total: dict[str, int] = {}
    for idx, student in enumerate(normalized_students):
        overall_pct = float(student.get("overall", {}).get("percentage", 0.0) or 0.0)
        for question in student.get("question_performance", []):
            qno = question["question_no"]
            entry = question_score.setdefault(
                qno,
                {"question_id": f"Q{question['question_no']}", "question_no": question["question_no"],
                 "topic": question["topic"], "bloom_level": question["bloom_level"],
                 "score": 0.0, "max_score": 0.0},
            )
            entry["score"] += question["score"]
            entry["max_score"] += question["max_score"]
            question_students.setdefault(qno, set()).add(idx)
            question_attempts[qno] = question_attempts.get(qno, 0) + 1
            # collect pair for discrimination/p_value: (overall_pct, question_pct)
            max_s = float(question.get("max_score", 0) or 0)
            score_s = float(question.get("score", 0) or 0)
            q_pct = (score_s / max_s * 100.0) if max_s > 0 else 0.0
            question_pairs.setdefault(qno, []).append((overall_pct, q_pct))
            # criteria missed rate if available
            crit = question.get("criteria_performance")
            if isinstance(crit, list) and crit:
                total = len(crit)
                missed = 0
                for c in crit:
                    if isinstance(c, dict):
                        achieved = c.get("achieved")
                        if achieved is False:
                            missed += 1
                        elif "awarded_marks" in c and "max_marks" in c:
                            try:
                                if float(c["awarded_marks"]) < float(c["max_marks"]):
                                    missed += 1
                            except Exception:
                                if not c.get("achieved"):
                                    missed += 1
                        elif not achieved:
                            missed += 1
                    else:
                        # unknown shape
                        missed += 0
                question_criteria_total[qno] = question_criteria_total.get(qno, 0) + total
                question_criteria_missed[qno] = question_criteria_missed.get(qno, 0) + missed
    question_performance = []
    for entry in sorted(question_score.values(), key=lambda item: item["question_no"]):
        avg_q = round(entry["score"] / entry["max_score"] * 100 if entry["max_score"] > 0 else 0.0, 2)
        sc_q = len(question_students.get(entry["question_no"], set()))
        ac_q = question_attempts.get(entry["question_no"], 0)
        qno = entry["question_no"]
        # p_value is avg_pct (difficulty index)
        p_value = float(avg_q)
        # discrimination: top vs bottom groups
        pairs = question_pairs.get(qno, [])
        n = len(pairs)
        discrimination = 0.0
        if n > 0:
            # determine k: 27% for n>=10 else half
            if n >= 10:
                k = max(1, int(round(n * 0.27)))
            else:
                k = max(1, n // 2)
            # guard k not exceeding n
            k = min(k, n)
            sorted_pairs = sorted(pairs, key=lambda x: x[0], reverse=True)
            top = sorted_pairs[:k]
            bottom = sorted_pairs[-k:] if k <= n else sorted_pairs
            # avoid overlap when n small? slicing already gives distinct when k*2 <= n, else overlap is okay for very small n (e.g., n=2 -> top 1 bottom 1 distinct, n=3 k=1 distinct)
            avg_top = sum(p[1] for p in top) / len(top) if top else 0.0
            avg_bottom = sum(p[1] for p in bottom) / len(bottom) if bottom else 0.0
            discrimination = round((avg_top - avg_bottom) / 100.0, 4)
            # clamp to -1..1
            if discrimination > 1.0:
                discrimination = 1.0
            elif discrimination < -1.0:
                discrimination = -1.0
        # missed_criterion_rate
        total_c = question_criteria_total.get(qno, 0)
        missed_c = question_criteria_missed.get(qno, 0)
        missed_criterion_rate = round(missed_c / total_c, 4) if total_c > 0 else None
        question_performance.append(
            {
                "question_id": entry["question_id"],
                "question_no": entry["question_no"],
                "topic": entry["topic"],
                "bloom_level": entry["bloom_level"],
                "average_percentage": avg_q,
                "evidence_status": _evidence_status(avg_q, sc_q, ac_q, min_students, min_attempts),
                "student_count": sc_q,
                "attempt_count": ac_q,
                "p_value": float(p_value),
                "discrimination": float(discrimination),
                "missed_criterion_rate": missed_criterion_rate,
            }
        )

    # Topic x Bloom matrix: group by (topic, bloom_level) sum score/max, count students
    matrix_score: dict[tuple[str, str], float] = {}
    matrix_max: dict[tuple[str, str], float] = {}
    matrix_students: dict[tuple[str, str], set[int]] = {}
    matrix_attempts: dict[tuple[str, str], int] = {}
    for idx, student in enumerate(normalized_students):
        for q in student.get("question_performance", []):
            key = (q["topic"], q["bloom_level"])
            matrix_score[key] = matrix_score.get(key, 0.0) + q["score"]
            matrix_max[key] = matrix_max.get(key, 0.0) + q["max_score"]
            matrix_students.setdefault(key, set()).add(idx)
            matrix_attempts[key] = matrix_attempts.get(key, 0) + 1
    topic_bloom_matrix = []
    for (topic, bloom_level), score in sorted(matrix_score.items()):
        max_s = matrix_max[(topic, bloom_level)]
        avg_pct = round(score / max_s * 100 if max_s else 0.0, 2)
        sc = len(matrix_students.get((topic, bloom_level), set()))
        ac = matrix_attempts.get((topic, bloom_level), 0)
        topic_bloom_matrix.append(
            {
                "topic": topic,
                "bloom_level": bloom_level,
                "average_percentage": avg_pct,
                "student_count": sc,
                "attempt_count": ac,
                "evidence_status": _evidence_status(avg_pct, sc, ac, min_students, min_attempts),
            }
        )

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
        "topic_bloom_matrix": topic_bloom_matrix,
        "attention_areas": attention_areas,
        "insights": insights,
    }
