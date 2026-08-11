"""Batch materialization of canonical student analytics documents."""

from dataclasses import dataclass, field

from pydantic import TypeAdapter, ValidationError

from app.analytics.student_document import NumericStudentAnalysis, build_numeric_analysis
from app.classifier.rules import classify_by_rules
from app.config import settings
from app.db.repository import (
    find_course_for_submission,
    find_graded_submissions,
    find_rubric_for_submission,
    upsert_student_analytics,
)
from app.ingestion.student_data import NormalizedStudentInput, normalize_student_submission
from app.llm.ollama import OllamaUnavailable
from app.llm.roles.student_analysis import QuestionSemantics, StudentInsightResponse
from app.schemas.student import StudentAnalyticsDocument
from app.services.llm_service import (
    classify_question_semantics,
    generate_student_insights,
)


@dataclass(frozen=True)
class MaterializationFailure:
    student_id: str
    reason: str


@dataclass
class MaterializationResult:
    saved: list[str] = field(default_factory=list)
    failures: list[MaterializationFailure] = field(default_factory=list)


_RULE_CONFIDENCE = {"high": 0.85, "medium": 0.65, "low": 0.4}


def _rule_semantics(question_text: str, degraded_reason: str) -> QuestionSemantics:
    rules = classify_by_rules(question_text)
    dominant_topic = (
        max(rules.topic_assignments, key=lambda assignment: assignment.weight).topic
        if rules.topic_assignments
        else "General"
    )
    subtopic = next(
        (str(concept).strip() for concept in rules.key_concepts if str(concept).strip()),
        dominant_topic,
    )
    confidence = _RULE_CONFIDENCE.get(rules.confidence, 0.4)
    return QuestionSemantics(
        level=rules.bloom_level,
        topic=dominant_topic,
        subtopic=subtopic,
        confidence=confidence,
        reason=f"rule-based fallback ({degraded_reason})",
    )


async def _classify_questions(
    normalized: NormalizedStudentInput,
    cache: dict[tuple[str, str], QuestionSemantics],
) -> dict[str, QuestionSemantics]:
    semantics_by_question: dict[str, QuestionSemantics] = {}
    course = {"code": normalized.course_code, "name": normalized.course_name}

    for question in sorted(normalized.questions, key=lambda item: item.question_no):
        cache_key = (normalized.rubric_ref, question.question_no)
        semantics = cache.get(cache_key)
        if semantics is None:
            try:
                response = await classify_question_semantics(
                    course,
                    question.question_text,
                    [criterion.criterion for criterion in question.criteria],
                )
            except OllamaUnavailable:
                response = {"status": "degraded", "reason": "ollama_unavailable"}

            if response.get("status") == "ok":
                try:
                    semantics = QuestionSemantics.model_validate(response.get("semantics"))
                except ValidationError:
                    semantics = _rule_semantics(question.question_text, "schema_failure")
            else:
                semantics = _rule_semantics(
                    question.question_text,
                    str(response.get("reason") or "model_degraded"),
                )
            cache[cache_key] = semantics
        semantics_by_question[question.question_no] = semantics

    return semantics_by_question


def _validated_insights(insights: dict) -> StudentInsightResponse | None:
    if insights.get("status") != "ok":
        return None

    target = insights.get("generation_target")
    if not isinstance(target, dict):
        return None
    whitelisted = {
        "learning_gaps": insights.get("learning_gaps"),
        "recommendations": insights.get("recommendations"),
        "generation_target": {
            "recommended_bloom_level": target.get("recommended_bloom_level"),
            "recommended_difficulty": target.get("recommended_difficulty"),
            "recommended_topics": target.get("recommended_topics"),
        },
    }
    try:
        return StudentInsightResponse.model_validate(whitelisted)
    except ValidationError:
        return None


def _assemble_document(
    normalized: NormalizedStudentInput,
    numeric: NumericStudentAnalysis,
    insights: dict,
    submission: dict,
) -> dict:
    document = numeric.model_dump(mode="json")
    validated_insights = _validated_insights(insights)
    if validated_insights is not None:
        document["learning_analysis"]["learning_gaps"] = list(
            validated_insights.learning_gaps
        )
        document["recommendations"] = [
            recommendation.model_dump(mode="json")
            for recommendation in validated_insights.recommendations
        ]
        target = validated_insights.generation_target
        document["next_question_generation"] = {
            "recommended_bloom_level": target.recommended_bloom_level,
            "recommended_difficulty": target.recommended_difficulty,
            "recommended_topics": list(target.recommended_topics),
            "number_of_questions": 5,
        }
    else:
        document["next_question_generation"]["number_of_questions"] = 5

    evaluation_metadata = submission.get("evaluation")
    if not isinstance(evaluation_metadata, dict):
        raise ValueError("missing submission evaluation metadata")
    grading_source = str(evaluation_metadata.get("grading_source") or "").strip()
    if not grading_source:
        raise ValueError("missing evaluation grading_source")
    if "rag_context_used" not in evaluation_metadata:
        raise ValueError("missing evaluation rag_context_used")
    try:
        rag_context_used = TypeAdapter(bool).validate_python(
            evaluation_metadata["rag_context_used"]
        )
    except ValidationError as exc:
        raise ValueError("invalid evaluation rag_context_used") from exc

    document.update(
        student_id=normalized.student_id,
        course={"code": normalized.course_code, "name": normalized.course_name},
        model_metadata={
            "bloom_model": settings.ollama_model,
            "bloom_model_type": settings.ollama_model_type,
            "grading_source": grading_source,
            "rag_context_used": rag_context_used,
        },
    )
    return document


async def materialize_student_analytics(
    db, submissions: list[dict] | None = None
) -> MaterializationResult:
    """Build and persist each graded submission without aborting the batch."""
    source_submissions = (
        await find_graded_submissions(db) if submissions is None else submissions
    )
    classification_cache: dict[tuple[str, str], QuestionSemantics] = {}
    saved: list[str] = []
    failures: list[MaterializationFailure] = []

    for submission in source_submissions:
        try:
            course = await find_course_for_submission(db, submission)
            rubric = await find_rubric_for_submission(db, submission)
            normalized = normalize_student_submission(
                course or {}, rubric or {}, submission
            )
            semantics = await _classify_questions(normalized, classification_cache)
            numeric = build_numeric_analysis(normalized, semantics)
            try:
                insights = await generate_student_insights(
                    normalized.student_id, numeric.evidence()
                )
            except OllamaUnavailable:
                insights = {
                    "status": "degraded",
                    "reason": "ollama_unavailable",
                }
            document = _assemble_document(normalized, numeric, insights, submission)
            validated = StudentAnalyticsDocument.model_validate(document)
            await upsert_student_analytics(db, validated.model_dump(mode="json"))
            saved.append(normalized.student_id)
        except Exception as exc:
            student_id = str(
                submission.get("student_id")
                or submission.get("student_key")
                or "unknown"
            )
            failures.append(
                MaterializationFailure(student_id=student_id, reason=str(exc))
            )

    return MaterializationResult(saved=saved, failures=failures)
