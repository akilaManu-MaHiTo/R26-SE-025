from collections.abc import Callable
from typing import Any

from src.agents.contracts import (
    AgentStatus,
    AgentWarning,
    AnswerAnalysisResult,
    QuestionMappingResult,
)
from src.analysis.exam_analysis import build_student_reports
from src.analysis.scoring.cognitive import cognitive_score


ModelProvider = Callable[[], tuple[Any | None, AgentWarning | None]]


class AnswerMisconceptionAgent:
    def __init__(self, cognitive_model_provider: ModelProvider | None = None):
        self.cognitive_model_provider = cognitive_model_provider

    @staticmethod
    def _partial_result(
        report: dict,
        mappings: dict[tuple[str, str], QuestionMappingResult],
        warnings: list[AgentWarning],
    ) -> AnswerAnalysisResult:
        question_id = str(report["question"])
        part_id = str(report["part"])
        mapping = mappings.get((question_id, part_id))
        topic = (
            mapping.topic_ids[0]
            if mapping and mapping.topic_ids
            else str(report["topic"])
        )
        weak_concepts = [topic] if float(report["concept_score"]) < 0.5 else []
        return AnswerAnalysisResult(
            student_id=str(report["student_id"]),
            exam=str(report["exam"]),
            year=str(report["year"]),
            question_id=question_id,
            part_id=part_id,
            topic=topic,
            marks_obtained=float(report["score"]),
            max_marks=float(report["max_marks"]),
            performance_score=float(report["performance_score"]),
            concept_score=float(report["concept_score"]),
            cognitive_score=float(report["cognitive_score"]),
            learning_score=float(report["learning_score"]),
            concept_reference_source=str(report["concept_reference_source"]),
            student_level=str(report["student_level"]),
            required_level=str(report["required_level"]),
            weak_concepts=weak_concepts,
            status=AgentStatus.PARTIAL,
            warnings=warnings,
        )

    @staticmethod
    def _failed_result(
        exam_data: dict,
        student: dict,
        question_id: str,
        part: dict,
        mappings: dict[tuple[str, str], QuestionMappingResult],
    ) -> AnswerAnalysisResult:
        part_id = str(part.get("part", ""))
        mapping = mappings.get((question_id, part_id))
        topic = (
            mapping.topic_ids[0]
            if mapping and mapping.topic_ids
            else f"Q{question_id}{part_id}"
        )
        max_marks = max(float(part.get("max_marks", 1) or 1), 0.001)
        marks = max(float(part.get("score", 0) or 0), 0.0)
        return AnswerAnalysisResult(
            student_id=str(student.get("student_id", "UNKNOWN")),
            exam=str(exam_data.get("exam", "EXAM")).replace(" ", "_"),
            year=str(student.get("year", exam_data.get("year", "UNKNOWN"))),
            question_id=question_id,
            part_id=part_id,
            topic=topic,
            marks_obtained=marks,
            max_marks=max_marks,
            performance_score=min(marks / max_marks, 1.0),
            concept_score=0.0,
            cognitive_score=0.0,
            learning_score=0.0,
            concept_reference_source="unavailable",
            student_level="unknown",
            required_level="unknown",
            analysis_confidence=0.0,
            status=AgentStatus.FAILED,
            warnings=[
                AgentWarning(
                    code="answer_analysis_failed",
                    message="This answer part could not be analyzed",
                    capability="answer_analysis",
                )
            ],
        )

    def run(
        self,
        exam_data: dict,
        student: dict,
        model_answers: dict | None,
        mappings: dict[tuple[str, str], QuestionMappingResult],
        *,
        performance_weight: float = 0.6,
        concept_weight: float = 0.25,
        cognitive_weight: float = 0.15,
    ) -> list[AnswerAnalysisResult]:
        scorer = cognitive_score
        model_warning = None
        if self.cognitive_model_provider is not None:
            model, model_warning = self.cognitive_model_provider()
            if model is not None:
                scorer = model.compare

        base_warnings = []
        if model_warning:
            base_warnings.append(model_warning)
        base_warnings.append(
            AgentWarning(
                code="misconception_extractor_unavailable",
                message=(
                    "Phase 1 preserves analytical scores without structured "
                    "misconception extraction"
                ),
                capability="misconception_extraction",
            )
        )

        results = []
        for question in student.get("answers", []):
            question_id = str(question.get("question_number", ""))
            for part in question.get("parts", []):
                single_student = {
                    **student,
                    "answers": [{"question_number": question_id, "parts": [part]}],
                }
                try:
                    reports = build_student_reports(
                        exam_data,
                        [single_student],
                        model_answers,
                        performance_weight=performance_weight,
                        concept_weight=concept_weight,
                        cognitive_weight=cognitive_weight,
                        cognitive_scorer=scorer,
                    )
                    results.extend(
                        self._partial_result(report, mappings, base_warnings)
                        for report in reports
                    )
                except Exception:
                    results.append(
                        self._failed_result(
                            exam_data,
                            student,
                            question_id,
                            part,
                            mappings,
                        )
                    )
        return results
