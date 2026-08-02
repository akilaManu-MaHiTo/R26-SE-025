from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from src.agents.answer_misconception_agent import AnswerMisconceptionAgent
from src.agents.cohort_prediction_agent import CohortPredictionAgent
from src.agents.contracts import (
    AgentRunContext,
    AgentStatus,
    AgentWarning,
    AgentWorkflowResult,
    AnswerAnalysisResult,
    CohortPredictionResult,
    QuestionMappingResult,
)
from src.agents.model_registry import ModelRegistry
from src.agents.question_knowledge_agent import QuestionKnowledgeAgent


class ExamAnalysisOrchestrator:
    def __init__(
        self,
        registry,
        question_agent,
        answer_agent,
        cohort_agent,
    ):
        self.registry = registry
        self.question_agent = question_agent
        self.answer_agent = answer_agent
        self.cohort_agent = cohort_agent

    @classmethod
    def with_defaults(cls, registry: ModelRegistry):
        return cls(
            registry,
            QuestionKnowledgeAgent(),
            AnswerMisconceptionAgent(),
            CohortPredictionAgent(),
        )

    @staticmethod
    def _input_hash(exam_data, students, model_answers, rubric) -> str:
        payload = json.dumps(
            {
                "exam_data": exam_data,
                "students": students,
                "model_answers": model_answers,
                "rubric": rubric,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _failed_mapping(exam_id, question, part, exc):
        question_id = str(question.get("question_number", ""))
        part_id = str(part.get("part", ""))
        return QuestionMappingResult(
            exam_id=exam_id,
            question_id=question_id,
            part_id=part_id,
            question_text=str(part.get("question", "")),
            max_marks=float(part.get("max_marks", 0) or 0),
            topic_ids=[f"Q{question_id}{part_id}"],
            mapping_confidence=0.0,
            status=AgentStatus.FAILED,
            warnings=[
                AgentWarning(
                    code="question_mapping_failed",
                    message=str(exc),
                    capability="question_mapping",
                )
            ],
        )

    @staticmethod
    def _failed_answers(exam_data, student, mapping_index, exc):
        warning = AgentWarning(
            code="answer_analysis_failed",
            message=str(exc),
            capability="answer_analysis",
        )
        results = []
        for question in student.get("answers", []):
            question_id = str(question.get("question_number", ""))
            for part in question.get("parts", []):
                part_id = str(part.get("part", ""))
                mapping = mapping_index.get((question_id, part_id))
                max_marks = float(part.get("max_marks", 1) or 1)
                marks = max(0.0, float(part.get("score", 0) or 0))
                topic = (
                    mapping.topic_ids[0]
                    if mapping and mapping.topic_ids
                    else f"Q{question_id}{part_id}"
                )
                results.append(
                    AnswerAnalysisResult(
                        student_id=str(student.get("student_id", "UNKNOWN")),
                        exam=str(exam_data.get("exam", "EXAM")).replace(
                            " ", "_"
                        ),
                        year=str(
                            student.get(
                                "year",
                                exam_data.get("year", "UNKNOWN"),
                            )
                        ),
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
                        warnings=[warning],
                    )
                )
        return results

    def run(
        self,
        exam_data: dict,
        students: list[dict],
        model_answers: dict | None = None,
        rubric: dict[str, list[str]] | None = None,
        **options,
    ) -> AgentWorkflowResult:
        model_answers = model_answers or {}
        rubric = rubric or {}
        exam_id = (
            f"{exam_data.get('exam', 'EXAM')}-"
            f"{exam_data.get('year', 'UNKNOWN')}"
        )
        mappings = []
        mapping_index = {}
        for question in exam_data.get("questions", []):
            question_id = str(question.get("question_number", ""))
            for part in question.get("parts", []):
                part_id = str(part.get("part", ""))
                criteria = rubric.get(f"{question_id}:{part_id}", [])
                try:
                    mapping = self.question_agent.run(
                        exam_id,
                        exam_data,
                        question,
                        part,
                        criteria,
                    )
                except Exception as exc:
                    mapping = self._failed_mapping(
                        exam_id,
                        question,
                        part,
                        exc,
                    )
                mappings.append(mapping)
                mapping_index[(question_id, part_id)] = mapping

        analyses = []
        weight_options = {
            name: options[name]
            for name in (
                "performance_weight",
                "concept_weight",
                "cognitive_weight",
            )
            if name in options
        }
        for student in students:
            try:
                analyses.extend(
                    self.answer_agent.run(
                        exam_data,
                        student,
                        model_answers,
                        mapping_index,
                        **weight_options,
                    )
                )
            except Exception as exc:
                analyses.extend(
                    self._failed_answers(
                        exam_data,
                        student,
                        mapping_index,
                        exc,
                    )
                )

        threshold_options = {
            name: options[name]
            for name in (
                "weak_threshold",
                "weak_min_students",
                "weak_min_below_share",
            )
            if name in options
        }
        try:
            cohort = self.cohort_agent.run(
                exam_id,
                exam_data,
                analyses,
                **threshold_options,
            )
        except Exception as exc:
            cohort = CohortPredictionResult(
                exam_id=exam_id,
                status=AgentStatus.FAILED,
                warnings=[
                    AgentWarning(
                        code="cohort_analysis_failed",
                        message=str(exc),
                        capability="cohort_analysis",
                    )
                ],
            )
        statuses = [item.status for item in mappings]
        statuses.extend(item.status for item in analyses)
        statuses.append(cohort.status)
        status = (
            AgentStatus.FAILED
            if AgentStatus.FAILED in statuses
            else (
                AgentStatus.PARTIAL
                if AgentStatus.PARTIAL in statuses
                else AgentStatus.SUCCESS
            )
        )
        context = AgentRunContext(
            run_id=str(uuid4()),
            input_hash=self._input_hash(
                exam_data,
                students,
                model_answers,
                rubric,
            ),
            exam_id=exam_id,
            started_at=datetime.now(timezone.utc),
            model_versions=self.registry.versions(),
        )
        warnings = [
            warning
            for item in mappings
            for warning in item.warnings
        ]
        warnings.extend(
            warning
            for item in analyses
            for warning in item.warnings
        )
        warnings.extend(cohort.warnings)
        return AgentWorkflowResult(
            context=context,
            question_mappings=mappings,
            answer_analyses=analyses,
            cohort_result=cohort,
            status=status,
            warnings=warnings,
        )
