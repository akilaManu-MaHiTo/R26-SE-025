"""
Cognitive gap analysis module.

Analyzes cognitive gaps in student understanding across different knowledge domains.
"""

from collections import Counter, defaultdict


LEVEL_SCORES = {
    "remember": 1,
    "understand": 2,
    "apply": 3,
    "analyze": 4,
    "evaluate": 5,
    "create": 6,
}


def _question_label(record):
    question_number = record.get("question") or record.get("question_number")
    part_id = record.get("part")

    if question_number is None:
        return "Unknown"

    if part_id is None:
        return f"Q{question_number}"

    return f"Q{question_number}{part_id}"


def _level_score(level):
    return LEVEL_SCORES.get(level, 2)


def _score_to_level(score):
    closest_level = "understand"
    closest_distance = float("inf")

    for level, level_score in LEVEL_SCORES.items():
        distance = abs(score - level_score)
        if distance < closest_distance:
            closest_distance = distance
            closest_level = level

    return closest_level


def _gap_band(required_score, average_student_score):
    gap = required_score - average_student_score

    if gap >= 2:
        return "HIGH"

    if gap >= 1:
        return "MEDIUM"

    return "LOW"


class CognitiveGapAnalyzer:
    """Analyzes cognitive gaps from student performance data."""

    def __init__(self):
        """Initialize the cognitive gap analyzer."""
        self.level_scores = LEVEL_SCORES

    def analyze(self, results):
        """Perform cognitive gap analysis."""
        question_groups = defaultdict(lambda: {"required_levels": [], "student_levels": []})

        for record in results or []:
            question = _question_label(record)
            group = question_groups[question]

            required_level = record.get("required_level")
            student_level = record.get("student_level")

            if required_level:
                group["required_levels"].append(required_level)
            if student_level:
                group["student_levels"].append(student_level)

        gaps = []

        for question, group in question_groups.items():
            required_levels = group["required_levels"]
            student_levels = group["student_levels"]

            if not required_levels or not student_levels:
                continue

            required_level = Counter(required_levels).most_common(1)[0][0]
            student_scores = [_level_score(level) for level in student_levels]
            average_student_score = sum(student_scores) / len(student_scores)
            average_student_level = _score_to_level(round(average_student_score))

            gaps.append({
                "question": question,
                "required": required_level,
                "average_student_level": average_student_level,
                "gap": _gap_band(_level_score(required_level), average_student_score),
            })

        return sorted(gaps, key=lambda item: (item["gap"], item["question"]))
