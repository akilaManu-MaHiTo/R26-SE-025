"""Student-level analysis helpers for exam grading analytics."""

from collections import Counter, defaultdict


PERFORMANCE_BANDS = (
    (0.75, "High"),
    (0.50, "Medium"),
    (0.00, "Low"),
)


def _question_label(record):
    question_number = record.get("question") or record.get("question_number")
    part_id = record.get("part")

    if question_number is None:
        return "Unknown"

    if part_id is None:
        return f"Q{question_number}"

    return f"Q{question_number}{part_id}"


def _learning_score(record):
    if "learning_score" in record:
        return record["learning_score"]

    if "performance_score" in record:
        return record["performance_score"]

    return record.get("score", 0)


def _performance_band(average_score):
    for threshold, label in PERFORMANCE_BANDS:
        if average_score >= threshold:
            return label
    return "Low"


def analyze_student_performance(results, weak_threshold=0.5):
    """Generate per-student summaries from per-attempt result records."""
    student_groups = defaultdict(list)

    for record in results or []:
        student_id = record.get("student_id", "UNKNOWN")
        student_groups[student_id].append(record)

    summaries = []

    for student_id, records in student_groups.items():
        scores = [_learning_score(record) for record in records]
        average_score = sum(scores) / len(scores) if scores else 0

        weak_questions = sorted(
            {
                _question_label(record)
                for record in records
                if _learning_score(record) < weak_threshold
            }
        )

        levels = [record.get("student_level") for record in records if record.get("student_level")]
        dominant_level = Counter(levels).most_common(1)[0][0] if levels else "unknown"

        summaries.append({
            "student_id": student_id,
            "average_learning_score": round(average_score, 3),
            "weak_questions": weak_questions,
            "dominant_cognitive_level": dominant_level,
            "performance_band": _performance_band(average_score),
        })

    return sorted(summaries, key=lambda item: (item["average_learning_score"], item["student_id"]), reverse=True)