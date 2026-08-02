import unittest

from src.agents.contracts import (
    AgentStatus,
    CohortPredictionResult,
    QuestionMappingResult,
)
from src.agents.model_registry import ModelRegistry
from src.agents.orchestrator import ExamAnalysisOrchestrator


class RecordingQuestionAgent:
    def __init__(self, events):
        self.events = events

    def run(self, exam_id, exam_data, question, part, rubric_criteria):
        self.events.append("question")
        return QuestionMappingResult(
            exam_id=exam_id,
            question_id=str(question["question_number"]),
            part_id=str(part["part"]),
            question_text=str(part["question"]),
            max_marks=float(part["max_marks"]),
            topic_ids=["Normalization"],
            mapping_confidence=0.8,
            status=AgentStatus.PARTIAL,
        )


class RecordingAnswerAgent:
    def __init__(self, events):
        self.events = events

    def run(self, exam_data, student, model_answers, mappings, **weights):
        self.events.append("answer")
        if ("1", "a") not in mappings:
            raise AssertionError("question mapping must exist before answer analysis")
        return []


class RecordingCohortAgent:
    def __init__(self, events):
        self.events = events

    def run(self, exam_id, exam_data, analyses, **thresholds):
        self.events.append("cohort")
        return CohortPredictionResult(
            exam_id=exam_id,
            status=AgentStatus.PARTIAL,
        )


class OrchestratorTests(unittest.TestCase):
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
        self.students = [
            {
                "student_id": "s1",
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
        ]

    def test_runs_question_answer_and_cohort_agents_in_order(self):
        events = []
        registry = ModelRegistry()
        registry.register("similarity", "v1", lambda: object())
        orchestrator = ExamAnalysisOrchestrator(
            registry,
            RecordingQuestionAgent(events),
            RecordingAnswerAgent(events),
            RecordingCohortAgent(events),
        )

        result = orchestrator.run(self.exam, self.students)

        self.assertEqual(events, ["question", "answer", "cohort"])
        self.assertEqual(result.context.model_versions, {"similarity": "v1"})
        self.assertEqual(result.status, AgentStatus.PARTIAL)
        self.assertEqual(len(result.question_mappings), 1)

    def test_input_hash_is_stable_across_equivalent_runs(self):
        orchestrator = ExamAnalysisOrchestrator.with_defaults(ModelRegistry())

        first = orchestrator._input_hash(self.exam, self.students, {}, {})
        second = orchestrator._input_hash(
            dict(self.exam),
            list(self.students),
            {},
            {},
        )

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
