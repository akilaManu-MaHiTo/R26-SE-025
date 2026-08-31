"""Unit tests for LiveQuestionRecommender in VivaEvaluationEngine."""
import json
import unittest

from VivaEvaluationEngine.services.live_question_recommender import (
    LiveQuestionRecommender,
    _extract_json_object,
    _is_similar,
)


class TestLiveQuestionRecommender(unittest.TestCase):
    def test_is_similar(self):
        q1 = "How did you handle concurrent transactions in PostgreSQL?"
        q2 = "How did you handle concurrent transactions in Postgres?"
        q3 = "What hashing algorithm was used for passwords?"
        self.assertTrue(_is_similar(q1, q2))
        self.assertFalse(_is_similar(q1, q3))

    def test_extract_json_object(self):
        raw = '```json\n{"analysis": {"topics": ["Auth"]}, "recommendations": []}\n```'
        extracted = _extract_json_object(raw)
        self.assertIsNotNone(extracted)
        self.assertEqual(extracted.get("analysis", {}).get("topics"), ["Auth"])

    def test_fallback_recommendations(self):
        recommender = LiveQuestionRecommender()
        res = recommender.generate_fallback_recommendations(
            candidate_transcript="We built an AI platform using PyTorch.",
            project_context={"project": "Gradex AI", "notes": "Python, React"},
        )
        self.assertEqual(res["status"], "fallback")
        self.assertEqual(res["source"], "heuristic")
        self.assertTrue(len(res["recommendations"]) > 0)
        first_q = res["recommendations"][0]
        self.assertIn("question", first_q)
        self.assertIn("bloom_level", first_q)
        self.assertIn("difficulty", first_q)
        self.assertIn("category", first_q)

    def test_parse_and_validate_with_bloom_levels(self):
        mock_output = json.dumps({
            "analysis": {
                "topics": ["WebSocket", "Concurrency"],
                "claims": ["Supports 10000 live streams"],
                "gaps": ["No backpressure mechanism explained"]
            },
            "recommendations": [
                {
                    "question": "How does the server handle WebSocket connection drops and reconnection storms?",
                    "reason": "Tests resilience against abrupt client disconnects.",
                    "bloom_level": "Analyze",
                    "difficulty": "advanced",
                    "priority": "high",
                    "category": "Resilience"
                },
                {
                    "question": "Can you explain how state synchronization works between clients?",
                    "reason": "Tests understanding of distributed state.",
                    "bloom_level": "Understand",
                    "difficulty": "basic",
                    "priority": "medium",
                    "category": "Architecture"
                }
            ]
        })

        recommender = LiveQuestionRecommender()
        res = recommender.parse_and_validate(mock_output, asked_questions=[])
        self.assertEqual(res["status"], "success")
        self.assertEqual(len(res["recommendations"]), 2)
        self.assertEqual(res["recommendations"][0]["bloom_level"], "Analyze")
        self.assertEqual(res["recommendations"][0]["difficulty"], "advanced")
        self.assertEqual(res["recommendations"][0]["priority"], "high")

    def test_recommend_questions_with_mock_chat(self):
        def mock_chat_fn(system_prompt, payload):
            return json.dumps({
                "analysis": {
                    "topics": ["Kafka", "Streaming"],
                    "claims": ["Guaranteed exactly-once delivery"],
                    "gaps": ["Consumer group rebalance lag"]
                },
                "recommendations": [
                    {
                        "question": "How do you achieve exactly-once semantics end-to-end?",
                        "reason": "Verifies Kafka transactional producer/consumer setup.",
                        "bloom_level": "Evaluate",
                        "difficulty": "advanced",
                        "priority": "high",
                        "category": "Data Consistency"
                    }
                ]
            })

        recommender = LiveQuestionRecommender(chat_fn=mock_chat_fn)
        res = recommender.recommend_questions(
            candidate_transcript="We stream data with Kafka and guarantee exactly-once processing.",
            project_context={"project": "DataPipeline"},
            asked_questions=["What is Kafka?"],
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(len(res["recommendations"]), 1)
        self.assertEqual(res["recommendations"][0]["bloom_level"], "Evaluate")
        self.assertIn("exactly-once", res["recommendations"][0]["question"])


if __name__ == "__main__":
    unittest.main()
