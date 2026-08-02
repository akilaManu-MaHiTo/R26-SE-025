import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from src.agents.answer_misconception_agent import AnswerMisconceptionAgent
from src.agents.cohort_prediction_agent import CohortPredictionAgent
from src.agents.contracts import (
    AgentStatus,
    AnswerAnalysisResult,
    CohortPredictionResult,
    QuestionMappingResult,
)
from src.agents.model_registry import ModelRegistry
from src.agents.orchestrator import ExamAnalysisOrchestrator
from src.agents.question_knowledge_agent import QuestionKnowledgeAgent


def analysis(student_id, question_id="1", part_id="a", status=AgentStatus.SUCCESS):
    return AnswerAnalysisResult(
        student_id=student_id,
        exam="DBMS",
        year="2025",
        question_id=question_id,
        part_id=part_id,
        topic="Normalization",
        marks_obtained=8,
        max_marks=10,
        performance_score=0.8,
        concept_score=0.7,
        cognitive_score=0.6,
        learning_score=0.735,
        concept_reference_source="model_answer",
        student_level="understand",
        required_level="apply",
        status=status,
    )


class TimingQuestionAgent:
    def __init__(self):
        self.called_at = None

    def run(self, exam_id, exam_data, question, part, rubric_criteria):
        self.called_at = datetime.now(timezone.utc)
        return QuestionMappingResult(
            exam_id=exam_id,
            question_id="1",
            part_id="a",
            question_text="Explain normalization",
            max_marks=10,
            topic_ids=["Normalization"],
            mapping_confidence=0.7,
        )


class NoOpAnswerAgent:
    def run(self, exam_data, student, model_answers, mappings, **weights):
        return []


class NoOpCohortAgent:
    def run(self, exam_id, exam_data, analyses, **thresholds):
        return CohortPredictionResult(exam_id=exam_id)


class ReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.exam = {
            "exam": "DBMS",
            "year": 2025,
            "questions": [
                {
                    "question_number": 1,
                    "topic": "Normalization",
                    "parts": [
                        {
                            "part": "a",
                            "question": "Analyze normalization anomalies",
                            "max_marks": 10,
                        }
                    ],
                }
            ],
        }

    def test_failed_answers_are_excluded_from_cohort_statistics(self):
        result = CohortPredictionAgent().run(
            "DBMS-2025",
            self.exam,
            [analysis("valid"), analysis("failed", status=AgentStatus.FAILED)],
        )

        self.assertEqual(result.question_summaries[0]["attempts"], 1)
        self.assertTrue(
            any(warning.code == "failed_analyses_excluded" for warning in result.warnings)
        )

    def test_input_hash_changes_when_workflow_options_change(self):
        orchestrator = ExamAnalysisOrchestrator.with_defaults(ModelRegistry())

        first = orchestrator._input_hash(
            self.exam,
            [],
            {},
            {},
            {"weak_threshold": 0.5},
        )
        second = orchestrator._input_hash(
            self.exam,
            [],
            {},
            {},
            {"weak_threshold": 0.4},
        )

        self.assertNotEqual(first, second)

    def test_run_context_starts_before_the_first_agent(self):
        question_agent = TimingQuestionAgent()
        orchestrator = ExamAnalysisOrchestrator(
            ModelRegistry(),
            question_agent,
            NoOpAnswerAgent(),
            NoOpCohortAgent(),
        )

        result = orchestrator.run(self.exam, [])

        self.assertLessEqual(result.context.started_at, question_agent.called_at)

    def test_unregistered_optional_model_returns_typed_warning(self):
        model, warning = ModelRegistry().try_get("forecaster")

        self.assertIsNone(model)
        self.assertEqual(warning.code, "model_not_registered")
        self.assertEqual(warning.capability, "forecaster")

    def test_topic_mapping_confidence_is_separate_from_bloom_confidence(self):
        question = self.exam["questions"][0]
        part = question["parts"][0]

        result = QuestionKnowledgeAgent().run(
            "DBMS-2025",
            self.exam,
            question,
            part,
        )

        self.assertEqual(result.mapping_confidence, 0.7)
        self.assertEqual(result.bloom_confidence, 0.6)

    def test_default_agents_use_registry_models_and_report_loaded_versions(self):
        calls = {"cognitive": 0, "weak_topic": 0, "similarity": 0}

        class CognitiveModel:
            def predict_level(self, _text):
                return "analyze", 0.91

            def compare(self, _question, _answer, use_strict=False):
                return {
                    "required_level": "analyze",
                    "student_level": "apply",
                    "cognitive_score": 0.75,
                }

        class WeakTopicModel:
            pipeline = object()

            def predict(self, _rows):
                return []

        registry = ModelRegistry()
        registry.register(
            "cognitive_bloom", "cognitive-test-v1",
            lambda: calls.__setitem__("cognitive", calls["cognitive"] + 1)
            or CognitiveModel(),
        )
        registry.register(
            "weak_topic", "weak-test-v1",
            lambda: calls.__setitem__("weak_topic", calls["weak_topic"] + 1)
            or WeakTopicModel(),
        )
        registry.register(
            "similarity", "similarity-test-v1",
            lambda: calls.__setitem__("similarity", calls["similarity"] + 1)
            or object(),
        )
        student = {
            "student_id": "s1",
            "year": 2025,
            "answers": [{
                "question_number": 1,
                "parts": [{
                    "part": "a", "answer": "A detailed answer",
                    "score": 8, "max_marks": 10,
                }],
            }],
        }

        result = ExamAnalysisOrchestrator.with_defaults(registry).run(
            self.exam, [student], {"1": {"a": "A reference answer"}},
        )

        self.assertEqual(calls, {"cognitive": 1, "weak_topic": 1, "similarity": 0})
        self.assertEqual(
            result.context.model_versions,
            {"cognitive_bloom": "cognitive-test-v1", "weak_topic": "weak-test-v1"},
        )
        self.assertEqual(result.question_mappings[0].required_bloom_level, "analyze")
        self.assertEqual(result.answer_analyses[0].cognitive_score, 0.75)

    @patch("src.agents.answer_misconception_agent.build_student_reports")
    def test_one_bad_answer_part_does_not_discard_sibling_part(self, build_mock):
        build_mock.side_effect = [
            RuntimeError("bad part"),
            [
                {
                    "student_id": "s1",
                    "exam": "DBMS",
                    "year": "2025",
                    "question": "1",
                    "part": "b",
                    "score": 4.0,
                    "max_marks": 5.0,
                    "performance_score": 0.8,
                    "concept_score": 0.7,
                    "concept_reference_source": "model_answer",
                    "cognitive_score": 0.6,
                    "student_level": "understand",
                    "required_level": "apply",
                    "topic": "Normalization",
                    "learning_score": 0.735,
                }
            ],
        ]
        student = {
            "student_id": "s1",
            "year": 2025,
            "answers": [
                {
                    "question_number": 1,
                    "parts": [
                        {"part": "a", "answer": "bad", "score": 1, "max_marks": 5},
                        {"part": "b", "answer": "good", "score": 4, "max_marks": 5},
                    ],
                }
            ],
        }
        mappings = {
            ("1", part): QuestionMappingResult(
                exam_id="DBMS-2025",
                question_id="1",
                part_id=part,
                question_text=part,
                max_marks=5,
                topic_ids=["Normalization"],
                mapping_confidence=0.7,
            )
            for part in ("a", "b")
        }

        results = AnswerMisconceptionAgent().run(
            self.exam,
            student,
            {"1": {"a": "reference", "b": "reference"}},
            mappings,
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].status, AgentStatus.FAILED)
        self.assertEqual(results[1].part_id, "b")
        self.assertEqual(results[1].marks_obtained, 4.0)


if __name__ == "__main__":
    unittest.main()
