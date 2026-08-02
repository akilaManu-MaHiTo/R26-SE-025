from src.agents.contracts import (
    AgentStatus,
    AgentWarning,
    AnswerAnalysisResult,
    QuestionMappingResult,
)
from src.analysis.exam_analysis import build_student_reports


class AnswerMisconceptionAgent:
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
        reports = build_student_reports(
            exam_data,
            [student],
            model_answers,
            performance_weight=performance_weight,
            concept_weight=concept_weight,
            cognitive_weight=cognitive_weight,
        )
        warning = AgentWarning(
            code="misconception_extractor_unavailable",
            message=(
                "Phase 1 preserves analytical scores without structured "
                "misconception extraction"
            ),
            capability="misconception_extraction",
        )
        results = []
        for report in reports:
            question_id = str(report["question"])
            part_id = str(report["part"])
            mapping = mappings.get((question_id, part_id))
            topic = (
                mapping.topic_ids[0]
                if mapping and mapping.topic_ids
                else str(report["topic"])
            )
            weak_concepts = (
                [topic]
                if float(report["concept_score"]) < 0.5
                else []
            )
            results.append(
                AnswerAnalysisResult(
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
                    concept_reference_source=str(
                        report["concept_reference_source"]
                    ),
                    student_level=str(report["student_level"]),
                    required_level=str(report["required_level"]),
                    weak_concepts=weak_concepts,
                    status=AgentStatus.PARTIAL,
                    warnings=[warning],
                )
            )
        return results
