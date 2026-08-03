from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from src.analysis.training.prepare_bloom_dataset import (
    sha256_file,
    write_artifact_set_atomic,
)


LEGACY_TO_MODEL = {
    "knowledge": "remember",
    "comprehension": "understand",
    "application": "apply",
    "analysis": "analyze",
    "synthesis": "create",
    "evaluation": "evaluate",
}

VALID_BLOOM_LEVELS = tuple(LEGACY_TO_MODEL.values())

EXPECTED_SOURCE_COUNTS = {
    "pone.0230442.s001.docx": 141,
    "pone.0230442.s002.docx": 600,
}

EXPECTED_LABEL_COUNTS = {
    "remember": 126,
    "understand": 123,
    "apply": 115,
    "analyze": 123,
    "create": 130,
    "evaluate": 124,
}

PIPELINE_VERSION = "1.0.0"

CSV_FIELDNAMES = (
    "row_id",
    "question_group_id",
    "question",
    "original_question",
    "bloom_level",
    "legacy_bloom_level",
    "source_document",
    "source_paragraph",
    "quality_flags",
    "split",
)

QUALITY_REVIEW_FIELDNAMES = CSV_FIELDNAMES + (
    "review_status",
    "review_notes",
)

ARTIFACT_FILENAMES = {
    "full": "pone_bloom_full.csv",
    "train": "pone_bloom_train.csv",
    "validation": "pone_bloom_validation.csv",
    "test": "pone_bloom_test.csv",
    "quality_review": "pone_bloom_quality_review.csv",
    "audit": "pone_bloom_audit.json",
}

WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORD_PARAGRAPH = f"{{{WORD_NAMESPACE}}}p"
WORD_TEXT = f"{{{WORD_NAMESPACE}}}t"

FLAG_ORDER = (
    "placeholder",
    "missing_context",
    "very_short",
    "possible_language_error",
    "exact_duplicate",
)

PLACEHOLDER_RE = re.compile(r"_{2,}|\.{3,}|…")
MISSING_CONTEXT_RE = re.compile(
    r"\b(above|below|following|diagram|picture|graph|passage|questionnaire|"
    r"table|selected information|story|text|article)\b",
    re.IGNORECASE,
)
LANGUAGE_ERROR_RE = re.compile(
    r"\b(the the|pictoral|cach |does .+ stands|did he took|"
    r"difference parts|a eukaryotic)\b",
    re.IGNORECASE,
)
WORD_TOKEN_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)


