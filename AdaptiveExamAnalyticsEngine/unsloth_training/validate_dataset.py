"""Validate Bloom-taxonomy JSONL files before fine-tuning.

This module intentionally uses only the Python standard library so it can be
run locally before installing the GPU training dependencies in Colab.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BLOOM_LEVELS = (
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create",
)

TOPICS = (
    "Introduction to DBMS & Conceptual Database Design",
    "Logical Database Design",
    "Schema Refinement",
    "Structured Query Language (SQL)",
    "Database Programming",
    "Java Database Connectivity (JDBC)",
    "Database Indexes and Storage Structures",
    "Database Transaction Management and Concurrency Control",
    "Database Recovery and Log Management",
    "Database Utilities",
    "Database Security",
)

EXPECTED_ROLES = ("system", "user", "assistant")
EXPECTED_RESPONSE_KEYS = {"level", "topic", "subtopic", "confidence", "reason"}
ANNOTATION_STATUSES = {"adjudicated", "example_only"}


class DatasetValidationError(ValueError):
    """Raised when one or more dataset records violate the contract."""


def _non_blank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_record(record: Any, source: Path, line_number: int) -> list[str]:
    prefix = f"{source}:{line_number}"
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"{prefix}: record must be a JSON object"]

    for field in ("question_id", "group_id", "gold_label", "annotation_status"):
        if not _non_blank(record.get(field)):
            errors.append(f"{prefix}: {field} must be a non-empty string")

    gold_label = record.get("gold_label")
    if gold_label not in BLOOM_LEVELS:
        errors.append(f"{prefix}: gold_label must be one of {BLOOM_LEVELS}")

    annotation_status = record.get("annotation_status")
    if annotation_status not in ANNOTATION_STATUSES:
        errors.append(
            f"{prefix}: annotation_status must be one of {sorted(ANNOTATION_STATUSES)}"
        )
    annotators = record.get("annotator_ids")
    if not isinstance(annotators, list) or not all(_non_blank(item) for item in annotators):
        errors.append(f"{prefix}: annotator_ids must be a list of non-empty strings")
    elif annotation_status == "adjudicated" and len(set(annotators)) < 2:
        errors.append(f"{prefix}: adjudicated records require at least two annotators")

    messages = record.get("messages")
    if not isinstance(messages, list) or len(messages) != 3:
        errors.append(f"{prefix}: messages must contain exactly system, user, assistant")
        return errors

    roles = tuple(message.get("role") for message in messages if isinstance(message, dict))
    if roles != EXPECTED_ROLES:
        errors.append(f"{prefix}: message roles must be {EXPECTED_ROLES}, received {roles}")
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            errors.append(f"{prefix}: messages[{index}] must be an object")
        elif not _non_blank(message.get("content")):
            errors.append(f"{prefix}: messages[{index}].content must be non-empty")

    if errors:
        return errors

    try:
        response = json.loads(messages[2]["content"])
    except json.JSONDecodeError as exc:
        return [f"{prefix}: assistant content must contain valid JSON: {exc}"]
    if not isinstance(response, dict):
        return [f"{prefix}: assistant JSON must be an object"]
    if set(response) != EXPECTED_RESPONSE_KEYS:
        errors.append(
            f"{prefix}: assistant JSON keys must be {sorted(EXPECTED_RESPONSE_KEYS)}"
        )
    if response.get("level") != gold_label:
        errors.append(f"{prefix}: assistant level must equal gold_label")
    if response.get("topic") not in TOPICS:
        errors.append(f"{prefix}: assistant topic is outside the controlled taxonomy")
    if not _non_blank(response.get("subtopic")):
        errors.append(f"{prefix}: assistant subtopic must be non-empty")
    if not _non_blank(response.get("reason")):
        errors.append(f"{prefix}: assistant reason must be non-empty")
    confidence = response.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        errors.append(f"{prefix}: assistant confidence must be numeric")
    elif not 0 <= float(confidence) <= 1:
        errors.append(f"{prefix}: assistant confidence must be between 0 and 1")
    return errors


def validate_paths(
    paths: list[Path], *, require_adjudicated: bool = False
) -> dict[str, Any]:
    errors: list[str] = []
    records_by_path: dict[Path, list[dict[str, Any]]] = {}
    seen_ids: dict[str, str] = {}
    groups_by_path: dict[Path, set[str]] = defaultdict(set)
    distribution: Counter[str] = Counter()

    for path in paths:
        records: list[dict[str, Any]] = []
        if not path.is_file():
            errors.append(f"{path}: file does not exist")
            continue
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_number}: invalid JSON: {exc}")
                continue
            errors.extend(_validate_record(record, path, line_number))
            if not isinstance(record, dict):
                continue
            question_id = record.get("question_id")
            if _non_blank(question_id):
                if question_id in seen_ids:
                    errors.append(
                        f"{path}:{line_number}: duplicate question_id {question_id!r}; "
                        f"first seen in {seen_ids[question_id]}"
                    )
                else:
                    seen_ids[question_id] = f"{path}:{line_number}"
            group_id = record.get("group_id")
            if _non_blank(group_id):
                groups_by_path[path].add(group_id)
            gold_label = record.get("gold_label")
            if gold_label in BLOOM_LEVELS:
                distribution[gold_label] += 1
            if require_adjudicated and record.get("annotation_status") != "adjudicated":
                errors.append(
                    f"{path}:{line_number}: production training requires annotation_status=adjudicated"
                )
            records.append(record)
        records_by_path[path] = records

    for index, left in enumerate(paths):
        for right in paths[index + 1 :]:
            overlap = groups_by_path[left] & groups_by_path[right]
            if overlap:
                errors.append(
                    f"group leakage between {left} and {right}: {sorted(overlap)}"
                )

    if errors:
        raise DatasetValidationError("\n".join(errors))
    return {
        "records": sum(len(records) for records in records_by_path.values()),
        "distribution": {level: distribution[level] for level in BLOOM_LEVELS},
        "files": {str(path): len(records_by_path[path]) for path in paths},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument(
        "--require-adjudicated",
        action="store_true",
        help="Reject example_only records before a real training run.",
    )
    args = parser.parse_args()
    try:
        summary = validate_paths(args.files, require_adjudicated=args.require_adjudicated)
    except DatasetValidationError as exc:
        print(f"Dataset validation failed:\n{exc}")
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
