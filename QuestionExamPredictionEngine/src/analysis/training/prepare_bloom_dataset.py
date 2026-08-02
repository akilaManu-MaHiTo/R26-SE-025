from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
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
    if not existing_reviews:
        return {}
    validate_review_rows(existing_reviews)
    return {
        str(row.get("group_id") or "").strip(): row
        for row in existing_reviews
    }

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
    required_fields = set(REVIEW_FIELDNAMES)
    for row_number, row in enumerate(rows, start=2):
        missing_fields = sorted(required_fields.difference(row.keys()))
        if missing_fields:
            raise ValueError(
                f"Review row {row_number} is missing required columns: "
                f"{', '.join(missing_fields)}"
            )

        normalized = normalize_question(row.get("normalized_question"))
        question = str(row.get("question") or "").strip()
        group_id = str(row.get("group_id") or "").strip()
        if group_id in seen_group_ids:
            raise ValueError(f"Duplicate review group_id at row {row_number}: {group_id}")
        seen_group_ids.add(group_id)

        if not normalized or group_id != question_group_id(normalized):
            raise ValueError(f"Review row {row_number} has a mismatched group_id")
        if not question:
            raise ValueError(f"Review row {row_number} has an empty question")
        if normalize_question(question) != normalized:
            raise ValueError(
                f"Review row {row_number} question does not match normalized_question"
            )
        try:
            source_row_count = int(str(row.get("source_row_count") or ""))
        except ValueError as error:
            raise ValueError(
                f"Review row {row_number} needs a positive source_row_count"
            ) from error
        if source_row_count <= 0:
            raise ValueError(
                f"Review row {row_number} needs a positive source_row_count"
            )

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

def read_csv_rows(
    path: Path,
    expected_fieldnames: Sequence[str] | None = None,
) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        if not reader.fieldnames:
            raise ValueError(f"CSV file has no header: {path}")
        fieldnames = list(reader.fieldnames)
        duplicate_headers = sorted({
            name
            for name in fieldnames
            if fieldnames.count(name) > 1
        })
        if duplicate_headers:
            raise ValueError(
                f"CSV file has duplicate columns: {', '.join(duplicate_headers)}"
            )
        if expected_fieldnames is not None:
            expected = set(expected_fieldnames)
            actual = set(fieldnames)
            missing = sorted(expected - actual)
            unexpected = sorted(actual - expected)
            if missing or unexpected:
                details = []
                if missing:
                    details.append(f"missing: {', '.join(missing)}")
                if unexpected:
                    details.append(f"unexpected: {', '.join(unexpected)}")
                raise ValueError(
                    "Review CSV columns do not match the required schema ("
                    + "; ".join(details)
                    + ")"
                )

        rows = list(reader)
        if any(None in row for row in rows):
            raise ValueError(f"CSV row has more values than columns: {path}")
        return rows


def _stage_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, object]],
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".stage",
        ) as handle:
            staged_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
            writer.writeheader()
            writer.writerows(rows)
        return staged_path
    except Exception:
        if staged_path and staged_path.exists():
            staged_path.unlink()
        raise


def _stage_json(path: Path, payload: Mapping[str, object]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".stage",
        ) as handle:
            staged_path = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
        return staged_path
    except Exception:
        if staged_path and staged_path.exists():
            staged_path.unlink()
        raise


def _commit_staged_files(staged_files: Mapping[Path, Path]) -> None:
    backups: dict[Path, Path | None] = {}
    try:
        for destination in staged_files:
            destination = Path(destination)
            if destination.exists():
                with tempfile.NamedTemporaryFile(
                    "wb",
                    delete=False,
                    dir=destination.parent,
                    prefix=f".{destination.name}.",
                    suffix=".backup",
                ) as handle:
                    backup_path = Path(handle.name)
                shutil.copy2(destination, backup_path)
                backups[destination] = backup_path
            else:
                backups[destination] = None

        for destination, staged_path in staged_files.items():
            os.replace(staged_path, destination)
    except Exception as commit_error:
        rollback_errors = []
        for destination, backup_path in backups.items():
            try:
                if backup_path and backup_path.exists():
                    os.replace(backup_path, destination)
                elif destination.exists():
                    destination.unlink()
            except OSError as rollback_error:
                rollback_errors.append(f"{destination}: {rollback_error}")
        if rollback_errors:
            raise RuntimeError(
                "Artifact commit failed and rollback was incomplete: "
                + "; ".join(rollback_errors)
            ) from commit_error
        raise
    finally:
        for staged_path in staged_files.values():
            if staged_path.exists():
                staged_path.unlink()
        for backup_path in backups.values():
            if backup_path and backup_path.exists():
                backup_path.unlink()


def write_artifact_set_atomic(
    csv_artifacts: Sequence[
        tuple[Path, Sequence[str], Sequence[Mapping[str, object]]]
    ],
    json_artifacts: Sequence[tuple[Path, Mapping[str, object]]],
) -> None:
    staged_files: dict[Path, Path] = {}
    try:
        for path, fieldnames, rows in csv_artifacts:
            destination = Path(path)
            staged_files[destination] = _stage_csv(destination, fieldnames, rows)
        for path, payload in json_artifacts:
            destination = Path(path)
            staged_files[destination] = _stage_json(destination, payload)
    except Exception:
        for staged_path in staged_files.values():
            if staged_path.exists():
                staged_path.unlink()
        raise

    _commit_staged_files(staged_files)


def write_csv_atomic(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, object]],
) -> None:
    write_artifact_set_atomic([(Path(path), fieldnames, rows)], [])


def write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    write_artifact_set_atomic([], [(Path(path), payload)])

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def review_queue_sha256(review_rows: list[Mapping[str, object]]) -> str:
    immutable_fields = REVIEW_FIELDNAMES[:10]
    queue_payload = [
        {
            field: str(row.get(field) or "").strip()
            for field in immutable_fields
        }
        for row in sorted(
            review_rows,
            key=lambda row: str(row.get("group_id") or ""),
        )
    ]
    serialized = json.dumps(
        queue_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


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
        "review_queue_sha256": review_queue_sha256(review_rows),
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
    existing_reviews = (
        read_csv_rows(review_path, REVIEW_FIELDNAMES)
        if review_path.exists()
        else None
    )
    review_rows = build_review_records(source_rows, existing_reviews=existing_reviews)
    training_rows = build_training_records(review_rows)
    audit = build_audit(input_path, source_rows, review_rows, training_rows)

    write_artifact_set_atomic(
        [
            (review_path, REVIEW_FIELDNAMES, review_rows),
            (training_path, TRAIN_FIELDNAMES, training_rows),
        ],
        [(audit_path, audit)],
    )
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

    review_rows = read_csv_rows(review_file, REVIEW_FIELDNAMES)
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
    expected_review_fingerprint = str(audit.get("review_queue_sha256") or "")
    actual_review_fingerprint = review_queue_sha256(review_rows)
    if not expected_review_fingerprint:
        raise ValueError("Audit has no review queue fingerprint; run prepare-review again")
    if actual_review_fingerprint != expected_review_fingerprint:
        raise ValueError(
            "Review queue does not match its audit; run prepare-review with the original source"
        )

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

    write_artifact_set_atomic(
        [(training_path, TRAIN_FIELDNAMES, training_rows)],
        [(audit_path, audit)],
    )
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
