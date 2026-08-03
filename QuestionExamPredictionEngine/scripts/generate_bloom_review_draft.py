from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from src.analysis.training.prepare_bloom_dataset import REVIEW_FIELDNAMES, read_csv_rows


def draft_approval_for(question: str) -> tuple[str, str]:
    concept = question.strip()
    if concept.lower().startswith("explain ") and concept.endswith(" briefly."):
        name = concept[len("explain "):-len(" briefly.")].strip()
        return (
            "understand",
            f"Draft: asks the learner to explain {name}, demonstrating "
            "constructed meaning (Understand).",
        )
    if concept.startswith("Give one application of "):
        name = concept[len("Give one application of "):].rsplit(" in ", 1)[0].strip()
        return (
            "understand",
            f"Draft: asks for an example of how {name} is used; exemplifying is "
            "Understand, not executing a procedure.",
        )
    if concept.startswith("What is "):
        name = concept[len("What is "):].rsplit(" in ", 1)[0].strip().rstrip("?")
        return (
            "remember",
            f"Draft: asks the learner to recall or state what {name} is (Remember).",
        )
    if concept.startswith("Why is "):
        name = concept[len("Why is "):].rsplit(" important for ", 1)[0].strip()
        return (
            "understand",
            f"Draft: asks the learner to explain the significance of {name} "
            "(Understand).",
        )
    raise ValueError(f"Unrecognized question pattern: {question!r}")


def build_draft_review(review_path: Path, output_path: Path) -> None:
    rows = read_csv_rows(review_path, REVIEW_FIELDNAMES)
    draft_rows = []
    for row in rows:
        approval, note = draft_approval_for(str(row["question"]).strip())
        draft = dict(row)
        draft["approved_bloom_level"] = approval
        draft["review_notes"] = note
        draft_rows.append(draft)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REVIEW_FIELDNAMES))
        writer.writeheader()
        writer.writerows(draft_rows)
    print(f"Wrote {len(draft_rows)} draft rows to {output_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Auto-fill draft Bloom approvals for the review queue"
    )
    parser.add_argument("--review-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    build_draft_review(args.review_file, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
