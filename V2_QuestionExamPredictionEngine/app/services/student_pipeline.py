"""Batch materialization of canonical student analytics documents."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from pydantic import TypeAdapter, ValidationError

from app.analytics.student_document import (
    NumericStudentAnalysis,
    _PRIORITY_BY_STATUS,
    build_numeric_analysis,
)
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
from app.services.llm_service import generate_student_insights


@dataclass(frozen=True)
class MaterializationFailure:
    student_id: str
    reason: str


StepCallback = Callable[[str], None]


@dataclass
class MaterializationResult:
    saved: list[str] = field(default_factory=list)
    failures: list[MaterializationFailure] = field(default_factory=list)


def _try_bloom_semantics(question_text: str) -> QuestionSemantics:
    """Bloom ModernBERT ONLY: mandatory ModernBERT prediction for Bloom level, topic from rules (without double bloom inference)."""
    from app.classifier.bloom_classifier import is_bloom_model_available, predict_bloom

    if not is_bloom_model_available():
        raise RuntimeError(
            f"Bloom ModernBERT not available at {settings.bloom_model_dir} — "
            "ensure models/bloom_modernbert/bloom.safetensors + tokenizer exist"
        )
    bloom = predict_bloom(question_text)
    # Topic from rules WITHOUT triggering second bloom inference: compute hits directly
    from app.analytics.taxonomy import TOPICS
    from app.classifier.rules import TOPIC_KEYWORDS
    import re

    lower = question_text.lower()
    hits: dict[str, int] = {}
    for topic in TOPICS:
        kws = TOPIC_KEYWORDS.get(topic)
        if kws is None:
            norm = topic.replace("&", "and")
            kws = TOPIC_KEYWORDS.get(norm)
        if kws is None and "SQL" in topic:
            kws = TOPIC_KEYWORDS.get("SQL")
        if not kws:
            continue
        count = 0
        for kw in kws:
            count += len(re.findall(re.escape(kw), lower))
        if count > 0:
            hits[topic] = count
    if not hits:
        dominant_topic = TOPICS[0] if TOPICS else "General"
        subtopic = dominant_topic
    else:
        dominant_topic = max(hits, key=lambda t: hits[t])
        subtopic = dominant_topic
    return QuestionSemantics(
        level=bloom["level"],
        topic=dominant_topic,
        subtopic=subtopic,
        confidence=float(bloom["confidence"]),
        reason=f"modernbert {bloom['label']} {bloom['confidence']:.3f}",
    )


def _rule_semantics(question_text: str, degraded_reason: str) -> QuestionSemantics:
    """Deprecated fallback — now also uses ModernBERT only (no rule bloom)."""
    # degraded_reason kept for signature compatibility but ignored for Bloom level
    return _try_bloom_semantics(question_text)


async def _classify_questions(
    normalized: NormalizedStudentInput,
    cache: dict[tuple[str, str], QuestionSemantics],
    progress: StepCallback | None = None,
) -> dict[str, QuestionSemantics]:
    """Classify questions using ONLY bloom_modernbert for Bloom level (topic from rules)."""
    semantics_by_question: dict[str, QuestionSemantics] = {}

    # Collect uncached questions — BloomModernBERT is the ONLY method for Bloom
    uncached: list = []
    for question in sorted(normalized.questions, key=lambda item: item.question_no):
        cache_key = (normalized.rubric_ref, question.question_no)
        semantics = cache.get(cache_key)
        if semantics is not None:
            semantics_by_question[question.question_no] = semantics
            if progress is not None:
                progress(f"classify q{question.question_no} (cached)")
        else:
            uncached.append(question)

    if not uncached:
        return semantics_by_question

    for q in uncached:
        # Mandatory ModernBERT — no LLM, no rule fallback for Bloom
        semantics = _try_bloom_semantics(q.question_text)
        if progress is not None:
            progress(f"classify q{q.question_no} (bloom_model)")
        cache[(normalized.rubric_ref, q.question_no)] = semantics
        semantics_by_question[q.question_no] = semantics

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


def _gap_from_insight_text(text: str, learning_analysis: dict) -> dict:
    candidates = (
        learning_analysis.get("critical_topics", [])
        + learning_analysis.get("weak_topics", [])
        + learning_analysis.get("developing_topics", [])
    )
    topic = next((name for name in candidates if name), "General")
    priority = _PRIORITY_BY_STATUS.get(
        learning_analysis.get("overall_performance"), "Medium"
    )
    return {"topic": topic, "subtopic": text, "priority": priority}


def _bloom_levels_with_target(target: str, strategy: dict) -> list[str]:
    levels = strategy.get("recommended_bloom_levels") or []
    return [target] + [level for level in levels if level != target]


def _assemble_document(
    normalized: NormalizedStudentInput,
    numeric: NumericStudentAnalysis,
    insights: dict,
    submission: dict,
) -> dict:
    document = numeric.model_dump(mode="json")
    validated_insights = _validated_insights(insights)
    if validated_insights is not None:
        document["learning_analysis"]["learning_gaps"] = [
            _gap_from_insight_text(text, document["learning_analysis"])
            for text in validated_insights.learning_gaps
        ]
        document["recommendations"] = [
            recommendation.model_dump(mode="json")
            for recommendation in validated_insights.recommendations
        ]
        target = validated_insights.generation_target
        document["next_question_strategy"]["recommended_bloom_levels"] = (
            _bloom_levels_with_target(
                target.recommended_bloom_level,
                document["next_question_strategy"],
            )
        )
        document["next_question_strategy"]["recommended_difficulty"] = (
            target.recommended_difficulty
        )
        document["next_question_strategy"]["recommended_topics"] = list(
            target.recommended_topics
        )
    document["next_question_strategy"]["number_of_questions"] = 5

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
        subject_code=normalized.course_code,
        subject_name=normalized.subject_name,
        year=normalized.year,
        month=normalized.month,
        semester=normalized.semester,
        session_name=normalized.session_name,
        model_metadata={
            "bloom_model": settings.llm_model,
            "bloom_model_type": settings.ollama_model_type,
            "grading_source": grading_source,
            "rag_context_used": rag_context_used,
        },
        generated_at=datetime.now(timezone.utc).isoformat(),
        analysis_version="1.0",
    )
    return document


async def _build_student_analytics(
    db,
    submission: dict,
    classification_cache: dict[tuple[str, str], QuestionSemantics],
    progress: StepCallback | None = None,
) -> StudentAnalyticsDocument:
    course = await find_course_for_submission(db, submission)
    rubric = await find_rubric_for_submission(db, submission)
    normalized = normalize_student_submission(
        course or {}, rubric or {}, submission
    )
    semantics = await _classify_questions(
        normalized, classification_cache, progress=progress
    )
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
    if progress is not None:
        progress(f"insights {normalized.student_id}")
    document = _assemble_document(normalized, numeric, insights, submission)
    return StudentAnalyticsDocument.model_validate(document)


async def build_student_analytics(
    db, submission: dict, progress_callback=None
) -> StudentAnalyticsDocument:
    """Build and persist-ready analytics for a single graded submission."""
    return await _build_student_analytics(db, submission, {}, progress=progress_callback)


async def materialize_student_analytics(
    db,
    submissions: list[dict] | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> MaterializationResult:
    """Build and persist each graded submission without aborting the batch.

    When ``progress_callback`` is provided it is invoked after each slow step
    (per-question classification and per-student insight generation) with
    ``(steps_done, total_steps, description)``.
    """
    source_submissions = (
        await find_graded_submissions(db) if submissions is None else submissions
    )
    classification_cache: dict[tuple[str, str], QuestionSemantics] = {}
    saved: list[str] = []
    failures: list[MaterializationFailure] = []

    def _submission_step_count(submission: dict) -> int:
        results = submission.get("evaluation", {}).get("results", [])
        return len(results) + 1

    total_steps = (
        sum(_submission_step_count(submission) for submission in source_submissions)
        if progress_callback is not None
        else 0
    )
    steps_done = 0

    def _report(phase: str) -> None:
        nonlocal steps_done
        if progress_callback is None:
            return
        steps_done += 1
        progress_callback(steps_done, total_steps, phase)

    for submission in source_submissions:
        try:
            document = await _build_student_analytics(
                db, submission, classification_cache, progress=_report
            )
            await upsert_student_analytics(
                db, document.model_dump(mode="json")
            )
            saved.append(document.student_id)
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
