import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from pydantic import ValidationError

from src.agents.contracts import (
    AgentRunContext,
    AgentStatus,
    AgentWorkflowResult,
    CohortPredictionResult,
)
from src.api.routers.agent_workflows import analyze_exam_agent_workflow
from src.api.schemas.requests import AgentWorkflowAnalyzeExamRequest


class AgentWorkflowRouterTests(unittest.TestCase):
    @patch("src.api.routers.agent_workflows.get_model_answer", return_value={})
    @patch("src.api.routers.agent_workflows.get_student_answers", return_value=[])
    @patch(
        "src.api.routers.agent_workflows.get_exam_data",
        return_value={"exam": "DBMS", "year": 2025, "questions": []},
    )
    @patch("src.api.routers.agent_workflows.get_agent_orchestrator")
    def test_route_returns_the_orchestrated_result(
        self,
        orchestrator_dependency,
        _exam_dependency,
        _answers_dependency,
        _model_answer_dependency,
    ):
        expected = AgentWorkflowResult(
            context=AgentRunContext(
                run_id="run-1",
                input_hash="abc",
                exam_id="DBMS-2025",
                started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            ),
            question_mappings=[],
            answer_analyses=[],
            cohort_result=CohortPredictionResult(
                exam_id="DBMS-2025",
                status=AgentStatus.PARTIAL,
            ),
            status=AgentStatus.PARTIAL,
        )
        orchestrator = Mock()
        orchestrator.run.return_value = expected
        orchestrator_dependency.return_value = orchestrator

        response = analyze_exam_agent_workflow(
            AgentWorkflowAnalyzeExamRequest(year=2025)
        )

        self.assertEqual(response.result, expected)

    def test_request_rejects_learning_weights_that_do_not_sum_to_one(self):
        with self.assertRaises(ValidationError):
            AgentWorkflowAnalyzeExamRequest(
                year=2025,
                performance_weight=0.5,
                concept_weight=0.2,
                cognitive_weight=0.1,
            )


if __name__ == "__main__":
    unittest.main()
