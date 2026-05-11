"""
Misunderstood questions analysis module.

Analyzes questions that are frequently misunderstood or answered incorrectly.
"""

from collections import defaultdict


def _question_label(record):
    question_number = record.get("question") or record.get("question_number")
    part_id = record.get("part")

    if question_number is None:
        return "Unknown"

    if part_id is None:
        return f"Q{question_number}"

    return f"Q{question_number}{part_id}"


def _score(record):
    if "learning_score" in record:
        return record["learning_score"]

    if "performance_score" in record:
        return record["performance_score"]

    return record.get("score", 0)


class MisunderstoodQuestionsAnalyzer:
    """Analyzes misunderstood questions from student performance data."""

    def __init__(self, threshold=0.5, minimum_students=2, minimum_below_share=0.4):
        """Initialize the misunderstood questions analyzer."""
        self.threshold = threshold
        self.minimum_students = minimum_students
        self.minimum_below_share = minimum_below_share

    def analyze(self, results):
        """Perform misunderstood questions analysis."""
        question_groups = defaultdict(lambda: defaultdict(list))

        for record in results or []:
            question = _question_label(record)
            student_id = record.get("student_id", "UNKNOWN")
            question_groups[question][student_id].append(_score(record))

        misunderstood = []

        for question, student_scores in question_groups.items():
            if not student_scores:
                continue

            student_averages = [sum(scores) / len(scores) for scores in student_scores.values() if scores]
            if not student_averages:
                continue

            average_score = sum(student_averages) / len(student_averages)
            students_below_threshold = sum(1 for score in student_averages if score < self.threshold)
            total_students = len(student_averages)
            below_share = students_below_threshold / total_students if total_students else 0

            misunderstood.append({
                "question": question,
                "average_score": round(average_score, 3),
                "students_below_threshold": students_below_threshold,
                "status": "Misunderstood"
                if total_students >= self.minimum_students and below_share >= self.minimum_below_share
                else "Review",
            })

        return sorted(
            misunderstood,
            key=lambda item: (item["students_below_threshold"], -item["average_score"], item["question"]),
            reverse=True,
        )
