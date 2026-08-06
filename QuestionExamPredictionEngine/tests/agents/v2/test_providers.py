import unittest

from src.agents.v2.providers import (
    RequiredBloomProvider,
    RuleBasedDifficultyEstimator,
    RuleBasedQuestionTypeClassifier,
    RuleBasedTopicMapper,
)
from src.agents.v2.records import QuestionRecord, RubricCriterion

QUESTION = QuestionRecord(
    question_id="assessment:1",
    assessment_id="assessment",
    question_no_raw="01",
    question_no_normalized="1",
    question_text="Compare B-tree and hash indexing strategies",
    max_marks=10,
    rubric_criteria=[
        RubricCriterion(point="Mentions B-tree structure", marks=3),
        RubricCriterion(point="Mentions hash structure", marks=3),
    ],
    model_answer="B-tree keeps data sorted; hash gives O(1) lookups",
)


class FakeBloomModel:
    def predict_level(self, text):
        return "analyze", 0.9


class RequiredBloomProviderTests(unittest.TestCase):
    def test_uses_model_when_available(self):
        provider = RequiredBloomProvider(lambda: (FakeBloomModel(), None))
        result, warnings = provider.predict_question("Compare two strategies")
        self.assertTrue(result.used_model)
        self.assertEqual(result.level, "analyze")
        self.assertEqual(warnings, [])

    def test_falls_back_to_heuristic_when_model_missing(self):
        provider = RequiredBloomProvider(lambda: (None, None))
        result, warnings = provider.predict_question("Compare two strategies")
        self.assertFalse(result.used_model)
        self.assertEqual(warnings[0].code, "bloom_fallback_used")


class RuleBasedTopicMapperTests(unittest.TestCase):
    def test_declared_topic_wins(self):
        question = QUESTION.model_copy(update={"topic_id": "Database Indexing"})
        mappings, mode = RuleBasedTopicMapper(canonical_topics=["Database Indexing"]).map_question(
            question
        )
        self.assertEqual(mode, "declared")
        self.assertEqual(mappings[0].topic_id, "Database Indexing")
        self.assertEqual(mappings[0].score, 1.0)

    def test_token_candidates_when_no_canonical_topics(self):
        question = QUESTION.model_copy(update={"topic_id": None})
        mappings, mode = RuleBasedTopicMapper(canonical_topics=[]).map_question(question)
        self.assertEqual(mode, "token")
        self.assertTrue(mappings)
        self.assertTrue(all(mapping.score <= 0.3 for mapping in mappings))

    def test_no_text_returns_empty(self):
        question = QuestionRecord(
            question_id="assessment:1",
            assessment_id="assessment",
            question_no_raw="01",
            question_no_normalized="1",
            question_text="",
            max_marks=5,
        )
        mappings, mode = RuleBasedTopicMapper(canonical_topics=["Database Indexing"]).map_question(
            question
        )
        self.assertEqual(mode, "empty")
        self.assertEqual(mappings, [])


class RuleBasedQuestionTypeClassifierTests(unittest.TestCase):
    def test_comparison_keywords(self):
        question_type, confidence = RuleBasedQuestionTypeClassifier().classify(
            "Compare and contrast two strategies"
        )
        self.assertEqual(question_type, "comparison")
        self.assertGreater(confidence, 0.5)

    def test_empty_text(self):
        question_type, confidence = RuleBasedQuestionTypeClassifier().classify("")
        self.assertIsNone(question_type)
        self.assertEqual(confidence, 0.0)


class RuleBasedDifficultyEstimatorTests(unittest.TestCase):
    def test_higher_bloom_level_increases_difficulty(self):
        estimator = RuleBasedDifficultyEstimator()
        low = estimator.estimate(QUESTION, bloom_level="remember")
        high = estimator.estimate(QUESTION, bloom_level="create")
        self.assertLess(low, high)
        self.assertGreaterEqual(low, 1)
        self.assertLessEqual(high, 5)


if __name__ == "__main__":
    unittest.main()
