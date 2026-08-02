import csv
import hashlib
import io
import json
import os
import shutil
import unittest
from contextlib import contextmanager, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from src.analysis.training.prepare_bloom_dataset import (
    build_review_records,
    build_training,
    build_training_records,
    main,
    normalize_question,
    prepare_review,
    question_group_id,
    read_csv_rows,
    validate_source_rows,
)
from src.analysis.scoring.cognitive_bloom_model import load_tabular_dataset


@contextmanager
def workspace_temp_directory():
    path = Path("tests") / "_bloom_dataset_tmp"
    if path.exists():
        shutil.rmtree(path)
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


def source_row(**overrides):
    row = {
        "id": "1",
        "subject": "Computer Science",
        "topic": "Databases",
        "subtopic": "Transactions",
        "question": "Explain ACID?",
        "bloom_level": "Understand",
    }
    row.update(overrides)
    return row


def review_row(question, approval):
    normalized = normalize_question(question)
    return {
        "group_id": question_group_id(normalized),
        "question": question,
        "normalized_question": normalized,
        "source_row_count": "1",
        "observed_labels": "remember",
        "label_counts": '{"remember": 1}',
        "subjects": "Computer Science",
        "topics": "Databases",
        "subtopics": "Transactions",
        "source_ids": "1",
        "approved_bloom_level": approval,
        "review_status": "approved" if approval else "needs_review",
        "review_notes": "",
    }


