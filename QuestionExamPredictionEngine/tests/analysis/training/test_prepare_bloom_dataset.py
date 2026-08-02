import unittest

from src.analysis.training.prepare_bloom_dataset import (
    build_review_records,
    build_training_records,
    normalize_question,
    question_group_id,
    validate_source_rows,
)


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
        normalized = normalize_question("Explain ACID?")
        existing = [{
            "group_id": question_group_id(normalized),
            "normalized_question": normalized,
            "approved_bloom_level": "Understand",
            "review_notes": "Checked by lecturer",
        }]

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


if __name__ == "__main__":
    unittest.main()
