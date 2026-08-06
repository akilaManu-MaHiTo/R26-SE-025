"""v2 Question Knowledge Agent.

Converts one question and its rubric into a normalized, evidence-backed
mapping: canonical topics with scores, concept IDs, Bloom level, question
type, difficulty, source citations, and a confidence/status summary.

The agent runs once per unique question version and its result is meant to
be reused for every student attempt to that question.
"""

from __future__ import annotations

import re

from src.agents.contracts import AgentRunContext, AgentWarning
from src.agents.v2.contracts import (
    QuestionKnowledgeResult,
    TopicMapping,
    V2AgentStatus,
)
from src.agents.v2.providers import (
    RequiredBloomProvider,
    RubricEvidenceRetriever,
    RuleBasedDifficultyEstimator,
    RuleBasedQuestionTypeClassifier,
    RuleBasedTopicMapper,
)
from src.agents.v2.records import (
    AssessmentRecord,
    CourseRecord,
    QuestionRecord,
)

LOW_CONFIDENCE_THRESHOLD = 0.4


class QuestionKnowledgeAgentV2:
    def __init__(
        self,
        bloom_provider: RequiredBloomProvider | None = None,
        topic_mapper: RuleBasedTopicMapper | None = None,
        question_type_classifier: RuleBasedQuestionTypeClassifier | None = None,
        difficulty_estimator: RuleBasedDifficultyEstimator | None = None,
        knowledge_retriever: object | None = None,
    ):
        self.bloom_provider = bloom_provider or RequiredBloomProvider()
        self.topic_mapper = topic_mapper or RuleBasedTopicMapper()
        self.question_type_classifier = (
            question_type_classifier or RuleBasedQuestionTypeClassifier()
        )
        self.difficulty_estimator = difficulty_estimator or RuleBasedDifficultyEstimator()
        self.knowledge_retriever = knowledge_retriever

    @staticmethod
    def _slugify(text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug[:60] or "criterion"

    def _concept_ids(self, question: QuestionRecord) -> list[str]:
        concept_ids: list[str] = []
        for index, criterion in enumerate(question.rubric_criteria):
            slug = self._slugify(criterion.point)
            concept_ids.append(
                f"{question.question_id}:{slug}" if slug else f"{question.question_id}:c{index}"
            )
        return concept_ids

    def _rubric_citations(
        self,
        question: QuestionRecord,
        assessment: AssessmentRecord,
    ) -> list:
        return RubricEvidenceRetriever().retrieve(
            question.question_text,
            {
                "rubric_id": assessment.rubric_id or assessment.assessment_id,
                "rubric_filename": assessment.rubric_filename,
                "model_answer": question.model_answer,
            },
        )

    def _mapping_confidence(
        self,
        topic_mappings: list[TopicMapping],
        bloom_confidence: float,
        type_confidence: float,
        mode: str,
    ) -> float:
        topic_score = topic_mappings[0].score if topic_mappings else 0.0
        if mode == "token":
            topic_component = topic_score * 0.5
        else:
            topic_component = topic_score
        return round(
            min(
                1.0,
                0.5 * topic_component + 0.3 * bloom_confidence + 0.2 * type_confidence,
            ),
            4,
        )

    def _status(
        self,
        confidence: float,
        mode: str,
        warnings: list[AgentWarning],
    ) -> V2AgentStatus:
        codes = {warning.code for warning in warnings}
        if confidence < LOW_CONFIDENCE_THRESHOLD or mode == "token":
            return V2AgentStatus.REVIEW_REQUIRED
        if codes & {
            "bloom_fallback_used",
            "topic_mapper_unavailable",
            "knowledge_retrieval_unavailable",
        }:
            return V2AgentStatus.PARTIAL
        return V2AgentStatus.SUCCESS

    def run(
        self,
        context: AgentRunContext,
        course: CourseRecord,
        assessment: AssessmentRecord,
        question: QuestionRecord,
    ) -> QuestionKnowledgeResult:
        if not question.question_text.strip():
            return QuestionKnowledgeResult(
                question_id=question.question_id,
                assessment_id=assessment.assessment_id,
                status=V2AgentStatus.FAILED,
                warnings=[
                    AgentWarning(
                        code="question_text_unavailable",
                        message="Question has no text and cannot be mapped",
                        capability="question_mapping",
                    )
                ],
            )

        warnings: list[AgentWarning] = []

        bloom, bloom_warnings = self.bloom_provider.predict_question(question.question_text)
        warnings.extend(bloom_warnings)

        topic_mappings, mode = self.topic_mapper.map_question(question, course)
        if mode == "token":
            warnings.append(
                AgentWarning(
                    code="topic_mapping_low_confidence",
                    message="Only token candidates could be derived; semantic mapping unavailable",
                    capability="topic_mapping",
                )
            )
        elif mode == "empty":
            warnings.append(
                AgentWarning(
                    code="topic_mapper_unavailable",
                    message="No topic could be derived from the question",
                    capability="topic_mapping",
                )
            )

        question_type, type_confidence = self.question_type_classifier.classify(
            question.question_text
        )
        difficulty = self.difficulty_estimator.estimate(
            question,
            bloom.level,
            question_type,
        )

        citations = self._rubric_citations(question, assessment)
        if self.knowledge_retriever is None:
            warnings.append(
                AgentWarning(
                    code="knowledge_retrieval_unavailable",
                    message="No course-material retriever is configured; rubric evidence only",
                    capability="knowledge_retrieval",
                )
            )
        else:
            try:
                retrieved = self.knowledge_retriever.retrieve(
                    question.question_text,
                    {
                        "subject_code": assessment.subject_code,
                        "course_id": course.course_id,
                        "assessment_id": assessment.assessment_id,
                    },
                )
                citations.extend(retrieved or [])
            except Exception as exc:
                warnings.append(
                    AgentWarning(
                        code="knowledge_retrieval_unavailable",
                        message=str(exc),
                        capability="knowledge_retrieval",
                    )
                )

        confidence = self._mapping_confidence(
            topic_mappings,
            bloom.confidence,
            type_confidence,
            mode,
        )
        status = self._status(confidence, mode, warnings)

        return QuestionKnowledgeResult(
            question_id=question.question_id,
            assessment_id=assessment.assessment_id,
            canonical_topic_ids=topic_mappings,
            concept_ids=self._concept_ids(question),
            rubric_criteria=question.rubric_criteria,
            required_bloom_level=bloom.level,
            question_type=question_type,
            difficulty=difficulty,
            source_citations=citations,
            mapping_confidence=confidence,
            status=status,
            warnings=warnings,
        )


def build_question_knowledge_agent(registry=None) -> QuestionKnowledgeAgentV2:
    """Build the agent, wiring the Bloom model through a ModelRegistry if given."""
    if registry is not None:
        bloom_provider = RequiredBloomProvider(
            lambda: registry.try_get("cognitive_bloom")
        )
        return QuestionKnowledgeAgentV2(bloom_provider=bloom_provider)
    return QuestionKnowledgeAgentV2()
