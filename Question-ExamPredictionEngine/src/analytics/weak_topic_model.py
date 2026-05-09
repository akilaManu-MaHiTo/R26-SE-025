"""Weak topic detection model helpers.

This module builds topic-level features from per-attempt student reports and
trains a lightweight classifier that can replace the hard threshold rule.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "model" / "weak_topic" / "weak_topic_model.joblib"

LEVEL_SCORES = {
    "remember": 1,
    "understand": 2,
    "apply": 3,
    "analyze": 4,
    "evaluate": 5,
    "create": 6,
}


def _score_from_record(record):
    if "learning_score" in record:
        return float(record["learning_score"])

    if "performance_score" in record:
        return float(record["performance_score"])

    return float(record.get("score", 0) or 0)


def _numeric_level(level):
    if not level:
        return None

    return LEVEL_SCORES.get(str(level).lower())


def _safe_mean(values):
    return mean(values) if values else 0.0


def _safe_std(values):
    return pstdev(values) if len(values) > 1 else 0.0


def build_topic_feature_rows(results, weak_threshold=0.5, minimum_students=2, minimum_below_share=0.4):
    """Aggregate per-attempt records into topic-level training rows."""

    topic_groups = defaultdict(lambda: defaultdict(list))

    for record in results or []:
        topic = record.get("topic")
        if not topic:
            question_number = record.get("question") or record.get("question_number")
            part_id = record.get("part")
            topic = f"Q{question_number}{part_id}" if question_number is not None else "Unknown"

        student_id = record.get("student_id", "UNKNOWN")
        topic_groups[topic][student_id].append(record)

    rows = []

    for topic, student_groups in topic_groups.items():
        student_averages = []
        learning_scores = []
        performance_scores = []
        concept_scores = []
        cognitive_scores = []
        level_gaps = []

        for records in student_groups.values():
            scores = [_score_from_record(record) for record in records]
            if not scores:
                continue

            student_average = _safe_mean(scores)
            student_averages.append(student_average)
            learning_scores.extend(scores)

            for record in records:
                if record.get("performance_score") is not None:
                    performance_scores.append(float(record["performance_score"]))
                if record.get("concept_score") is not None:
                    concept_scores.append(float(record["concept_score"]))
                if record.get("cognitive_score") is not None:
                    cognitive_scores.append(float(record["cognitive_score"]))

                required_level = _numeric_level(record.get("required_level"))
                student_level = _numeric_level(record.get("student_level"))
                if required_level is not None and student_level is not None:
                    level_gaps.append(required_level - student_level)

        if not student_averages:
            continue

        weak_students = sum(1 for score in student_averages if score < weak_threshold)
        students_attempted = len(student_averages)
        weak_share = weak_students / students_attempted if students_attempted else 0.0
        attempts = len(learning_scores)
        average_learning_score = _safe_mean(learning_scores)

        rows.append({
            "topic": topic,
            "average_learning_score": round(average_learning_score, 3),
            "average_performance_score": round(_safe_mean(performance_scores), 3),
            "average_concept_score": round(_safe_mean(concept_scores), 3),
            "average_cognitive_score": round(_safe_mean(cognitive_scores), 3),
            "score_stddev": round(_safe_std(learning_scores), 3),
            "weak_student_count": weak_students,
            "students_attempted": students_attempted,
            "attempts": attempts,
            "weak_student_share": round(weak_share, 3),
            "average_level_gap": round(_safe_mean(level_gaps), 3),
            "label": int(students_attempted >= minimum_students and weak_share >= minimum_below_share),
        })

    return rows


class WeakTopicModel:
    """Train and run a small classifier for weak topic detection."""

    FEATURE_NAMES = [
        "average_learning_score",
        "average_performance_score",
        "average_concept_score",
        "average_cognitive_score",
        "score_stddev",
        "weak_student_count",
        "students_attempted",
        "attempts",
        "weak_student_share",
        "average_level_gap",
    ]

    def __init__(self, model_path=DEFAULT_MODEL_PATH, weak_probability_threshold=0.55):
        self.model_path = Path(model_path) if model_path else None
        self.weak_probability_threshold = weak_probability_threshold
        self.pipeline = None

        if self.model_path and self.model_path.exists():
            self.load()

    def _matrix(self, rows):
        return [[float(row.get(name, 0.0) or 0.0) for name in self.FEATURE_NAMES] for row in rows]

    def fit(self, rows):
        labels = [int(row.get("label", 0)) for row in rows]
        if len(set(labels)) < 2:
            raise ValueError("Weak topic model needs both weak and non-weak examples")

        self.pipeline = Pipeline([
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=42,
                ),
            ),
        ])
        self.pipeline.fit(self._matrix(rows), labels)
        return self

    def predict(self, rows):
        if not self.pipeline:
            raise ValueError("Weak topic model is not trained or loaded")

        probabilities = self.pipeline.predict_proba(self._matrix(rows))[:, 1]
        predictions = []

        for row, probability in zip(rows, probabilities):
            weak_probability = float(probability)
            predictions.append({
                "topic": row["topic"],
                "average_learning_score": row["average_learning_score"],
                "average_performance_score": row["average_performance_score"],
                "average_concept_score": row["average_concept_score"],
                "average_cognitive_score": row["average_cognitive_score"],
                "score_stddev": row["score_stddev"],
                "weak_student_count": row["weak_student_count"],
                "students_attempted": row["students_attempted"],
                "attempts": row["attempts"],
                "weak_student_share": row["weak_student_share"],
                "average_level_gap": row["average_level_gap"],
                "weak_probability": round(weak_probability, 3),
                "status": "WEAK" if weak_probability >= self.weak_probability_threshold else "REVIEW",
            })

        return sorted(
            predictions,
            key=lambda item: (item["weak_probability"], item["weak_student_share"], -item["average_learning_score"]),
            reverse=True,
        )

    def save(self):
        if not self.model_path or not self.pipeline:
            return

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "pipeline": self.pipeline,
            "feature_names": self.FEATURE_NAMES,
            "weak_probability_threshold": self.weak_probability_threshold,
        }, self.model_path)

    def load(self):
        payload = joblib.load(self.model_path)
        self.pipeline = payload["pipeline"]
        self.weak_probability_threshold = payload.get("weak_probability_threshold", self.weak_probability_threshold)
        return self

    def fit_from_results(self, results, weak_threshold=0.5, minimum_students=2, minimum_below_share=0.4):
        rows = build_topic_feature_rows(
            results,
            weak_threshold=weak_threshold,
            minimum_students=minimum_students,
            minimum_below_share=minimum_below_share,
        )

        if not rows:
            return []

        self.fit(rows)
        self.save()
        return self.predict(rows)
