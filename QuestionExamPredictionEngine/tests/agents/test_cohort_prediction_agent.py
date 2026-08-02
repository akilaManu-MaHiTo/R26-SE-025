import unittest

from src.agents.cohort_prediction_agent import CohortPredictionAgent
from src.agents.contracts import AgentStatus, AnswerAnalysisResult


def answer(student_id: str, learning_score: float) -> AnswerAnalysisResult:
    return AnswerAnalysisResult(
        student_id=student_id,
        exam="DBMS",
        year="2025",
        question_id="1",
        part_id="a",
        topic="Normalization",
        marks_obtained=learning_score * 10,
        max_marks=10,
        performance_score=learning_score,
        concept_score=learning_score,
        cognitive_score=learning_score,
        learning_score=learning_score,
        concept_reference_source="model_answer",
        student_level="understand",
        required_level="apply",
    )


class CohortPredictionAgentTests(unittest.TestCase):
    def test_returns_current_analytics_without_fake_forecast(self):
        result = CohortPredictionAgent().run(
            "dbms-2025",
            {"questions": []},
            [answer("s1", 0.2), answer("s2", 0.3)],
        )

        self.assertEqual(result.status, AgentStatus.PARTIAL)
        self.assertTrue(result.question_summaries)
        self.assertTrue(result.misunderstood_questions)
        self.assertTrue(result.weak_topics)
        self.assertIn("Normalization", result.historical_trends)
        self.assertEqual(result.future_topic_probabilities, [])
        self.assertEqual(result.warnings[0].code, "forecaster_unavailable")

    def test_empty_cohort_is_valid_partial_result(self):
        result = CohortPredictionAgent().run("dbms-2025", {}, [])

        self.assertEqual(result.status, AgentStatus.PARTIAL)
        self.assertEqual(result.question_summaries, [])
        self.assertEqual(result.future_topic_probabilities, [])


if __name__ == "__main__":
    unittest.main()
