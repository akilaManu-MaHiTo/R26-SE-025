"""Synthetic fixtures check validation, not model accuracy or holdout independence."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "holdout_audit", Path(__file__).resolve().parents[1] / "scripts/audit_bloom_evidence.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def labeled_question():
    return dict(question_id="exam-1-Q1", question_text="Explain transaction isolation.",
                source_reference="unseen-exam.pdf page 1", rater_a_id="lecturer-a",
                rater_a_label="Understand", rater_b_id="lecturer-b",
                rater_b_label="Understand", adjudicator_id="", bloom_label="Understand")


def test_holdout_accepts_reviewed_unseen_question():
    rows = [labeled_question()]
    assert audit.validate_holdout(rows, ["Define SQL"]) == rows


@pytest.mark.parametrize("field,value", [
    ("question_text", ""), ("question_id", ""), ("source_reference", ""),
    ("rater_a_id", ""), ("rater_b_id", "lecturer-a"),
    ("rater_a_label", "BT2"), ("bloom_label", "invented"),
    ("rater_b_label", "Analyze"), ("bloom_label", "Apply"),
])
def test_holdout_rejects_missing_or_unresolved_labels(field, value):
    row = labeled_question()
    row[field] = value
    with pytest.raises(ValueError):
        audit.validate_holdout([row], [])


def test_holdout_accepts_recorded_adjudication():
    row = labeled_question()
    row.update(rater_b_label="Apply", adjudicator_id="lead-lecturer", bloom_label="Analyze")
    assert audit.validate_holdout([row], []) == [row]


@pytest.mark.parametrize("text", ["Explain transaction isolation.", " EXPLAIN  transaction\nisolation! "])
def test_holdout_rejects_training_overlap_despite_formatting(text):
    with pytest.raises(ValueError, match="overlap"):
        audit.validate_holdout([labeled_question()], [text])


def test_holdout_rejects_duplicates_and_empty_sets():
    with pytest.raises(ValueError):
        audit.validate_holdout([], [])
    row = labeled_question()
    for duplicate in [dict(row, question_id="other"), dict(row, question_text="Different text")]:
        with pytest.raises(ValueError, match="Duplicate"):
            audit.validate_holdout([row, duplicate], [])


@pytest.mark.parametrize("filename", ["independent_holdout_template.csv", "final_exam_holdout_candidates.csv"])
def test_cli_rejects_unlabeled_sets_before_loading_model(filename):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/evaluate_bloom_holdout.py"),
         str(root / "datasets/bloom_dataset/bloom" / filename), "--evaluate"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "Holdout rejected:" in result.stderr
    assert result.stdout == ""


def test_prepared_candidates_remain_unlabeled_and_disjoint_from_source():
    import csv
    root = Path(__file__).resolve().parents[1] / "datasets/bloom_dataset/bloom"
    with (root / "final_exam_holdout_candidates.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    with (root / "blooms_taxonomy_dataset.csv").open(encoding="utf-8-sig", newline="") as f:
        excluded = {audit.holdout_key(r["Questions"]) for r in csv.DictReader(f)}
    assert len(rows) == 14
    assert all(not r["bloom_label"] and not r["rater_a_label"] and not r["rater_b_label"] for r in rows)
    assert not {audit.holdout_key(r["question_text"]) for r in rows} & excluded
    assert all(r["source_reference"] for r in rows)


def test_evaluation_reports_real_metrics_with_model_boundary_stubbed(monkeypatch, capsys):
    import json
    from types import ModuleType

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("holdout_cli", scripts / "evaluate_bloom_holdout.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    rows = []
    for i, label in enumerate(["Remember", "Remember", "Apply"]):
        row = labeled_question()
        row.update(question_id=str(i), question_text=f"Unseen question {i}",
                   rater_a_label=label, rater_b_label=label, bloom_label=label)
        rows.append(row)
    monkeypatch.setattr(cli, "read_rows", lambda p: rows if p.name == "holdout.csv" else [{"Questions": "Training example"}])
    monkeypatch.setattr(cli, "sha256", lambda p: "fixture-hash")
    received = []
    model = ModuleType("app.classifier.bloom_classifier")
    model._model_dir = lambda: scripts.parent / "models/bloom_modernbert"
    def predict(texts):
        received.extend(texts)
        return [{"level": level} for level in ["Remember", "Apply", "Apply"]]
    model.predict_bloom_batch = predict
    monkeypatch.setitem(sys.modules, "app.classifier.bloom_classifier", model)
    monkeypatch.setattr(sys, "argv", ["evaluate_bloom_holdout.py", "holdout.csv", "--evaluate"])
    cli.main()
    report = json.loads(capsys.readouterr().out)
    assert received == [r["question_text"] for r in rows]
    assert report["metrics"]["accuracy"] == 2 / 3
    assert report["metrics"]["macro_f1_all_six"] == pytest.approx(2 / 9)
    assert report["metrics"]["confusion_rows_gold_columns_prediction"][0][2] == 1
    assert [r["question_id"] for r in report["predictions"]] == ["0", "1", "2"]
