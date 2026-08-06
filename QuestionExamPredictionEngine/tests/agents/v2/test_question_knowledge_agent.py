import unittest
from datetime import datetime, timezone

from src.agents.contracts import AgentRunContext
from src.agents.v2.contracts import V2AgentStatus
from src.agents.v2.normalize import (
    normalize_assessment,
    normalize_course,
    normalize_question,
)
from src.agents.v2.question_knowledge_agent import (
    QuestionKnowledgeAgentV2,
    build_question_knowledge_agent,
)
from src.agents.v2.providers import (
    RequiredBloomProvider,
    RuleBasedTopicMapper,
)
from src.agents.v2.records import QuestionRecord, RubricCriterion

COURSE_DOC = {
    "_id": "ObjectId('64b8f1a2c39d2a1b5e000001')",
    "code": "SE3040",
    "name": "Software Architecture",
}

RUBRIC_DOC = {
    "_id": "ObjectId('64b8f1a2c39d2a1b5e000002')",
    "session_name": "Semester 1 Final Exam",
    "subject_code": "SE3040",
    "filename": "rubric.pdf",
    "parsed_at": 1720000000.123,
    "questions": [
        {
            "question_no": "01",
            "question_text": "Explain two-phase locking.",
            "max_marks": 5,
            "criteria": [
                {"point": "Mentions growing phase", "marks": 2},
                {"point": "Defines lock point", "marks": 1},
            ],
            "model_answer": "Two-phase locking grows locks then shrinks.",
        }
    ],
}


def make_context():
    return AgentRunContext(
        run_id="run-1",
        input_hash="abc",
        exam_id="SE3040",
        started_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )


def make_fixtures():
    course = normalize_course(COURSE_DOC)
    assessment = normalize_assessment(RUBRIC_DOC, course)
    question = normalize_question(RUBRIC_DOC["questions"][0], assessment)
    return course, assessment, question


class FakeBloomModel:
    def predict_level(self, text):
        return "understand", 0.85


class QuestionKnowledgeAgentV2Tests(unittest.TestCase):
    def test_run_returns_complete_mapping(self):
        course, assessment, question = make_fixtures()
        agent = QuestionKnowledgeAgentV2(
            bloom_provider=RequiredBloomProvider(lambda: (FakeBloomModel(), None)),
            topic_mapper=RuleBasedTopicMapper(
                canonical_topics=["Two-Phase Locking", "Database Programming"]
            ),
        )
        result = agent.run(make_context(), course, assessment, question)

        self.assertEqual(result.question_id, question.question_id)
        self.assertEqual(result.required_bloom_level, "understand")
        self.assertEqual(result.question_type, "explanation")
        self.assertGreaterEqual(result.difficulty, 1)
        self.assertLessEqual(result.difficulty, 5)
        self.assertTrue(result.canonical_topic_ids)
        self.assertTrue(result.concept_ids)
        self.assertTrue(result.source_citations)
        self.assertEqual(result.status, V2AgentStatus.PARTIAL)

    def test_retrieval_unavailable_warning_emitted(self):
        course, assessment, question = make_fixtures()
        result = QuestionKnowledgeAgentV2(
            bloom_provider=RequiredBloomProvider(lambda: (FakeBloomModel(), None))
        ).run(make_context(), course, assessment, question)
        codes = {warning.code for warning in result.warnings}
        self.assertIn("knowledge_retrieval_unavailable", codes)

    def test_review_required_for_low_confidence_token_mapping(self):
        course, assessment, question = make_fixtures()
        question = QuestionRecord(
            question_id="assessment:9",
            assessment_id=assessment.assessment_id,
            question_no_raw="09",
            question_no_normalized="9",
            question_text="xyzzy quux widget",
            max_marks=2,
            rubric_criteria=[RubricCriterion(point="Vague", marks=2)],
        )
        result = QuestionKnowledgeAgentV2(
            bloom_provider=RequiredBloomProvider(lambda: (FakeBloomModel(), None)),
            topic_mapper=RuleBasedTopicMapper(canonical_topics=["Database Programming"]),
        ).run(make_context(), course, assessment, question)
        self.assertEqual(result.status, V2AgentStatus.REVIEW_REQUIRED)
        self.assertLess(result.mapping_confidence, 0.4)

    def test_failed_when_question_has_no_text(self):
        course, assessment, _ = make_fixtures()
        question = QuestionRecord(
            question_id="assessment:2",
            assessment_id=assessment.assessment_id,
            question_no_raw="02",
            question_no_normalized="2",
            question_text="",
            max_marks=5,
        )
        result = QuestionKnowledgeAgentV2().run(make_context(), course, assessment, question)
        self.assertEqual(result.status, V2AgentStatus.FAILED)

    def test_build_question_knowledge_agent_with_registry(self):
        from src.agents.model_registry import ModelRegistry

        registry = ModelRegistry()
        registry.register("cognitive_bloom", "fake-v1", lambda: FakeBloomModel())
        agent = build_question_knowledge_agent(registry)
        self.assertIsInstance(agent, QuestionKnowledgeAgentV2)


if __name__ == "__main__":
    unittest.main()
