import unittest
from unittest.mock import patch

from src.agents.contracts import AgentStatus
from src.agents.model_registry import ModelRegistry
from src.agents.orchestrator import ExamAnalysisOrchestrator


class AgentWorkflowIntegrationTests(unittest.TestCase):
    @patch("src.analysis.exam_analysis.cognitive_score")
    def test_current_exam_flows_through_all_agents(self, cognitive_mock):
        cognitive_mock.return_value = {
            "cognitive_score": 0.8,
            "student_level": "understand",
            "required_level": "understand",
        }
        exam = {
            "exam": "DBMS",
            "year": 2025,
            "questions": [
                {
                    "question_number": 1,
                    "topic": "Normalization",
                    "parts": [
                        {
                            "part": "a",
                            "question": "Explain normalization",
                            "max_marks": 10,
                        }
                    ],
                }
            ],
        }
        students = [
            {
                "student_id": "s1",
                "year": 2025,
                "answers": [
                    {
                        "question_number": 1,
                        "parts": [
                            {
                                "part": "a",
                                "answer": "reduces redundancy",
                                "score": 8,
                                "max_marks": 10,
                            }
                        ],
                    }
                ],
            },
            {
                "student_id": "s2",
                "year": 2025,
                "answers": [
                    {
                        "question_number": 1,
                        "parts": [
                            {
                                "part": "a",
                                "answer": "unrelated",
                                "score": 2,
                                "max_marks": 10,
                            }
                        ],
                    }
                ],
            },
        ]
        model_answers = {
            "1": {"a": "Normalization reduces redundancy"}
        }
        registry = ModelRegistry()
        registry.register("similarity", "v1", lambda: object())

        result = ExamAnalysisOrchestrator.with_defaults(registry).run(
            exam,
            students,
            model_answers,
        )

        self.assertEqual(len(result.question_mappings), 1)
        self.assertEqual(len(result.answer_analyses), 2)
        self.assertEqual(result.answer_analyses[0].marks_obtained, 8.0)
        self.assertEqual(result.answer_analyses[1].marks_obtained, 2.0)
        self.assertTrue(result.cohort_result.question_summaries)
        self.assertEqual(
            result.cohort_result.future_topic_probabilities,
            [],
        )
        self.assertEqual(result.status, AgentStatus.PARTIAL)


if __name__ == "__main__":
    unittest.main()
