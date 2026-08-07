import logging
from datetime import datetime, timezone

from app.analytics.coverage import detect_gaps
from app.analytics.evidence import apply_evidence_statuses, cohort_summary
from app.analytics.mastery import compute_topic_bloom_matrix, compute_topic_metrics
from app.analytics.recommender import rank_recommendations
from app.config import settings
from app.db.repository import (
    insert_attempts,
    save_recommendations,
    save_run,
    save_snapshot,
    upsert_catalog,
)
from app.ingestion.transformer import ingest
from app.schemas.derived import AnalysisRun, AnalyticsSnapshot, ExamRecommendation
from app.services.llm_service import classify_question, is_embedding_available

logger = logging.getLogger(__name__)


async def run_analytics(
    db,
    run_id: str,
    course: dict,
    papers: list[dict],
    submissions: list[dict],
) -> AnalysisRun:
    course_settings = course.get("settings", {})
    pass_threshold = course_settings.get("pass_threshold", settings.pass_threshold)
    min_students = course_settings.get("min_students", settings.min_students)
    min_attempts = course_settings.get("min_attempts", settings.min_attempts)
    topic_importance = course_settings.get("topic_importance", {})
    blueprint_targets = course_settings.get("blueprint_targets", {})

    algorithm_version = settings.algorithm_version
    await save_run(
        db,
        {
            "run_id": run_id,
            "course_code": course["course_code"],
            "exam_id": course.get("exam_id", ""),
            "status": "running",
            "algorithm_version": algorithm_version,
            "thresholds": {
                "pass_threshold": pass_threshold,
                "min_students": min_students,
                "min_attempts": min_attempts,
            },
            "created_at": datetime.now(timezone.utc),
        },
    )

    catalog_records, attempt_records = ingest(
        [course], papers, submissions, run_id, algorithm_version
    )
    for c in catalog_records:
        try:
            c["model_output"] = classify_question(c["question_text"])
        except Exception:
            c["model_output"] = {"status": "rules_degraded", "reason": "classification_error"}
    if is_embedding_available():
        try:
            from app.embeddings.embedder import Embedder

            embedder = Embedder()
            vectors = embedder.embed_batch([c["question_text"] for c in catalog_records])
            for c, _vec in zip(catalog_records, vectors):
                c["embedding_ref"] = f"emb:{c['question_id']}"
        except Exception:
            logger.exception("embedding enrichment failed; continuing without embeddings")
    for c in catalog_records:
        await upsert_catalog(db, c)
    await insert_attempts(db, attempt_records)

    attempts = attempt_records
    course_code = course["course_code"]
    exam_ids = sorted({a["exam_id"] for a in attempts})
    exam_id = exam_ids[0] if exam_ids else ""

    matrix = compute_topic_bloom_matrix(attempts)
    apply_evidence_statuses(matrix, pass_threshold, min_students, min_attempts)
    topic_metrics = [compute_topic_metrics(attempts, m.topic) for m in matrix]
    apply_evidence_statuses(topic_metrics, pass_threshold, min_students, min_attempts)

    summary = cohort_summary(attempts)

    gaps = detect_gaps(attempts, targets=blueprint_targets)

    topic_gaps = {}
    for topic in gaps["coverage_gaps"]:
        topic_gaps[topic] = 1.0
    bloom_gaps = {}
    for bloom in gaps["bloom_gaps"]:
        bloom_gaps[bloom] = 1.0

    ranked = rank_recommendations(
        matrix,
        topic_gaps=topic_gaps,
        bloom_gaps=bloom_gaps,
        topic_importance=topic_importance,
    )

    snapshot = AnalyticsSnapshot(
        snapshot_id=f"{run_id}-snapshot",
        run_id=run_id,
        course_code=course_code,
        exam_id=exam_id,
        algorithm_version=algorithm_version,
        cohort_metrics=summary,
        topic_metrics=topic_metrics,
        topic_bloom_matrix=matrix,
        evidence_statuses={m.topic: m.evidence_status for m in topic_metrics},
        grade_distribution=summary["grade_distribution"],
        record_counts={"catalog": len(catalog_records), "attempts": len(attempt_records)},
        pass_threshold=pass_threshold,
        min_students=min_students,
        min_attempts=min_attempts,
    )
    await save_snapshot(db, snapshot.model_dump(mode="json"))

    recommendations = []
    for cell, breakdown, priority in ranked[:10]:
        recommendations.append(
            ExamRecommendation(
                recommendation_id=f"{run_id}-{cell.topic.replace(' ', '_')}-{cell.bloom_level}",
                run_id=run_id,
                course_code=course_code,
                exam_id=exam_id,
                topic=cell.topic,
                bloom_level=cell.bloom_level,
                question_type="problem_solving",
                mark_range=(1.0, 4.0),
                priority_score=round(priority, 4),
                component_breakdown=breakdown,
                evidence={
                    "mastery": cell.mastery,
                    "failure_rate": cell.failure_rate,
                    "student_count": cell.student_count,
                    "attempt_count": cell.attempt_count,
                    "missed_criterion_rate": cell.missed_criterion_rate,
                    "evidence_status": cell.evidence_status,
                },
            )
        )
    await save_recommendations(db, [r.model_dump(mode="json") for r in recommendations])

    run = AnalysisRun(
        run_id=run_id,
        course_code=course_code,
        exam_id=exam_id,
        status="ready",
        data_counts=snapshot.record_counts,
        algorithm_version=algorithm_version,
        thresholds={
            "pass_threshold": pass_threshold,
            "min_students": min_students,
            "min_attempts": min_attempts,
        },
        completed_at=datetime.now(timezone.utc),
    )
    await save_run(db, run.model_dump(mode="json"))
    return run