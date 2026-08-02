import unittest

from src.agents.contracts import AgentStatus
from src.agents.question_knowledge_agent import QuestionKnowledgeAgent


class QuestionKnowledgeAgentTests(unittest.TestCase):
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

    def test_maps_current_topic_bloom_and_rubric(self):
        question = self.exam["questions"][0]
        part = question["parts"][0]

        result = QuestionKnowledgeAgent().run(
            "dbms-2025",
            self.exam,
            question,
            part,
            rubric_criteria=["Identify update anomalies"],
        )

        self.assertEqual(result.topic_ids, ["Normalization"])
        self.assertEqual(result.required_bloom_level, "analyze")
        self.assertEqual(result.rubric_criteria, ["Identify update anomalies"])
        self.assertEqual(result.status, AgentStatus.PARTIAL)
        self.assertEqual(
            result.warnings[0].code,
            "knowledge_retrieval_unavailable",
        )

    def test_uses_question_part_fallback_topic(self):
        question = {"question_number": 3, "parts": []}
        part = {
            "part": "b",
            "question": "State one property",
            "max_marks": 2,
        }

        result = QuestionKnowledgeAgent().run(
            "dbms-2025",
            {"questions": []},
            question,
            part,
        )

        self.assertEqual(result.topic_ids, ["Q3b"])


if __name__ == "__main__":
    unittest.main()
