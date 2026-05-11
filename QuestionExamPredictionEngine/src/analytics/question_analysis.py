"""Question-level analysis helpers for exam grading analytics.

This module provides a simple aggregator that builds per-question
statistics from the per-attempt student report records produced by
the grading pipeline (see `analyze_exam.py`).

The primary function `analyze_questions` accepts an iterable of result
records and returns a sorted list of per-question summaries.
"""

from collections import defaultdict
from statistics import mean


def _question_label(record):
    q = record.get("question") or record.get("question_number")
    part = record.get("part")
    if q is None:
        return "Unknown"
    if part is None:
        return f"Q{q}"
    return f"Q{q}{part}"


def _learning_score(record):
    if "learning_score" in record:
        return float(record.get("learning_score") or 0)
    if "performance_score" in record:
        return float(record.get("performance_score") or 0)
    return float(record.get("score", 0) or 0)


def analyze_questions(results, weak_threshold=0.5):
    """Aggregate per-question metrics from grading results.

    Args:
        results: Iterable of per-attempt result records (dict-like).
        weak_threshold: Threshold under which an attempt counts as weak.

    Returns:
        A list of dictionaries, each describing a question part, sorted by
        descending average learning score.
    """
    groups = defaultdict(list)

    for rec in results or []:
        label = _question_label(rec)
        groups[label].append(rec)

    summaries = []

    for label, recs in groups.items():
        learning_scores = [_learning_score(r) for r in recs]
        performance_scores = [float(r.get("performance_score", 0) or 0) for r in recs if r.get("performance_score") is not None]
        concept_scores = [float(r.get("concept_score", 0) or 0) for r in recs if r.get("concept_score") is not None]
        cognitive_scores = [float(r.get("cognitive_score", 0) or 0) for r in recs if r.get("cognitive_score") is not None]

        avg_learning = mean(learning_scores) if learning_scores else 0.0
        avg_performance = mean(performance_scores) if performance_scores else 0.0
        avg_concept = mean(concept_scores) if concept_scores else 0.0
        avg_cognitive = mean(cognitive_scores) if cognitive_scores else 0.0

        student_ids = {r.get("student_id", "UNKNOWN") for r in recs}
        weak_count = sum(1 for s in learning_scores if s < weak_threshold)

        if avg_learning < 0.4:
            difficulty = "HARD"
        elif avg_learning < 0.7:
            difficulty = "MEDIUM"
        else:
            difficulty = "EASY"

        summaries.append({
            "question": label,
            "average_learning_score": round(avg_learning, 3),
            "average_performance_score": round(avg_performance, 3),
            "average_concept_score": round(avg_concept, 3),
            "average_cognitive_score": round(avg_cognitive, 3),
            "attempts": len(learning_scores),
            "students_attempted": len(student_ids),
            "weak_attempts": weak_count,
            "difficulty": difficulty,
        })

    return sorted(summaries, key=lambda x: (x["average_learning_score"], x["question"]), reverse=True)
