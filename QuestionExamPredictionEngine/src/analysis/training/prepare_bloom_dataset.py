from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping


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
