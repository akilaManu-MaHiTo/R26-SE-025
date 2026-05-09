from src.analytics.weak_topic_model import DEFAULT_MODEL_PATH, WeakTopicModel, build_topic_feature_rows


class WeakTopicAnalyzer:
    """Analyzes weak topics from student performance data."""

    def __init__(self, exam_data=None, threshold=0.5, model_path=DEFAULT_MODEL_PATH, probability_threshold=0.55):
        """Initialize the weak topic analyzer."""
        self.exam_data = exam_data or {}
        self.threshold = threshold
        self.model = WeakTopicModel(model_path=model_path, weak_probability_threshold=probability_threshold)

    def analyze(self, results):
        """Perform weak topic analysis."""
        topic_rows = build_topic_feature_rows(results, weak_threshold=self.threshold)

        if not topic_rows:
            return []

        if self.model.pipeline:
            return self.model.predict(topic_rows)

        weak_topics = []

        for row in topic_rows:
            if row["students_attempted"] >= 2 and row["weak_student_share"] >= 0.4:
                weak_topics.append({
                    "topic": row["topic"],
                    "average_learning_score": row["average_learning_score"],
                    "weak_student_count": row["weak_student_count"],
                    "students_attempted": row["students_attempted"],
                    "weak_student_share": row["weak_student_share"],
                    "average_performance_score": row["average_performance_score"],
                    "average_concept_score": row["average_concept_score"],
                    "average_cognitive_score": row["average_cognitive_score"],
                    "score_stddev": row["score_stddev"],
                    "average_level_gap": row["average_level_gap"],
                    "status": "WEAK",
                    "weak_probability": None,
                })

        return sorted(
            weak_topics,
            key=lambda item: (item["weak_student_share"], item["average_learning_score"]),
            reverse=True,
        )
