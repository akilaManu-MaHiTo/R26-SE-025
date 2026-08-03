import csv
import importlib
import io
import json
import os
import shutil
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape
from zipfile import ZipFile


@contextmanager
def workspace_temp_directory():
    path = Path("tests") / "_pone_bloom_dataset_tmp"
    if path.exists():
        shutil.rmtree(path)
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


def load_module(test_case):
    try:
        return importlib.import_module(
            "src.analysis.training.prepare_pone_bloom_dataset"
        )
    except ModuleNotFoundError:
        test_case.fail("prepare_pone_bloom_dataset module is missing")


def write_docx(path, paragraphs, include_document_xml=True):
    body = "".join(
        f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>"
        for text in paragraphs
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>'
        f"{body}</w:body></w:document>"
    )
    with ZipFile(path, "w") as archive:
        if include_document_xml:
            archive.writestr("word/document.xml", xml)


def six_section_paragraphs():
    return [
        "Note: fixture metadata",
        "Knowledge",
        "Recall a fact.",
        "Comprehension",
        "Explain a fact.",
        "Application",
        "Use the rule.",
        "Analysis",
        "Compare the cases.",
        "Synthesis",
        "Design a solution.",
        "Evaluation",
        "Judge the solution.",
    ]


def source_record(
    question="Explain a complete idea.",
    paragraph=2,
    label="remember",
    legacy="knowledge",
    source_document="fixture.docx",
):
    return {
        "question": question,
        "original_question": question,
        "bloom_level": label,
        "legacy_bloom_level": legacy,
        "source_document": source_document,
        "source_paragraph": paragraph,
    }


def assigned_row(row_number, label, group_id=None):
    group_id = group_id or f"group-{label}-{row_number}"
    return {
        "row_id": f"row-{label}-{row_number}",
        "question_group_id": group_id,
        "question": f"Question {label} {row_number}",
        "original_question": f"Question {label} {row_number}",
        "bloom_level": label,
        "legacy_bloom_level": label,
        "source_document": "fixture.docx",
        "source_paragraph": row_number,
        "quality_flags": "none",
    }


def write_fixture_sources(directory):
    source_one = directory / "source-one.docx"
    source_two = directory / "source-two.docx"
    first = six_section_paragraphs()
    second = six_section_paragraphs()
    for index in (2, 4, 6, 8, 10, 12):
        first[index] = f"First source {first[index]}"
        second[index] = f"Second source {second[index]}"
    write_docx(source_one, first)
    write_docx(source_two, second)
    return source_one, source_two


FIXTURE_LABEL_COUNTS = {label: 2 for label in (
    "remember", "understand", "apply", "analyze", "create", "evaluate"
)}


