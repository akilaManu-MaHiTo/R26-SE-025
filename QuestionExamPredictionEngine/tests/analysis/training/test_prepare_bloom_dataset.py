import unittest

from src.analysis.training.prepare_bloom_dataset import (
    build_review_records,
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


if __name__ == "__main__":
    unittest.main()
