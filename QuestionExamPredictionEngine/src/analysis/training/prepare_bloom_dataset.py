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


def build_review_records(
    rows: list[Mapping[str, object]],
    existing_reviews: list[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    validate_source_rows(rows)
    del existing_reviews

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
        review_records.append({
            "group_id": question_group_id(normalized),
            "question": representative_question,
            "normalized_question": normalized,
            "source_row_count": len(group),
            "observed_labels": "|".join(sorted(label_counts)),
            "label_counts": json.dumps(dict(sorted(label_counts.items())), sort_keys=True),
            "subjects": _joined_values(group, "subject"),
            "topics": _joined_values(group, "topic"),
            "subtopics": _joined_values(group, "subtopic"),
            "source_ids": _joined_values(group, "id"),
            "approved_bloom_level": "",
            "review_status": "needs_review",
            "review_notes": "",
        })

    return review_records
