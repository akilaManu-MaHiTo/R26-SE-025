# src/analytics/topic_analysis.py

from collections import defaultdict

from src.analytics.topic_utils import resolve_topic


class TopicAnalytics:

    def __init__(self, exam_data):
        self.exam_data = exam_data
        self.topic_scores = defaultdict(list)
        self.question_scores = defaultdict(list)

    # 🔹 Get topic
    def get_topic(self, q_id, part_id):
        return resolve_topic(self.exam_data, q_id, part_id)

    # 🔹 Add score during grading
    def add_result(self, q_id, part_id, marks, max_marks):
        topic = self.get_topic(q_id, part_id)

        normalized = marks / max_marks if max_marks else 0

        self.topic_scores[topic].append(normalized)
        self.question_scores[(q_id, part_id)].append(normalized)

    # 🔹 Build topic analysis
    def analyze_topics(self):
        results = {}

        for topic, scores in self.topic_scores.items():
            avg = sum(scores) / len(scores)

            if avg < 0.4:
                level = "WEAK"
            elif avg < 0.7:
                level = "AVERAGE"
            else:
                level = "STRONG"

            results[topic] = {
                "average_score": round(avg, 2),
                "performance": level,
                "attempts": len(scores)
            }

        return results

    # 🔹 Build question analysis
    def analyze_questions(self):
        results = {}

        for (q_id, part_id), scores in self.question_scores.items():
            avg = sum(scores) / len(scores)

            if avg < 0.4:
                difficulty = "HARD"
            elif avg < 0.7:
                difficulty = "MEDIUM"
            else:
                difficulty = "EASY"

            results[f"Q{q_id}{part_id}"] = {
                "average_score": round(avg, 2),
                "difficulty": difficulty,
                "attempts": len(scores)
            }

        return results

    # 🔹 Insights
    def get_insights(self, topic_analysis):
        if not topic_analysis:
            return {
                "weakest_topic": None,
                "strongest_topic": None
            }

        weakest = min(topic_analysis.items(), key=lambda x: x[1]["average_score"])
        strongest = max(topic_analysis.items(), key=lambda x: x[1]["average_score"])

        return {
            "weakest_topic": weakest[0],
            "strongest_topic": strongest[0]
        }