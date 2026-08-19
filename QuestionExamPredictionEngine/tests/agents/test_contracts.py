import unittest
from datetime import datetime

from pydantic import ValidationError

from src.agents.contracts import (
    AgentRunContext,
    AgentStatus,
    AgentWarning,
    AnswerAnalysisResult,
    QuestionMappingResult,
)


class AgentContractTests(unittest.TestCase):
    def test_question_mapping_rejects_confidence_outside_unit_interval(self):
        with self.assertRaises(ValidationError):
            QuestionMappingResult(
                exam_id="dbms-2025",
                question_id="1",
                part_id="a",
                question_text="Explain normalization",
                max_marks=10,
                topic_ids=["Normalization"],
                mapping_confidence=1.1,
            )

    def test_answer_result_converts_to_existing_analytics_record(self):
        result = AnswerAnalysisResult(
            student_id="student-1",
            exam="DBMS",
            year="2025",
            question_id="1",
            part_id="a",
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
        )

        record = result.to_analytics_record()

        self.assertEqual(record["question"], "1")
        self.assertEqual(record["part"], "a")
        self.assertEqual(record["score"], 8.0)
        self.assertNotIn("misconceptions", record)

    def test_run_context_requires_timezone_aware_timestamp(self):
        with self.assertRaises(ValidationError):
            AgentRunContext(
                run_id="run-1",
                input_hash="abc",
                exam_id="dbms-2025",
                started_at=datetime(2025, 1, 1),
            )

    def test_partial_result_can_carry_typed_warning(self):
        warning = AgentWarning(
            code="knowledge_retrieval_unavailable",
            message="No knowledge retriever is configured",
            capability="knowledge_retrieval",
        )
        self.assertEqual(AgentStatus.PARTIAL.value, "partial")
        self.assertEqual(warning.capability, "knowledge_retrieval")


if __name__ == "__main__":
    unittest.main()
