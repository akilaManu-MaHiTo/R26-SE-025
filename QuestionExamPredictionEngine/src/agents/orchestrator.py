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
    AgentWorkflowResult,
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
                mapping = self.question_agent.run(
                    exam_id,
                    exam_data,
                    question,
                    part,
                    criteria,
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
            analyses.extend(
                self.answer_agent.run(
                    exam_data,
                    student,
                    model_answers,
                    mapping_index,
                    **weight_options,
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
        cohort = self.cohort_agent.run(
            exam_id,
            exam_data,
            analyses,
            **threshold_options,
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