class PoneBloomDatasetPreparationTests(unittest.TestCase):
    def test_extract_docx_maps_all_legacy_headings(self):
        module = load_module(self)
        with workspace_temp_directory() as temporary_path:
            source_path = temporary_path / "fixture.docx"
            write_docx(source_path, six_section_paragraphs())

            rows = module.extract_docx_questions(source_path)

        self.assertEqual(
            [row["bloom_level"] for row in rows],
            [
                "remember",
                "understand",
                "apply",
                "analyze",
                "create",
                "evaluate",
            ],
        )
        self.assertEqual(rows[0]["source_paragraph"], 2)
        self.assertEqual(rows[0]["legacy_bloom_level"], "knowledge")
        self.assertEqual(rows[0]["source_document"], "fixture.docx")

    def test_extract_docx_preserves_original_and_normalizes_model_text(self):
        module = load_module(self)
        paragraphs = six_section_paragraphs()
        paragraphs[2] = "  Recall   the ﬁrst fact.  "
        with workspace_temp_directory() as temporary_path:
            source_path = temporary_path / "fixture.docx"
            write_docx(source_path, paragraphs)

            rows = module.extract_docx_questions(source_path)

        self.assertEqual(rows[0]["original_question"], "  Recall   the ﬁrst fact.  ")
        self.assertEqual(rows[0]["question"], "Recall the first fact.")

    def test_extract_docx_rejects_question_before_first_heading(self):
        module = load_module(self)
        paragraphs = six_section_paragraphs()
        paragraphs[0] = "Unlabeled question"
        with workspace_temp_directory() as temporary_path:
            source_path = temporary_path / "fixture.docx"
            write_docx(source_path, paragraphs)

            with self.assertRaisesRegex(ValueError, "before the first Bloom heading"):
                module.extract_docx_questions(source_path)

    def test_extract_docx_rejects_missing_bloom_heading(self):
        module = load_module(self)
        paragraphs = six_section_paragraphs()[:-2]
        with workspace_temp_directory() as temporary_path:
            source_path = temporary_path / "fixture.docx"
            write_docx(source_path, paragraphs)

            with self.assertRaisesRegex(ValueError, "missing Bloom headings: evaluation"):
                module.extract_docx_questions(source_path)

    def test_extract_docx_rejects_missing_document_xml(self):
        module = load_module(self)
        with workspace_temp_directory() as temporary_path:
            source_path = temporary_path / "fixture.docx"
            write_docx(source_path, [], include_document_xml=False)

            with self.assertRaisesRegex(ValueError, "word/document.xml"):
                module.extract_docx_questions(source_path)


    def test_build_rows_keeps_duplicate_questions_and_flags_them(self):
        module = load_module(self)
        extracted = [
            source_record("Explain the diagram...", paragraph=2),
            source_record("Explain the diagram...", paragraph=3),
        ]

        with patch.object(module, "extract_docx_questions", return_value=extracted):
            rows = module.build_rows([Path("fixture.docx")])

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0]["question_group_id"],
            rows[1]["question_group_id"],
        )
        self.assertNotEqual(rows[0]["row_id"], rows[1]["row_id"])
        self.assertEqual(
            rows[0]["quality_flags"],
            "placeholder|missing_context|very_short|exact_duplicate",
        )

    def test_quality_flags_detect_short_and_language_error_questions(self):
        module = load_module(self)

        self.assertEqual(
            module.quality_flags("Define morphology"),
            ("very_short",),
        )
        self.assertEqual(
            module.quality_flags("How much data can be stored in the cach memory"),
            ("possible_language_error",),
        )
        self.assertEqual(
            module.quality_flags("Explain how evaporation changes water."),
            (),
        )

    def test_assign_grouped_splits_is_deterministic_and_keeps_groups_together(self):
        module = load_module(self)
        labels = (
            "remember",
            "understand",
            "apply",
            "analyze",
            "create",
            "evaluate",
        )
        rows = [
            assigned_row(row_number, label)
            for label in labels
            for row_number in range(12)
        ]
        duplicate = dict(rows[0])
        duplicate["row_id"] = "row-remember-duplicate"
        duplicate["source_paragraph"] = 1000
        rows.append(duplicate)

        first = module.assign_grouped_splits(rows, seed=42)
        second = module.assign_grouped_splits(rows, seed=42)

        self.assertEqual(first, second)
        self.assertEqual(len(first), len(rows))
        self.assertEqual(
            {row["split"] for row in first},
            {"train", "validation", "test"},
        )
        for group_id in {row["question_group_id"] for row in first}:
            self.assertEqual(
                len({
                    row["split"]
                    for row in first
                    if row["question_group_id"] == group_id
                }),
                1,
            )
        for label in labels:
            self.assertEqual(
                {row["split"] for row in first if row["bloom_level"] == label},
                {"train", "validation", "test"},
            )

    def test_assign_grouped_splits_rejects_conflicting_duplicate_labels(self):
        module = load_module(self)
        rows = [
            assigned_row(1, "remember", group_id="same-question"),
            assigned_row(2, "analyze", group_id="same-question"),
        ]

        with self.assertRaisesRegex(ValueError, "multiple Bloom labels"):
            module.assign_grouped_splits(rows)

    def test_build_dataset_writes_reconciled_loader_compatible_artifacts(self):
        module = load_module(self)
        with workspace_temp_directory() as temporary_path:
            source_one, source_two = write_fixture_sources(temporary_path)
            output_dir = temporary_path / "output"
            expected_source_counts = {
                source_one.name: 6,
                source_two.name: 6,
            }
            with (
                patch.object(module, "EXPECTED_SOURCE_COUNTS", expected_source_counts),
                patch.object(module, "EXPECTED_LABEL_COUNTS", FIXTURE_LABEL_COUNTS),
            ):
                audit = module.build_dataset(
                    [source_one, source_two], output_dir, seed=42
                )

            self.assertEqual(audit["pipeline_version"], "1.0.0")
            self.assertEqual(audit["total_rows"], 12)
            self.assertEqual(audit["label_distribution"], FIXTURE_LABEL_COUNTS)
            self.assertEqual(sum(audit["split_counts"].values()), 12)
            self.assertEqual(
                audit["source_documents"][0]["sha256"],
                module.sha256_file(source_one),
            )

            def read_csv(name):
                with (output_dir / name).open(
                    "r", encoding="utf-8", newline=""
                ) as handle:
                    return list(csv.DictReader(handle))

            full = read_csv("pone_bloom_full.csv")
            splits = [
                read_csv("pone_bloom_train.csv"),
                read_csv("pone_bloom_validation.csv"),
                read_csv("pone_bloom_test.csv"),
            ]
            split_rows = [row for rows in splits for row in rows]
            self.assertEqual(len(full), 12)
            self.assertEqual(
                {row["row_id"] for row in full},
                {row["row_id"] for row in split_rows},
            )
            self.assertEqual(len(split_rows), len({row["row_id"] for row in split_rows}))
            with (output_dir / "pone_bloom_audit.json").open(
                "r", encoding="utf-8"
            ) as handle:
                self.assertEqual(json.load(handle)["total_rows"], 12)

            from src.analysis.scoring.cognitive_bloom_model import load_tabular_dataset

            self.assertEqual(
                len(load_tabular_dataset(output_dir / "pone_bloom_full.csv")),
                12,
            )

    def test_validate_dataset_rejects_wrong_source_count(self):
        module = load_module(self)
        with workspace_temp_directory() as temporary_path:
            source_one, source_two = write_fixture_sources(temporary_path)
            rows = module.assign_grouped_splits(
                module.build_rows([source_one, source_two])
            )
            with patch.object(
                module,
                "EXPECTED_SOURCE_COUNTS",
                {source_one.name: 7, source_two.name: 6},
            ):
                audit = module.build_audit([source_one, source_two], rows)
                with self.assertRaisesRegex(ValueError, "expected 7"):
                    module.validate_dataset([source_one, source_two], rows, audit)

    def test_build_dataset_rolls_back_all_outputs_on_replace_failure(self):
        module = load_module(self)
        with workspace_temp_directory() as temporary_path:
            source_one, source_two = write_fixture_sources(temporary_path)
            output_dir = temporary_path / "output"
            output_dir.mkdir()
            names = (
                "pone_bloom_full.csv",
                "pone_bloom_train.csv",
                "pone_bloom_validation.csv",
                "pone_bloom_test.csv",
                "pone_bloom_quality_review.csv",
                "pone_bloom_audit.json",
            )
            for name in names:
                (output_dir / name).write_bytes(f"sentinel:{name}".encode())

            real_replace = os.replace
            failed = False

            def fail_audit_once(source, destination):
                nonlocal failed
                if Path(destination).name == "pone_bloom_audit.json" and not failed:
                    failed = True
                    raise OSError("simulated replace failure")
                return real_replace(source, destination)

            with (
                patch.object(
                    module,
                    "EXPECTED_SOURCE_COUNTS",
                    {source_one.name: 6, source_two.name: 6},
                ),
                patch.object(module, "EXPECTED_LABEL_COUNTS", FIXTURE_LABEL_COUNTS),
                patch(
                    "src.analysis.training.prepare_bloom_dataset.os.replace",
                    side_effect=fail_audit_once,
                ),
                self.assertRaisesRegex(OSError, "simulated replace failure"),
            ):
                module.build_dataset([source_one, source_two], output_dir)

            for name in names:
                self.assertEqual(
                    (output_dir / name).read_bytes(),
                    f"sentinel:{name}".encode(),
                )

    def test_cli_requires_two_distinct_inputs_and_prints_summary(self):
        module = load_module(self)
        with workspace_temp_directory() as temporary_path:
            source_one, source_two = write_fixture_sources(temporary_path)
            output_dir = temporary_path / "output"
            stdout = io.StringIO()
            with (
                patch.object(
                    module,
                    "EXPECTED_SOURCE_COUNTS",
                    {source_one.name: 6, source_two.name: 6},
                ),
                patch.object(module, "EXPECTED_LABEL_COUNTS", FIXTURE_LABEL_COUNTS),
                redirect_stdout(stdout),
            ):
                result = module.main([
                    "--input", str(source_one),
                    "--input", str(source_two),
                    "--output-dir", str(output_dir),
                ])
            self.assertEqual(result, 0)
            self.assertIn("Total rows: 12", stdout.getvalue())
            self.assertIn("Output directory:", stdout.getvalue())

            with self.assertRaises(SystemExit):
                module.main([
                    "--input", str(source_one),
                    "--input", str(source_one),
                    "--output-dir", str(output_dir),
                ])


if __name__ == "__main__":
    unittest.main()
