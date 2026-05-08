"""
Weak topic analysis module.

Analyzes topics where students have demonstrated weakness or poor performance.
"""

from collections import defaultdict

from src.analytics.topic_utils import resolve_topic


class WeakTopicAnalyzer:
    """Analyzes weak topics from student performance data."""

    def __init__(self, exam_data=None, threshold=0.5):
        """Initialize the weak topic analyzer."""
        self.exam_data = exam_data or {}
        self.threshold = threshold

    def _topic_key_for_result(self, result):
        topic = result.get("topic")
        if topic:
            return topic

        question_number = result.get("question") or result.get("question_number")
        part_id = result.get("part")

        if question_number is not None:
            return resolve_topic(self.exam_data, question_number, part_id)

        return "Unknown"

    def _score_from_result(self, result):
        if "learning_score" in result:
            return result["learning_score"]

        performance = result.get("performance_score")
        if performance is not None:
            return performance

        return result.get("score", 0)

    def analyze(self, results):
        """Perform weak topic analysis."""
        student_topic_scores = defaultdict(lambda: defaultdict(list))

        for result in results:
            student_id = result.get("student_id", "UNKNOWN")
            topic = self._topic_key_for_result(result)
            student_topic_scores[student_id][topic].append(self._score_from_result(result))

        topic_aggregates = defaultdict(lambda: {
            "weak_students": 0,
            "students_attempted": 0,
            "attempts": 0,
            "total_score": 0.0,
        })

        for student_id, topics in student_topic_scores.items():
            for topic, scores in topics.items():
                if not scores:
                    continue

                average_score = sum(scores) / len(scores)
                aggregate = topic_aggregates[topic]
                aggregate["students_attempted"] += 1
                aggregate["attempts"] += len(scores)
                aggregate["total_score"] += average_score

                if average_score < self.threshold:
                    aggregate["weak_students"] += 1

        weak_topics = []

        for topic, aggregate in topic_aggregates.items():
            if not aggregate["students_attempted"]:
                continue

            weak_share = aggregate["weak_students"] / aggregate["students_attempted"]
            average_score = aggregate["total_score"] / aggregate["students_attempted"]

            if aggregate["students_attempted"] >= 2 and weak_share >= 0.4:
                weak_topics.append({
                    "topic": topic,
                    "average_learning_score": round(average_score, 3),
                    "weak_student_count": aggregate["weak_students"],
                    "students_attempted": aggregate["students_attempted"],
                    "weak_student_share": round(weak_share, 3),
                    "status": "WEAK"
                })

        return sorted(weak_topics, key=lambda item: (item["weak_student_share"], item["average_learning_score"]), reverse=True)
