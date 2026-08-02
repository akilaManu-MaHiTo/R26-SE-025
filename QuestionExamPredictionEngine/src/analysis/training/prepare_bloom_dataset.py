from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path


VALID_BLOOM_LEVELS = (
    "remember",
    "understand",
    "apply",
    "analyze",
    "evaluate",
    "create",
)

PIPELINE_VERSION = "1.0.0"

REQUIRED_SOURCE_COLUMNS = (
    "id",
    "subject",
    "topic",
    "subtopic",
    "question",
    "bloom_level",
)

REVIEW_FIELDNAMES = (
    "group_id",
    "question",
    "normalized_question",
    "source_row_count",
    "observed_labels",
    "label_counts",
    "subjects",
    "topics",
    "subtopics",
    "source_ids",
    "approved_bloom_level",
    "review_status",
    "review_notes",
)


def normalize_question(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return " ".join(text.split())


def question_group_id(normalized_question: str) -> str:
    digest = hashlib.sha256(normalized_question.encode("utf-8")).hexdigest()
    return f"bloom-{digest[:16]}"


def validate_source_rows(rows: list[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError("Source dataset is empty")

    required = set(REQUIRED_SOURCE_COLUMNS)
    for row_number, row in enumerate(rows, start=2):
        missing = sorted(required.difference(row.keys()))
        if missing:
            raise ValueError(
                f"Row {row_number} is missing required columns: {', '.join(missing)}"
            )

        if not normalize_question(row.get("question")):
            raise ValueError(f"Row {row_number} has an empty question")

        label = str(row.get("bloom_level") or "").strip().lower()
        if label not in VALID_BLOOM_LEVELS:
            raise ValueError(
                f"Row {row_number} has unsupported Bloom label: "
                f"{row.get('bloom_level')!r}"
            )


def _joined_values(rows: list[Mapping[str, object]], column: str) -> str:
    values = {
        str(row.get(column) or "").strip()
        for row in rows
        if str(row.get(column) or "").strip()
    }
    return "|".join(sorted(values, key=lambda value: (value.casefold(), value)))


def _index_existing_reviews(
    existing_reviews: list[Mapping[str, object]] | None,
) -> dict[str, Mapping[str, object]]:
    indexed = {}
    for row_number, row in enumerate(existing_reviews or [], start=2):
        normalized = normalize_question(row.get("normalized_question"))
        group_id = str(row.get("group_id") or "").strip()
        if group_id in indexed:
            raise ValueError(f"Duplicate review group_id at row {row_number}: {group_id}")
        if not normalized or group_id != question_group_id(normalized):
            raise ValueError(f"Review row {row_number} has a mismatched group_id")

        approval = str(row.get("approved_bloom_level") or "").strip().lower()
        if approval and approval not in VALID_BLOOM_LEVELS:
            raise ValueError(
                f"Review row {row_number} has invalid approved Bloom label: {approval!r}"
            )
        indexed[group_id] = row
    return indexed


def build_review_records(
    rows: list[Mapping[str, object]],
    existing_reviews: list[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    validate_source_rows(rows)
    existing_by_id = _index_existing_reviews(existing_reviews)

    grouped_rows: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        normalized = normalize_question(row.get("question"))
        grouped_rows[normalized].append(row)

    review_records = []
    for normalized in sorted(grouped_rows):
        group = grouped_rows[normalized]
        label_counts = Counter(
            str(row.get("bloom_level") or "").strip().lower()
            for row in group
        )
        question_variants = {
            str(row.get("question") or "").strip()
            for row in group
        }
        representative_question = min(
            question_variants,
            key=lambda value: (len(value), value.casefold(), value),
        )
        group_id = question_group_id(normalized)
        existing = existing_by_id.get(group_id, {})
        approval = str(existing.get("approved_bloom_level") or "").strip().lower()
        review_records.append({
            "group_id": group_id,
            "question": representative_question,
            "normalized_question": normalized,
            "source_row_count": len(group),
            "observed_labels": "|".join(sorted(label_counts)),
            "label_counts": json.dumps(dict(sorted(label_counts.items())), sort_keys=True),
            "subjects": _joined_values(group, "subject"),
            "topics": _joined_values(group, "topic"),
            "subtopics": _joined_values(group, "subtopic"),
            "source_ids": _joined_values(group, "id"),
            "approved_bloom_level": approval,
            "review_status": "approved" if approval else "needs_review",
            "review_notes": str(existing.get("review_notes") or "").strip(),
        })

    return review_records

TRAIN_FIELDNAMES = (
    "group_id",
    "question",
    "bloom_level",
    "source_row_count",
    "review_status",
    "review_notes",
)


def validate_review_rows(rows: list[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError("Review dataset is empty")

    seen_group_ids = set()
    for row_number, row in enumerate(rows, start=2):
        normalized = normalize_question(row.get("normalized_question"))
        group_id = str(row.get("group_id") or "").strip()
        if group_id in seen_group_ids:
            raise ValueError(f"Duplicate review group_id at row {row_number}: {group_id}")
        seen_group_ids.add(group_id)

        if not normalized or group_id != question_group_id(normalized):
            raise ValueError(f"Review row {row_number} has a mismatched group_id")

        approval = str(row.get("approved_bloom_level") or "").strip().lower()
        if approval and approval not in VALID_BLOOM_LEVELS:
            raise ValueError(
                f"Review row {row_number} has invalid approved Bloom label: {approval!r}"
            )


def build_training_records(
    review_rows: list[Mapping[str, object]],
    require_complete: bool = False,
) -> list[dict[str, object]]:
    validate_review_rows(review_rows)

    unreviewed_count = sum(
        1
        for row in review_rows
        if not str(row.get("approved_bloom_level") or "").strip()
    )
    if require_complete and unreviewed_count:
        raise ValueError(
            f"Bloom review is incomplete: {unreviewed_count} question groups remain"
        )

    training_records = []
    for row in review_rows:
        approval = str(row.get("approved_bloom_level") or "").strip().lower()
        if not approval:
            continue
        training_records.append({
            "group_id": str(row.get("group_id") or "").strip(),
            "question": str(row.get("question") or "").strip(),
            "bloom_level": approval,
            "source_row_count": row.get("source_row_count") or "",
            "review_status": "approved",
            "review_notes": str(row.get("review_notes") or "").strip(),
        })

    return sorted(
        training_records,
        key=lambda row: (str(row["question"]).casefold(), str(row["group_id"])),
    )

def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV file has no header: {path}")
        return list(reader)


def write_csv_atomic(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, object]],
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            temporary_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_audit(
    source_path: Path,
    source_rows: list[Mapping[str, object]],
    review_rows: list[Mapping[str, object]],
    training_rows: list[Mapping[str, object]],
) -> dict[str, object]:
    source_labels = Counter(
        str(row.get("bloom_level") or "").strip().lower()
        for row in source_rows
    )
    conflicting_rows = []
    for row in review_rows:
        counts = json.loads(str(row.get("label_counts") or "{}"))
        if len(counts) > 1:
            conflicting_rows.append(row)

    review_status_counts = Counter(
        "approved"
        if str(row.get("approved_bloom_level") or "").strip()
        else "needs_review"
        for row in review_rows
    )
    training_labels = Counter(
        str(row.get("bloom_level") or "").strip().lower()
        for row in training_rows
    )

    return {
        "pipeline_version": PIPELINE_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(Path(source_path).resolve()),
        "input_sha256": sha256_file(source_path),
        "source_rows": len(source_rows),
        "source_label_distribution": dict(sorted(source_labels.items())),
        "unique_normalized_questions": len(review_rows),
        "conflicting_question_groups": len(conflicting_rows),
        "rows_in_conflicting_groups": sum(
            int(row.get("source_row_count") or 0)
            for row in conflicting_rows
        ),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "approved_training_rows": len(training_rows),
        "approved_training_label_distribution": dict(sorted(training_labels.items())),
        "excluded_unreviewed_groups": len(review_rows) - len(training_rows),
    }


def prepare_review(input_path: Path, output_dir: Path) -> dict[str, object]:
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    review_path = output_dir / "dataset_v1_bloom_review.csv"
    training_path = output_dir / "dataset_v1_bloom_train.csv"
    audit_path = output_dir / "dataset_v1_bloom_audit.json"

    source_rows = read_csv_rows(input_path)
    existing_reviews = read_csv_rows(review_path) if review_path.exists() else None
    review_rows = build_review_records(source_rows, existing_reviews=existing_reviews)
    training_rows = build_training_records(review_rows)
    audit = build_audit(input_path, source_rows, review_rows, training_rows)

    write_csv_atomic(review_path, REVIEW_FIELDNAMES, review_rows)
    write_csv_atomic(training_path, TRAIN_FIELDNAMES, training_rows)
    write_json_atomic(audit_path, audit)
    return audit

def build_training(
    review_file: Path,
    output_dir: Path,
    require_complete_review: bool = False,
) -> dict[str, object]:
    review_file = Path(review_file)
    output_dir = Path(output_dir)
    training_path = output_dir / "dataset_v1_bloom_train.csv"
    audit_path = output_dir / "dataset_v1_bloom_audit.json"

    review_rows = read_csv_rows(review_file)
    training_rows = build_training_records(
        review_rows,
        require_complete=require_complete_review,
    )
    if not audit_path.exists():
        raise ValueError(
            f"Audit file not found; run prepare-review first: {audit_path}"
        )
    with audit_path.open("r", encoding="utf-8") as handle:
        audit = json.load(handle)

    review_status_counts = Counter(
        "approved"
        if str(row.get("approved_bloom_level") or "").strip()
        else "needs_review"
        for row in review_rows
    )
    training_labels = Counter(
        str(row.get("bloom_level") or "").strip().lower()
        for row in training_rows
    )
    audit.update({
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "unique_normalized_questions": len(review_rows),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "approved_training_rows": len(training_rows),
        "approved_training_label_distribution": dict(sorted(training_labels.items())),
        "excluded_unreviewed_groups": len(review_rows) - len(training_rows),
    })

    write_csv_atomic(training_path, TRAIN_FIELDNAMES, training_rows)
    write_json_atomic(audit_path, audit)
    return audit


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare expert-reviewed Bloom classification data"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare-review",
        help="Create or refresh the expert-review queue",
    )
    prepare_parser.add_argument("--input", type=Path, required=True)
    prepare_parser.add_argument("--output-dir", type=Path, required=True)

    training_parser = subparsers.add_parser(
        "build-training",
        help="Build the approved-only training CSV",
    )
    training_parser.add_argument("--review-file", type=Path, required=True)
    training_parser.add_argument("--output-dir", type=Path, required=True)
    training_parser.add_argument("--require-complete-review", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-review":
            audit = prepare_review(args.input, args.output_dir)
        else:
            audit = build_training(
                args.review_file,
                args.output_dir,
                require_complete_review=args.require_complete_review,
            )
    except (OSError, ValueError, csv.Error, json.JSONDecodeError) as error:
        parser.error(str(error))

    print(f"Source rows: {audit['source_rows']}")
    print(f"Review groups: {audit['unique_normalized_questions']}")
    print(f"Approved training rows: {audit['approved_training_rows']}")
    print(f"Unreviewed groups: {audit['excluded_unreviewed_groups']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
