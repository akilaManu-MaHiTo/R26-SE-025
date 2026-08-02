import unittest

from src.agents.contracts import (
    AgentStatus,
    CohortPredictionResult,
    QuestionMappingResult,
)
from src.agents.model_registry import ModelRegistry
from src.agents.orchestrator import ExamAnalysisOrchestrator


class FailingQuestionAgent:
    def run(self, exam_id, exam_data, question, part, rubric_criteria):
        if part["part"] == "a":
            raise RuntimeError("mapping failed")
        return QuestionMappingResult(
            exam_id=exam_id,
            question_id="1",
            part_id="b",
            question_text="Second",
            max_marks=5,
            topic_ids=["Q1b"],
            mapping_confidence=0.5,
            status=AgentStatus.PARTIAL,
        )


class SuccessfulQuestionAgent:
    def run(self, exam_id, exam_data, question, part, rubric_criteria):
        return QuestionMappingResult(
            exam_id=exam_id,
            question_id="1",
            part_id="a",
            question_text="Explain normalization",
            max_marks=10,
            topic_ids=["Normalization"],
            mapping_confidence=0.8,
        )


class NoOpAnswerAgent:
    def run(self, exam_data, student, model_answers, mappings, **weights):
        return []


class FirstStudentFailsAgent:
    def __init__(self):
        self.calls = 0

    def run(self, exam_data, student, model_answers, mappings, **weights):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("analysis failed")
        return []


class NoOpCohortAgent:
    def run(self, exam_id, exam_data, analyses, **thresholds):
        return CohortPredictionResult(
            exam_id=exam_id,
            status=AgentStatus.PARTIAL,
        )


class OrchestratorFailureTests(unittest.TestCase):
    def setUp(self):
        self.exam = {
            "exam": "DBMS",
            "year": 2025,
            "questions": [
                {
                    "question_number": 1,
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
        self.student = {
            "student_id": "s1",
            "year": 2025,
            "answers": [
                {
                    "question_number": 1,
                    "parts": [
                        {
                            "part": "a",
                            "answer": "text",
                            "score": 8,
                            "max_marks": 10,
                        }
                    ],
                }
            ],
        }

    def test_question_failure_does_not_stop_other_question_parts(self):
        exam = dict(self.exam)
        exam["questions"] = [
            {
                "question_number": 1,
                "parts": [
                    {"part": "a", "question": "First", "max_marks": 5},
                    {"part": "b", "question": "Second", "max_marks": 5},
                ],
            }
        ]
        orchestrator = ExamAnalysisOrchestrator(
            ModelRegistry(),
            FailingQuestionAgent(),
            NoOpAnswerAgent(),
            NoOpCohortAgent(),
        )

        result = orchestrator.run(exam, [])

        self.assertEqual(len(result.question_mappings), 2)
        self.assertEqual(result.question_mappings[0].status, AgentStatus.FAILED)
        self.assertEqual(
            result.question_mappings[0].warnings[0].code,
            "question_mapping_failed",
        )
        self.assertEqual(result.question_mappings[1].part_id, "b")

    def test_student_failure_produces_failed_answer_and_continues(self):
        answer_agent = FirstStudentFailsAgent()
        orchestrator = ExamAnalysisOrchestrator(
            ModelRegistry(),
            SuccessfulQuestionAgent(),
            answer_agent,
            NoOpCohortAgent(),
        )

        result = orchestrator.run(
            self.exam,
            [self.student, dict(self.student)],
        )

        self.assertEqual(answer_agent.calls, 2)
        self.assertEqual(result.answer_analyses[0].status, AgentStatus.FAILED)
        self.assertEqual(result.answer_analyses[0].student_id, "s1")
        self.assertEqual(
            result.answer_analyses[0].warnings[0].code,
            "answer_analysis_failed",
        )


if __name__ == "__main__":
    unittest.main()
