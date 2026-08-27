import csv
from collections import Counter


def accuracy(predictions: list[str], labels: list[str]) -> float:
    if not predictions:
        return 0.0
    correct = sum(1 for p, l in zip(predictions, labels) if p == l)
    return correct / len(predictions)


def confusion_matrix(
    predictions: list[str], labels: list[str], classes: list[str]
) -> list[list[int]]:
    index = {c: i for i, c in enumerate(classes)}
    matrix = [[0 for _ in classes] for _ in classes]
    for p, l in zip(predictions, labels):
        if p in index and l in index:
            matrix[index[l]][index[p]] += 1
    return matrix


def _per_class_f1(matrix: list[list[int]], classes: list[str]) -> list[float]:
    f1s = []
    for c, _ in enumerate(classes):
        tp = matrix[c][c]
        fp = sum(matrix[r][c] for r in range(len(classes))) - tp
        fn = sum(matrix[c][k] for k in range(len(classes))) - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        f1s.append(f1)
    return f1s


def macro_f1(
    predictions: list[str], labels: list[str], classes: list[str] | None = None
) -> float:
    classes = classes or sorted(set(labels) | set(predictions))
    if not classes:
        return 0.0
    matrix = confusion_matrix(predictions, labels, classes)
    f1s = _per_class_f1(matrix, classes)
    return sum(f1s) / len(f1s)


def cohen_kappa(rater_a: list[str], rater_b: list[str]) -> float:
    n = len(rater_a)
    if n == 0:
        return 0.0
    observed = sum(1 for a, b in zip(rater_a, rater_b) if a == b) / n
    ca = Counter(rater_a)
    cb = Counter(rater_b)
    expected = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1.0 - expected) if expected != 1.0 else 0.0


def write_labeling_template(question_parts: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "question_id", "question_text", "part",
                "topic_label", "bloom_label", "question_type",
                "key_concepts", "notes",
            ],
        )
        writer.writeheader()
        for q in question_parts:
            writer.writerow(
                {
                    "question_id": q.get("question_id", ""),
                    "question_text": q.get("question_text", ""),
                    "part": q.get("part", ""),
                    "topic_label": "",
                    "bloom_label": "",
                    "question_type": "",
                    "key_concepts": "",
                    "notes": "",
                }
            )


# --- Weakness-Aligned Usefulness labeling (research task: help lecturer generate useful questions) ---

USEFULNESS_TEMPLATE_FIELDS = [
    "question_id",
    "question_text",
    "canonical_topic",
    "bloom_level",
    "difficulty",
    "source_type",
    "analytics_snapshot_id",
    "weakness_context_json",
    "recommendation_score",
    "priority",
    "lecture_coverage",
    "tutorial_evidence",
    "exam_relevance",
    "bloom_gap",
    "rating_overall",        # 1..5
    "rating_weakness_fit",   # 1..5
    "rating_curriculum_fit", # 1..5
    "rating_difficulty_fit", # 1..5
    "rating_clarity",        # 1..5
    "would_use",             # TRUE/FALSE
    "would_edit",            # TRUE/FALSE
    "annotator_id",
    "comments",
]


def write_usefulness_labeling_template(
    recommendations: list[dict],
    analytics_snapshot_id: str,
    weakness_context: dict[str, float] | None,
    path: str,
    annotator_id: str = "",
) -> None:
    """Write lecturer usefulness rating sheet for a ranked recommendation set.

    Args:
        recommendations: output of app.services.recommendation.recommend_questions
            (each dict must have question_id, text, canonical_topic, bloom_level, etc.)
        analytics_snapshot_id: e.g. "IT2040@Final2023" - links ratings to cohort
        weakness_context: {canonical_topic: weakness 0..1} for audit column
        path: output CSV path
        annotator_id: pre-fill if known, else blank for rater to fill
    """
    import json as _json

    weakness_json = _json.dumps(weakness_context or {}, ensure_ascii=False)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=USEFULNESS_TEMPLATE_FIELDS)
        writer.writeheader()
        for rec in recommendations:
            writer.writerow(
                {
                    "question_id": rec.get("question_id", ""),
                    "question_text": rec.get("text", "")[:2000],
                    "canonical_topic": rec.get("canonical_topic", ""),
                    "bloom_level": rec.get("bloom_level", ""),
                    "difficulty": rec.get("difficulty", ""),
                    "source_type": rec.get("source_type", ""),
                    "analytics_snapshot_id": analytics_snapshot_id,
                    "weakness_context_json": weakness_json,
                    "recommendation_score": rec.get("recommendation_score", ""),
                    "priority": rec.get("priority", ""),
                    "lecture_coverage": rec.get("lecture_coverage", ""),
                    "tutorial_evidence": rec.get("tutorial_evidence", ""),
                    "exam_relevance": rec.get("exam_relevance", ""),
                    "bloom_gap": rec.get("bloom_gap", ""),
                    "rating_overall": "",
                    "rating_weakness_fit": "",
                    "rating_curriculum_fit": "",
                    "rating_difficulty_fit": "",
                    "rating_clarity": "",
                    "would_use": "",
                    "would_edit": "",
                    "annotator_id": annotator_id,
                    "comments": "",
                }
            )


def ndcg_at_k(ranked_would_use: list[bool], k: int | None = None) -> float:
    """NDCG@k for binary relevance (would_use). Ideal = all True first."""
    import math as _math

    if not ranked_would_use:
        return 0.0
    k = k or len(ranked_would_use)
    ranked = ranked_would_use[:k]
    dcg = sum((1.0 / _math.log2(i + 2)) for i, rel in enumerate(ranked) if rel)
    ideal = sorted(ranked, reverse=True)
    idcg = sum((1.0 / _math.log2(i + 2)) for i, rel in enumerate(ideal) if rel)
    return dcg / idcg if idcg else 0.0


def precision_at_k(ranked_would_use: list[bool], k: int) -> float:
    if k <= 0 or not ranked_would_use:
        return 0.0
    topk = ranked_would_use[:k]
    return sum(1 for x in topk if x) / len(topk)