class BloomDatasetPreparationTests(unittest.TestCase):
    def test_normalize_question_collapses_spacing_and_case(self):
        self.assertEqual(
            normalize_question("  Explain   ACID?  "),
            "explain acid?",
        )

    def test_question_group_id_is_stable(self):
        self.assertEqual(
            question_group_id("explain acid?"),
            question_group_id(normalize_question(" Explain  ACID? ")),
        )

    def test_validate_source_rows_rejects_missing_required_column(self):
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            validate_source_rows([{"id": "1", "question": "Explain ACID?"}])

    def test_validate_source_rows_rejects_empty_question(self):
        with self.assertRaisesRegex(ValueError, "empty question"):
            validate_source_rows([source_row(question="   ")])

    def test_validate_source_rows_rejects_invalid_bloom_label(self):
        with self.assertRaisesRegex(ValueError, "unsupported Bloom label"):
            validate_source_rows([source_row(bloom_level="Invent")])

    def test_conflicting_labels_are_grouped_without_selecting_one(self):
        rows = [
            source_row(id="2", bloom_level="Remember", topic="Architecture"),
            source_row(id="1", question=" explain   acid? ", bloom_level="Analyze"),
        ]

        review = build_review_records(rows)

        self.assertEqual(len(review), 1)
        self.assertEqual(review[0]["approved_bloom_level"], "")
        self.assertEqual(review[0]["review_status"], "needs_review")
        self.assertEqual(review[0]["observed_labels"], "analyze|remember")
        self.assertEqual(
            review[0]["label_counts"],
            '{"analyze": 1, "remember": 1}',
        )
        self.assertEqual(review[0]["source_ids"], "1|2")
        self.assertEqual(review[0]["topics"], "Architecture|Databases")


    def test_existing_review_is_preserved(self):
        existing = [review_row("Explain ACID?", "Understand")]
        existing[0]["review_notes"] = "Checked by lecturer"

        review = build_review_records([source_row()], existing_reviews=existing)

        self.assertEqual(review[0]["approved_bloom_level"], "understand")
        self.assertEqual(review[0]["review_status"], "approved")
        self.assertEqual(review[0]["review_notes"], "Checked by lecturer")


    def test_training_rows_include_only_valid_approvals(self):
        reviews = [
            review_row("Explain ACID?", "Remember"),
            review_row("Compare SQL and NoSQL.", ""),
        ]

        result = build_training_records(reviews)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["bloom_level"], "remember")
        self.assertEqual(result[0]["review_status"], "approved")

    def test_invalid_nonblank_approval_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid approved Bloom label"):
            build_training_records([review_row("Explain ACID?", "Invent")])

    def test_complete_review_can_be_required(self):
        with self.assertRaisesRegex(ValueError, "review is incomplete"):
            build_training_records(
                [review_row("Explain ACID?", "")],
                require_complete=True,
            )

    def test_duplicate_review_group_ids_are_rejected(self):
        row = review_row("Explain ACID?", "Remember")
        with self.assertRaisesRegex(ValueError, "Duplicate review group_id"):
            build_training_records([row, dict(row)])

    def test_mismatched_review_group_id_is_rejected(self):
        row = review_row("Explain ACID?", "Remember")
        row["group_id"] = "bloom-not-the-question-hash"
        with self.assertRaisesRegex(ValueError, "mismatched group_id"):
            build_training_records([row])


    def test_prepare_review_writes_reconciled_outputs_without_changing_source(self):
        with workspace_temp_directory() as temporary_path:
            source_path = temporary_path / "source.csv"
            output_dir = temporary_path / "processed"
            source_rows = [
                source_row(id="1", bloom_level="Remember"),
                source_row(id="2", question=" explain   acid? ", bloom_level="Analyze"),
                source_row(
                    id="3",
                    question="Compare SQL and NoSQL.",
                    bloom_level="Analyze",
                    subtopic="NoSQL",
                ),
            ]
            with source_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(source_rows[0]))
                writer.writeheader()
                writer.writerows(source_rows)
            source_before = source_path.read_bytes()
            checksum_before = hashlib.sha256(source_before).hexdigest()

            audit = prepare_review(source_path, output_dir)

            self.assertEqual(source_path.read_bytes(), source_before)
            self.assertEqual(audit["input_sha256"], checksum_before)
            review_rows = load_tabular_dataset(
                output_dir / "dataset_v1_bloom_review.csv"
            )
            training_rows = load_tabular_dataset(
                output_dir / "dataset_v1_bloom_train.csv"
            )
            saved_audit = json.loads(
                (output_dir / "dataset_v1_bloom_audit.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(review_rows), 2)
            self.assertEqual(len(training_rows), 0)
            self.assertEqual(saved_audit, audit)
            self.assertEqual(audit["source_rows"], 3)
            self.assertEqual(audit["unique_normalized_questions"], 2)
            self.assertEqual(audit["conflicting_question_groups"], 1)
            self.assertEqual(audit["rows_in_conflicting_groups"], 2)
            self.assertEqual(audit["approved_training_rows"], 0)
            self.assertEqual(audit["excluded_unreviewed_groups"], 2)


    def test_build_training_writes_only_the_approved_subset(self):
        with workspace_temp_directory() as temporary_path:
            source_path = temporary_path / "source.csv"
            output_dir = temporary_path / "processed"
            source_rows = [
                source_row(id="1", bloom_level="Remember"),
                source_row(
                    id="2",
                    question="Compare SQL and NoSQL.",
                    bloom_level="Analyze",
                    subtopic="NoSQL",
                ),
            ]
            with source_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(source_rows[0]))
                writer.writeheader()
                writer.writerows(source_rows)
            prepare_review(source_path, output_dir)
            review_path = output_dir / "dataset_v1_bloom_review.csv"
            review_rows = load_tabular_dataset(review_path)
            review_rows[0]["approved_bloom_level"] = "Remember"
            review_rows[0]["review_notes"] = "Lecturer checked"
            with review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(review_rows[0]))
                writer.writeheader()
                writer.writerows(review_rows)

            audit = build_training(review_path, output_dir)

            training_rows = load_tabular_dataset(
                output_dir / "dataset_v1_bloom_train.csv"
            )
            self.assertEqual(len(training_rows), 1)
            self.assertEqual(training_rows[0]["bloom_level"], "remember")
            self.assertEqual(training_rows[0]["review_notes"], "Lecturer checked")
            self.assertEqual(audit["approved_training_rows"], 1)
            self.assertEqual(audit["excluded_unreviewed_groups"], 1)
            self.assertEqual(
                audit["approved_training_label_distribution"],
                {"remember": 1},
            )

    def test_cli_complete_review_requirement_exits_nonzero(self):
        with workspace_temp_directory() as temporary_path:
            source_path = temporary_path / "source.csv"
            output_dir = temporary_path / "processed"
            row = source_row()
            with source_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
            prepare_review(source_path, output_dir)

            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main([
                        "build-training",
                        "--review-file",
                        str(output_dir / "dataset_v1_bloom_review.csv"),
                        "--output-dir",
                        str(output_dir),
                        "--require-complete-review",
                    ])
            self.assertNotEqual(raised.exception.code, 0)


    def test_build_training_rejects_review_queue_from_another_audit(self):
        with workspace_temp_directory() as temporary_path:
            source_path = temporary_path / "source.csv"
            output_dir = temporary_path / "processed"
            row = source_row()
            with source_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
            prepare_review(source_path, output_dir)

            foreign = review_row("Compare SQL and NoSQL.", "Analyze")
            review_path = output_dir / "dataset_v1_bloom_review.csv"
            with review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(foreign))
                writer.writeheader()
                writer.writerow(foreign)

            with self.assertRaisesRegex(ValueError, "does not match its audit"):
                build_training(review_path, output_dir)


    def test_approved_review_requires_nonblank_question(self):
        row = review_row("Explain ACID?", "Remember")
        row["question"] = "   "
        with self.assertRaisesRegex(ValueError, "empty question"):
            build_training_records([row])

    def test_review_requires_positive_source_row_count(self):
        row = review_row("Explain ACID?", "Remember")
        row["source_row_count"] = "0"
        with self.assertRaisesRegex(ValueError, "positive source_row_count"):
            build_training_records([row])

    def test_review_question_must_match_normalized_question(self):
        row = review_row("Explain ACID?", "Remember")
        row["question"] = "Compare SQL and NoSQL."
        with self.assertRaisesRegex(ValueError, "question does not match"):
            build_training_records([row])


    def test_prepare_review_rolls_back_all_outputs_when_commit_fails(self):
        with workspace_temp_directory() as temporary_path:
            source_path = temporary_path / "source.csv"
            output_dir = temporary_path / "processed"
            initial_row = source_row()
            with source_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(initial_row))
                writer.writeheader()
                writer.writerow(initial_row)
            prepare_review(source_path, output_dir)
            output_paths = [
                output_dir / "dataset_v1_bloom_review.csv",
                output_dir / "dataset_v1_bloom_train.csv",
                output_dir / "dataset_v1_bloom_audit.json",
            ]
            original_outputs = {path: path.read_bytes() for path in output_paths}

            second_row = source_row(
                id="2",
                question="Compare SQL and NoSQL.",
                bloom_level="Analyze",
            )
            with source_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(initial_row))
                writer.writeheader()
                writer.writerows([initial_row, second_row])

            real_replace = os.replace

            failure_raised = {"value": False}

            def fail_audit_commit(source, destination):
                destination_path_value = Path(destination)
                if (
                    not failure_raised["value"]
                    and destination_path_value.name == "dataset_v1_bloom_audit.json"
                ):
                    failure_raised["value"] = True
                    raise OSError("simulated audit replacement failure")
                return real_replace(source, destination)

            with patch(
                "src.analysis.training.prepare_bloom_dataset.os.replace",
                side_effect=fail_audit_commit,
            ):
                with self.assertRaisesRegex(OSError, "simulated audit"):
                    prepare_review(source_path, output_dir)

            for path, original_bytes in original_outputs.items():
                self.assertEqual(path.read_bytes(), original_bytes)


    def test_read_csv_rows_rejects_malformed_quoting(self):
        with workspace_temp_directory() as temporary_path:
            malformed_path = temporary_path / "malformed.csv"
            malformed_path.write_text(
                'id,question\n1,"unterminated\n',
                encoding="utf-8",
            )
            with self.assertRaises(csv.Error):
                read_csv_rows(malformed_path)

    def test_review_missing_required_field_is_rejected(self):
        row = review_row("Explain ACID?", "Remember")
        del row["question"]
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            build_training_records([row])


if __name__ == "__main__":
    unittest.main()
