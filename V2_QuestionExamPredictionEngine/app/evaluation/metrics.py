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