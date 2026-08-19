import unittest
from unittest.mock import patch

from src.agents.answer_misconception_agent import AnswerMisconceptionAgent
from src.agents.contracts import AgentStatus, QuestionMappingResult


class AnswerMisconceptionAgentTests(unittest.TestCase):
    @patch("src.agents.answer_misconception_agent.build_student_reports")
    def test_preserves_existing_report_values_and_marks_partial(self, build_mock):
        build_mock.return_value = [
            {
                "student_id": "student-1",
                "exam": "DBMS",
                "year": "2025",
                "question": "1",
                "part": "a",
                "score": 8.0,
                "max_marks": 10.0,
                "performance_score": 0.8,
                "concept_score": 0.7,
                "concept_reference_source": "model_answer",
                "cognitive_score": 0.6,
                "student_level": "understand",
                "required_level": "apply",
                "topic": "Normalization",
                "learning_score": 0.735,
            }
        ]
        mapping = QuestionMappingResult(
            exam_id="dbms-2025",
            question_id="1",
            part_id="a",
            question_text="Explain normalization",
            max_marks=10,
            topic_ids=["Normalization"],
            mapping_confidence=0.8,
        )

        results = AnswerMisconceptionAgent().run(
            {"questions": []},
            {
                "student_id": "student-1",
                "answers": [{
                    "question_number": 1,
                    "parts": [{
                        "part": "a",
                        "answer": "normalized tables",
                        "score": 8,
                        "max_marks": 10,
                    }],
                }],
            },
            {},
            {("1", "a"): mapping},
        )

        self.assertEqual(results[0].marks_obtained, 8.0)
        self.assertEqual(results[0].learning_score, 0.735)
        self.assertEqual(results[0].status, AgentStatus.PARTIAL)
        self.assertEqual(results[0].misconceptions, [])
        self.assertEqual(
            results[0].warnings[0].code,
            "misconception_extractor_unavailable",
        )

    @patch(
        "src.agents.answer_misconception_agent.build_student_reports",
        return_value=[],
    )
    def test_empty_student_report_returns_empty_result(self, _build_mock):
        self.assertEqual(
            AnswerMisconceptionAgent().run({}, {}, {}, {}),
            [],
        )


if __name__ == "__main__":
    unittest.main()
