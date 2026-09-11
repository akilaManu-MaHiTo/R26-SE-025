import csv

from app.evaluation.metrics import (
    accuracy,
    cohen_kappa,
    confusion_matrix,
    macro_f1,
    write_labeling_template,
)

PRED = ["SQL", "SQL", "SQL"]
LABEL = ["SQL", "SQL", "Schema Refinement"]


def test_accuracy():
    assert accuracy(PRED, LABEL) == 2 / 3


def test_macro_f1_perfect_is_one():
    assert macro_f1(["SQL", "SQL"], ["SQL", "SQL"], ["SQL"]) == 1.0


def test_confusion_matrix_shape():
    matrix = confusion_matrix(PRED, LABEL, ["SQL", "Schema Refinement"])
    assert len(matrix) == 2
    assert len(matrix[0]) == 2


def test_cohen_kappa_perfect_agreement():
    assert cohen_kappa(["SQL", "SQL"], ["SQL", "SQL"]) == 1.0


def test_write_labeling_template(tmp_path):
    path = str(tmp_path / "labels.csv")
    write_labeling_template(
        [{"question_id": "q1", "question_text": "Write SQL", "part": "a"}],
        path,
    )
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["question_id"] == "q1"
    assert "topic_label" in rows[0]