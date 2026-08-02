from src.agents.contracts import AgentStatus, AgentWarning, QuestionMappingResult
from src.analysis.scoring.cognitive import detect_level
from src.analytics.topic_utils import resolve_topic


class QuestionKnowledgeAgent:
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
        bloom_level, bloom_confidence = detect_level(question_text, "question")
        return QuestionMappingResult(
            exam_id=exam_id,
            question_id=question_id,
            part_id=part_id,
            question_text=question_text,
            max_marks=float(part.get("max_marks", 0) or 0),
            topic_ids=[str(topic)],
            rubric_criteria=list(rubric_criteria or []),
            required_bloom_level=bloom_level,
            mapping_confidence=bloom_confidence,
            status=AgentStatus.PARTIAL,
            warnings=[AgentWarning(
                code="knowledge_retrieval_unavailable",
                message=(
                    "Phase 1 uses exam metadata; no knowledge retriever is "
                    "configured"
                ),
                capability="knowledge_retrieval",
            )],
        )
