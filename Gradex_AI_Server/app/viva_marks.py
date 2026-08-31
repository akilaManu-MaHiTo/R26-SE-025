"""Viva mark persistence helpers — isolated from other Gradex_AI_Server routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId

from VivaEvaluationEngine.services.assessment_scoring import (
    MODE_WITHOUT,
    MODE_WITH,
    STATUS_INCOMPLETE,
    STATUS_VALID,
    build_assessment,
)


def assessment_is_publishable(assessment: Any) -> bool:
    if not isinstance(assessment, dict):
        return False
    if assessment.get("status") == STATUS_INCOMPLETE:
        return False
    ai_score = (assessment.get("ai_performance") or {}).get("score")
    return ai_score is not None


def build_publish_update(
    engine_result: dict[str, Any],
    *,
    mode: str,
    technical_accuracy: Optional[float],
    student_id: Optional[str],
    published: bool = True,
    human_published: bool = True,
) -> dict[str, Any]:
    assessment = build_assessment(
        engine_result,
        mode=mode,
        technical_accuracy=technical_accuracy,
    )
    published_at = datetime.now(timezone.utc)
    return {
        "published": bool(published),
        "human_published": bool(human_published),
        "published_at": published_at,
        "student_id": student_id,
        "assessment_mode": mode,
        "features": assessment.get("training_features"),
        "feature_schema_version": assessment.get("feature_schema_version"),
        "scoring_version": assessment.get("scoring_version"),
        "ai_performance_score": (assessment.get("ai_performance") or {}).get("score"),
        "technical_accuracy": assessment.get("technical_accuracy"),
        "final_score": assessment.get("final_score"),
        "final_grade": assessment.get("grade"),
        "assessment": assessment,
    }


def publish_response_payload(
    mark_id: str,
    update: dict[str, Any],
    assessment: dict[str, Any],
) -> dict[str, Any]:
    published_at = update.get("published_at")
    return {
        "mark_id": mark_id,
        "published": update.get("published"),
        "published_at": published_at.isoformat() if hasattr(published_at, "isoformat") else published_at,
        "student_id": update.get("student_id"),
        "assessment_mode": update.get("assessment_mode"),
        "ai_performance_score": update.get("ai_performance_score"),
        "technical_accuracy": update.get("technical_accuracy"),
        "final_score": update.get("final_score"),
        "final_grade": update.get("final_grade"),
        "status": assessment.get("status"),
        "scoring_version": update.get("scoring_version"),
        "feature_schema_version": update.get("feature_schema_version"),
    }


async def apply_publish_to_mark(
    marks_col,
    object_id: ObjectId,
    *,
    mode: str,
    technical_accuracy: Optional[float],
    student_id: Optional[str],
    human_published: bool = True,
) -> dict[str, Any]:
    existing = await marks_col.find_one({"_id": object_id})
    if not existing:
        raise LookupError("Mark not found.")

    engine_result = existing.get("result") or {}
    if mode == MODE_WITH and technical_accuracy is None:
        raise ValueError("technical_accuracy is required for WITH_TECHNICAL_ACCURACY.")

    technical = None if mode == MODE_WITHOUT else technical_accuracy
    update = build_publish_update(
        engine_result,
        mode=mode,
        technical_accuracy=technical,
        student_id=student_id,
        human_published=human_published,
    )
    result = await marks_col.update_one({"_id": object_id}, {"$set": update})
    if result.matched_count == 0:
        raise LookupError("Mark not found.")

    assessment = update["assessment"]
    return publish_response_payload(str(object_id), update, assessment)


async def auto_publish_without_technical(
    marks_col,
    object_id: ObjectId,
    engine_result: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Publish immediately after analyze for presentation-only vivas."""
    assessment = engine_result.get("assessment") or {}
    if not assessment_is_publishable(assessment):
        return None

    payload = await apply_publish_to_mark(
        marks_col,
        object_id,
        mode=MODE_WITHOUT,
        technical_accuracy=None,
        student_id=None,
        human_published=False,
    )
    payload["auto_published"] = True
    return payload


def merge_auto_publish_into_analyze_result(
    analyze_result: dict[str, Any],
    publish_payload: dict[str, Any],
) -> None:
    """Mutates analyze response with published final mark fields."""
    analyze_result["published"] = True
    analyze_result["auto_published"] = True
    analyze_result["assessment_mode"] = publish_payload.get("assessment_mode")
    analyze_result["final_score"] = publish_payload.get("final_score")
    analyze_result["final_grade"] = publish_payload.get("final_grade")
    assessment = analyze_result.get("assessment")
    if isinstance(assessment, dict):
        assessment = dict(assessment)
        assessment["final_score"] = publish_payload.get("final_score")
        assessment["grade"] = publish_payload.get("final_grade")
        assessment["status"] = publish_payload.get("status") or STATUS_VALID
        analyze_result["assessment"] = assessment
