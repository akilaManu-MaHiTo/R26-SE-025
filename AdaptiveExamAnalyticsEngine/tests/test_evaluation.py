import csv
import math
import pytest

from app.evaluation.metrics import (
    accuracy,
    cohen_kappa,
    confusion_matrix,
    macro_f1,
    ndcg_at_k,
    write_labeling_template,
)

PRED = ["SQL", "SQL", "SQL"]
LABEL = ["SQL", "SQL", "Schema Refinement"]


@pytest.mark.parametrize("predictions,labels", [(["A"], ["A", "B"]), ([], ["A"]), (["A"], [])])
@pytest.mark.parametrize("metric", [accuracy, macro_f1, cohen_kappa,
    lambda p, l: confusion_matrix(p, l, ["A", "B"])])
def test_metrics_reject_unpaired_observations(metric, predictions, labels):
    with pytest.raises(ValueError, match="equal length"):
        metric(predictions, labels)


@pytest.mark.parametrize("classes", [["A"], ["A", "A", "B"], []])
def test_confusion_matrix_rejects_invalid_class_universe(classes):
    with pytest.raises(ValueError):
        confusion_matrix(["A"], ["B"], classes)


def test_ndcg_uses_all_candidates_for_ideal_ranking():
    assert ndcg_at_k([True, False, True], 2) == pytest.approx(1 / (1 + 1 / math.log2(3)))


def test_ndcg_cutoffs_and_empty_relevance():
    assert ndcg_at_k([True], 0) == 0
    assert ndcg_at_k([], 3) == 0
    assert ndcg_at_k([False, False], 2) == 0
    assert ndcg_at_k([True, True], 10) == 1
    assert ndcg_at_k([False, True]) == pytest.approx(1 / math.log2(3))
    with pytest.raises(ValueError):
        ndcg_at_k([True], -1)


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