def normalize_question(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    return " ".join(text.split())


def _document_root(path: Path) -> ET.Element:
    try:
        with ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except KeyError as error:
        raise ValueError(f"DOCX has no word/document.xml: {path}") from error
    return ET.fromstring(xml)


def _paragraph_text(paragraph: ET.Element) -> str:
    return "".join(
        element.text or ""
        for element in paragraph.iter(WORD_TEXT)
    )


def extract_docx_questions(path: Path) -> list[dict[str, object]]:
    path = Path(path)
    root = _document_root(path)
    current_legacy_level = None
    seen_headings = set()
    rows = []

    for paragraph_index, paragraph in enumerate(root.iter(WORD_PARAGRAPH)):
        original_text = _paragraph_text(paragraph)
        normalized_text = normalize_question(original_text)
        if not normalized_text:
            continue

        heading = normalized_text.rstrip(":").casefold()
        if heading in LEGACY_TO_MODEL:
            current_legacy_level = heading
            seen_headings.add(heading)
            continue

        if current_legacy_level is None:
            if normalized_text.casefold().startswith("note:"):
                continue
            raise ValueError(
                f"Question appears before the first Bloom heading at "
                f"paragraph {paragraph_index}: {normalized_text}"
            )

        rows.append({
            "question": normalized_text,
            "original_question": original_text,
            "bloom_level": LEGACY_TO_MODEL[current_legacy_level],
            "legacy_bloom_level": current_legacy_level,
            "source_document": path.name,
            "source_paragraph": paragraph_index,
        })

    missing_headings = [
        heading
        for heading in LEGACY_TO_MODEL
        if heading not in seen_headings
    ]
    if missing_headings:
        raise ValueError(
            "DOCX is missing Bloom headings: " + ", ".join(missing_headings)
        )

    return rows


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def quality_flags(question: str) -> tuple[str, ...]:
    flags = []
    if PLACEHOLDER_RE.search(question):
        flags.append("placeholder")
    if MISSING_CONTEXT_RE.search(question):
        flags.append("missing_context")
    if len(WORD_TOKEN_RE.findall(question)) < 4:
        flags.append("very_short")
    if LANGUAGE_ERROR_RE.search(question):
        flags.append("possible_language_error")
    return tuple(flags)


def build_rows(source_paths: Sequence[Path]) -> list[dict[str, object]]:
    extracted_rows = []
    for source_path in source_paths:
        extracted_rows.extend(extract_docx_questions(Path(source_path)))

    rows = []
    group_counts = defaultdict(int)
    for extracted in extracted_rows:
        question = str(extracted["question"])
        group_id = _stable_id("pone-question", question.casefold())
        group_counts[group_id] += 1
        row = dict(extracted)
        row["row_id"] = _stable_id(
            "pone-row",
            f"{row['source_document']}:{row['source_paragraph']}",
        )
        row["question_group_id"] = group_id
        rows.append(row)

    for row in rows:
        flags = list(quality_flags(str(row["question"])))
        if group_counts[str(row["question_group_id"])] > 1:
            flags.append("exact_duplicate")
        row["quality_flags"] = "|".join(flags) if flags else "none"

    return rows


def _ordered_group_ids(group_ids: Sequence[str], seed: int) -> list[str]:
    return sorted(
        group_ids,
        key=lambda group_id: hashlib.sha256(
            f"{seed}:{group_id}".encode("utf-8")
        ).hexdigest(),
    )


def assign_grouped_splits(
    rows: list[dict[str, object]],
    seed: int = 42,
) -> list[dict[str, object]]:
    grouped_rows = defaultdict(list)
    for row in rows:
        grouped_rows[str(row["question_group_id"])].append(row)

    groups_by_label = defaultdict(list)
    for group_id, group in grouped_rows.items():
        labels = {str(row["bloom_level"]) for row in group}
        if len(labels) != 1:
            raise ValueError(
                f"Question group {group_id} has multiple Bloom labels: "
                + ", ".join(sorted(labels))
            )
        groups_by_label[next(iter(labels))].append(group_id)

    group_splits = {}
    for label, group_ids in groups_by_label.items():
        ordered = _ordered_group_ids(group_ids, seed)
        if len(ordered) >= 3:
            evaluation_count = max(1, round(len(ordered) * 0.15))
            evaluation_count = min(evaluation_count, (len(ordered) - 1) // 2)
        else:
            evaluation_count = 0

        validation_end = evaluation_count
        test_end = validation_end + evaluation_count
        for group_id in ordered[:validation_end]:
            group_splits[group_id] = "validation"
        for group_id in ordered[validation_end:test_end]:
            group_splits[group_id] = "test"
        for group_id in ordered[test_end:]:
            group_splits[group_id] = "train"

    return [
        {**row, "split": group_splits[str(row["question_group_id"])]}
        for row in rows
    ]


def _label_counts(rows: Sequence[dict[str, object]]) -> dict[str, int]:
    counts = Counter(str(row["bloom_level"]) for row in rows)
    return {label: counts.get(label, 0) for label in VALID_BLOOM_LEVELS}


def _split_counts(rows: Sequence[dict[str, object]]) -> dict[str, int]:
    counts = Counter(str(row["split"]) for row in rows)
    return {
        split: counts.get(split, 0)
        for split in ("train", "validation", "test")
    }


def build_audit(
    source_paths: Sequence[Path],
    rows: list[dict[str, object]],
) -> dict[str, object]:
    source_counts = Counter(str(row["source_document"]) for row in rows)
    source_documents = [
        {
            "filename": Path(path).name,
            "path": str(Path(path).resolve()),
            "sha256": sha256_file(Path(path)),
            "rows": source_counts.get(Path(path).name, 0),
        }
        for path in source_paths
    ]

    flag_counts = Counter()
    flagged_rows = 0
    duplicate_groups = set()
    for row in rows:
        serialized_flags = str(row["quality_flags"])
        if serialized_flags == "none":
            continue
        flagged_rows += 1
        flags = serialized_flags.split("|")
        flag_counts.update(flags)
        if "exact_duplicate" in flags:
            duplicate_groups.add(str(row["question_group_id"]))

    split_label_distribution = {}
    for split in ("train", "validation", "test"):
        split_label_distribution[split] = _label_counts([
            row for row in rows if row["split"] == split
        ])

    return {
        "pipeline_version": PIPELINE_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_documents": source_documents,
        "total_rows": len(rows),
        "unique_question_groups": len({
            str(row["question_group_id"]) for row in rows
        }),
        "label_distribution": _label_counts(rows),
        "flag_counts": {
            flag: flag_counts.get(flag, 0)
            for flag in FLAG_ORDER
        },
        "flagged_rows": flagged_rows,
        "exact_duplicate_groups": len(duplicate_groups),
        "split_counts": _split_counts(rows),
        "split_label_distribution": split_label_distribution,
        "artifacts": dict(ARTIFACT_FILENAMES),
    }


def _validate_input_paths(source_paths: Sequence[Path]) -> list[Path]:
    paths = [Path(path) for path in source_paths]
    if len(paths) != 2:
        raise ValueError("Exactly two input DOCX files are required")
    resolved_paths = [path.resolve() for path in paths]
    if len(set(resolved_paths)) != 2:
        raise ValueError("The two input DOCX paths must be distinct")
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Input DOCX file does not exist: {path}")
    return paths


def validate_dataset(
    source_paths: Sequence[Path],
    rows: list[dict[str, object]],
    audit: dict[str, object],
) -> None:
    paths = _validate_input_paths(source_paths)
    if not rows:
        raise ValueError("Extracted dataset is empty")

    source_counts = Counter(str(row.get("source_document") or "") for row in rows)
    if set(source_counts) != set(EXPECTED_SOURCE_COUNTS):
        raise ValueError(
            "Source document names do not match the expected files: "
            + ", ".join(sorted(EXPECTED_SOURCE_COUNTS))
        )
    for filename, expected_count in EXPECTED_SOURCE_COUNTS.items():
        actual_count = source_counts.get(filename, 0)
        if actual_count != expected_count:
            raise ValueError(
                f"{filename} has {actual_count} questions; expected {expected_count}"
            )

    expected_total = sum(EXPECTED_SOURCE_COUNTS.values())
    if len(rows) != expected_total:
        raise ValueError(
            f"Combined dataset has {len(rows)} questions; expected {expected_total}"
        )

    row_ids = []
    groups = defaultdict(list)
    for row_number, row in enumerate(rows, start=1):
        question = normalize_question(row.get("question"))
        if not question:
            raise ValueError(f"Row {row_number} has an empty question")
        label = str(row.get("bloom_level") or "")
        if label not in VALID_BLOOM_LEVELS:
            raise ValueError(
                f"Row {row_number} has unsupported Bloom label: {label!r}"
            )
        split = str(row.get("split") or "")
        if split not in {"train", "validation", "test"}:
            raise ValueError(f"Row {row_number} has invalid split: {split!r}")
        row_id = str(row.get("row_id") or "")
        if not row_id:
            raise ValueError(f"Row {row_number} has no row_id")
        row_ids.append(row_id)
        group_id = str(row.get("question_group_id") or "")
        if not group_id:
            raise ValueError(f"Row {row_number} has no question_group_id")
        groups[group_id].append(row)

    duplicate_row_ids = sorted(
        row_id for row_id, count in Counter(row_ids).items() if count > 1
    )
    if duplicate_row_ids:
        raise ValueError("Duplicate row_id: " + ", ".join(duplicate_row_ids))

    for group_id, group_rows in groups.items():
        splits = {str(row["split"]) for row in group_rows}
        if len(splits) != 1:
            raise ValueError(f"Question group {group_id} crosses split boundaries")
        labels = {str(row["bloom_level"]) for row in group_rows}
        if len(labels) != 1:
            raise ValueError(f"Question group {group_id} has multiple Bloom labels")

    actual_labels = _label_counts(rows)
    if actual_labels != EXPECTED_LABEL_COUNTS:
        raise ValueError(
            f"Bloom label distribution is {actual_labels}; "
            f"expected {EXPECTED_LABEL_COUNTS}"
        )

    expected_audit = build_audit(paths, rows)
    for key, expected_value in expected_audit.items():
        if key == "generated_at_utc":
            continue
        if audit.get(key) != expected_value:
            raise ValueError(f"Audit field does not reconcile: {key}")


def build_dataset(
    source_paths: Sequence[Path],
    output_dir: Path,
    seed: int = 42,
) -> dict[str, object]:
    paths = _validate_input_paths(source_paths)
    rows = assign_grouped_splits(build_rows(paths), seed=seed)
    audit = build_audit(paths, rows)
    validate_dataset(paths, rows, audit)

    output_dir = Path(output_dir)
    split_rows = {
        split: [row for row in rows if row["split"] == split]
        for split in ("train", "validation", "test")
    }
    quality_review_rows = [
        {
            **row,
            "review_status": "needs_review",
            "review_notes": "",
        }
        for row in rows
        if row["quality_flags"] != "none"
    ]

    csv_artifacts = [
        (output_dir / ARTIFACT_FILENAMES["full"], CSV_FIELDNAMES, rows),
        *[
            (
                output_dir / ARTIFACT_FILENAMES[split],
                CSV_FIELDNAMES,
                split_rows[split],
            )
            for split in ("train", "validation", "test")
        ],
        (
            output_dir / ARTIFACT_FILENAMES["quality_review"],
            QUALITY_REVIEW_FIELDNAMES,
            quality_review_rows,
        ),
    ]
    write_artifact_set_atomic(
        csv_artifacts,
        [(output_dir / ARTIFACT_FILENAMES["audit"], audit)],
    )
    return audit


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the PONE six-class Bloom training dataset"
    )
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        audit = build_dataset(args.input, args.output_dir, seed=args.seed)
    except (OSError, ValueError, BadZipFile, ET.ParseError, csv.Error) as error:
        parser.error(str(error))

    labels = ", ".join(
        f"{label}={count}"
        for label, count in audit["label_distribution"].items()
    )
    print(f"Total rows: {audit['total_rows']}")
    print(f"Labels: {labels}")
    print(f"Flagged rows: {audit['flagged_rows']}")
    print(f"Output directory: {Path(args.output_dir).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
