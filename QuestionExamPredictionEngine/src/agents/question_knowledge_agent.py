from collections.abc import Callable
from typing import Any

from src.agents.contracts import AgentStatus, AgentWarning, QuestionMappingResult
from src.analysis.scoring.cognitive import detect_level
from src.analytics.topic_utils import resolve_topic


ModelProvider = Callable[[], tuple[Any | None, AgentWarning | None]]


class QuestionKnowledgeAgent:
    def __init__(self, cognitive_model_provider: ModelProvider | None = None):
        self.cognitive_model_provider = cognitive_model_provider

    def _detect_bloom(self, question_text: str):
        if self.cognitive_model_provider is None:
            level, confidence = detect_level(question_text, "question")
            return level, confidence, []

        model, warning = self.cognitive_model_provider()
        warnings = [warning] if warning else []
        if model is None:
            level, confidence = detect_level(question_text, "question")
            return level, confidence, warnings

        level, confidence = model.predict_level(question_text)
        return str(level), float(confidence), warnings

    def run(
        self,
        exam_id: str,
        exam_data: dict,
        question: dict,
        part: dict,
        rubric_criteria: list[str] | None = None,
    ) -> QuestionMappingResult:
        question_id = str(question.get("question_number", ""))
        part_id = str(part.get("part", ""))
        question_text = str(part.get("question", ""))
        topic = resolve_topic(
            exam_data,
            question_id,
            part_id,
            default=f"Q{question_id}{part_id}",
        )
        has_declared_topic = bool(part.get("topic") or question.get("topic"))
        bloom_level, bloom_confidence, model_warnings = self._detect_bloom(
            question_text
        )
        warnings = model_warnings + [
            AgentWarning(
                code="knowledge_retrieval_unavailable",
                message=(
                    "Phase 1 uses exam metadata; no knowledge retriever is "
                    "configured"
                ),
                capability="knowledge_retrieval",
            )
        ]
        return QuestionMappingResult(
            exam_id=exam_id,
            question_id=question_id,
            part_id=part_id,
            question_text=question_text,
            max_marks=float(part.get("max_marks", 0) or 0),
            topic_ids=[str(topic)],
            rubric_criteria=list(rubric_criteria or []),
            required_bloom_level=bloom_level,
            mapping_confidence=0.7 if has_declared_topic else 0.3,
            bloom_confidence=bloom_confidence,
            status=AgentStatus.PARTIAL,
            warnings=warnings,
        )
