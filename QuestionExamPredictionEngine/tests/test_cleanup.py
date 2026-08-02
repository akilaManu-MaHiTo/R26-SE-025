import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from src.analysis.exam_analysis import build_student_reports
from src.analysis.grading.service import grade_answer
from src.analysis.reporting import (
    create_analysis_output_dir,
    write_analysis_outputs,
)
from src.analytics import topic_utils
from src.prediction.topic_prediction import match_topics, predict_topics


class TopicMatchingTests(unittest.TestCase):
    def setUp(self):
        self.exam_data = {
            "questions": [
                {
                    "question_number": 1,
                    "topic": "Database normalization",
                    "parts": [
                        {
                            "part": "a",
                            "question": "Explain normalization and redundancy",
                        }
                    ],
                },
                {
                    "question_number": 2,
                    "topic": "Network security",
                    "parts": [
                        {
                            "part": "a",
                            "question": "Explain encryption and authentication",
                        }
                    ],
                },
            ]
        }

    def test_stop_words_do_not_create_topic_matches(self):
        results = match_topics("and the is with", self.exam_data, top_n=2)
        self.assertTrue(all(item["score"] == 0 for item in results))
        self.assertTrue(all(item["matched_terms"] == [] for item in results))

    def test_compatibility_alias_returns_same_results(self):
        expected = match_topics("normalization redundancy", self.exam_data)
        actual = predict_topics("normalization redundancy", self.exam_data)
        self.assertEqual(actual, expected)

    def test_canonical_topics_are_loaded_from_project_data(self):
        expected_path = Path(topic_utils.__file__).resolve().parents[2] / "data" / "topics.json"
        self.assertTrue(expected_path.exists())
        self.assertGreater(len(topic_utils._CANONICAL_TOPICS), 0)


class ExamAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.exam_data = {
            "exam": "Database Systems",
            "year": 2021,
            "questions": [
                {
                    "question_number": 1,
                    "topic": "Normalization",
                    "parts": [
                        {
                            "part": "a",
                            "question": "Explain database normalization",
                            "max_marks": 10,
                        }
                    ],
                }
            ],
        }
        self.student_data = [{
            "student_id": "student-1",
            "year": 2021,
            "answers": [{
                "question_number": 1,
                "parts": [{
                    "part": "a",
                    "answer": "Normalization reduces redundant data",
                    "score": 8,
                    "max_marks": 10,
                }],
            }],
        }]
        self.cognitive_result = {
            "cognitive_score": 0.8,
            "student_level": "understand",
            "required_level": "understand",
        }

    @patch("src.analysis.exam_analysis.cognitive_score")
    def test_concept_score_uses_model_answer(self, cognitive_mock):
        cognitive_mock.return_value = self.cognitive_result
        model_answers = {
            "1": {"a": "Normalization reduces redundant data"}
        }

        report = build_student_reports(
            self.exam_data,
            self.student_data,
            model_answers,
        )[0]

        self.assertEqual(report["concept_reference_source"], "model_answer")
        self.assertEqual(report["concept_score"], 1.0)
        self.assertEqual(report["score"], 8.0)
        self.assertEqual(report["max_marks"], 10.0)

    @patch("src.analysis.exam_analysis.cognitive_score")
    def test_missing_model_answer_uses_question_not_student_answer(self, cognitive_mock):
        cognitive_mock.return_value = self.cognitive_result
        self.student_data[0]["answers"][0]["parts"][0]["answer"] = (
            "A response containing unrelated vocabulary"
        )

        report = build_student_reports(
            self.exam_data,
            self.student_data,
            model_answers={},
        )[0]

        self.assertEqual(report["concept_reference_source"], "question_text")
        self.assertEqual(report["concept_score"], 0.0)


class GradingServiceTests(unittest.TestCase):
    @patch("src.analysis.grading.service.semantic_similarity", return_value=0.5)
    def test_v1_policy_is_shared_and_bounded(self, _similarity_mock):
        result = grade_answer(
            object(),
            "Atomicity Consistency",
            "Atomicity",
            10,
            version="v1",
        )

        self.assertEqual(result["similarity"], 0.5)
        self.assertEqual(result["concept_score"], 0.5)
        self.assertEqual(result["marks_obtained"], 5.0)
        self.assertNotIn("feedback", result)

    @patch("src.analysis.grading.service.semantic_similarity", return_value=0.9)
    def test_v2_policy_includes_feedback(self, _similarity_mock):
        result = grade_answer(
            object(),
            "Atomicity Consistency Isolation Durability",
            "Unrelated answer",
            10,
            version="v2",
        )

        self.assertIn("feedback", result)
        self.assertLess(result["marks_obtained"], 3)

    def test_invalid_max_marks_is_rejected(self):
        with self.assertRaises(ValueError):
            grade_answer(object(), "reference", "answer", 0)


class ReportingTests(unittest.TestCase):
    def test_output_writer_uses_all_expected_filenames(self):
        results = {
            "student_reports": [{"student_id": "1"}],
            "question_summaries": [],
            "student_summaries": [],
            "misunderstood_questions": [],
            "cognitive_gaps": [],
            "weak_topics": [],
        }

        temporary_dir = Path("tests") / "_reporting_tmp"
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        temporary_dir.mkdir()
        try:
            output_dir = create_analysis_output_dir(
                temporary_dir,
                {"exam": "DBMS: Final/Exam", "year": 2021},
                timestamp="run",
            )
            write_analysis_outputs(results, output_dir)

            filenames = {path.name for path in output_dir.glob("*.json")}
            self.assertEqual(len(filenames), 6)
            self.assertIn("student_report.json", filenames)
            payload = json.loads(
                (output_dir / "student_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload[0]["student_id"], "1")
        finally:
            shutil.rmtree(temporary_dir)


if __name__ == "__main__":
    unittest.main()
