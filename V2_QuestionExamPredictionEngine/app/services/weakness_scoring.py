"""Service layer for student weakness - Phase 3.

Provides async helpers to fetch exam analytics and compute weakness
scores for the recommendation engine (Phase 4).

Wraps app.analytics.weakness pure functions with DB access.
"""
from __future__ import annotations

from typing import Any

from app.analytics.weakness import (
    compute_weakness_scores,
    rank_weak_topics,
    subtopic_weakness_from_question_performance,
)
from app.db.repository import find_exam_analytics


async def get_weakness_for_exam(
    db,
    course_code: str,
    session_name: str,
    year: int | None = None,
    month: int | None = None,
    semester: int | None = None,
) -> dict[str, Any]:
    """Fetch stored exam analytics and return weakness analysis.

    Returns:
      {
        "weakness_scores": {canonical_topic: {weakness, average_percentage, status}},
        "ranked_weak_topics": [(topic, weakness), ...],
        "subtopic_weakness": {question_id: weakness},
        "source": "canonical" | "raw",
      }
    """
    doc = await find_exam_analytics(db, course_code, session_name, year, month, semester)
    if not doc:
        return {"weakness_scores": {}, "ranked_weak_topics": [], "subtopic_weakness": {}, "source": "none"}

    canonical = doc.get("canonical_topic_performance")
    raw = doc.get("topic_performance")
    # prefer canonical if available
    if canonical:
        scores = compute_weakness_scores(canonical, None)
        source = "canonical"
    else:
        scores = compute_weakness_scores(None, raw)
        source = "raw"

    ranked = rank_weak_topics(scores)
    subtopic = subtopic_weakness_from_question_performance(doc.get("question_performance", []))

    return {
        "weakness_scores": scores,
        "ranked_weak_topics": ranked,
        "subtopic_weakness": subtopic,
        "source": source,
        "exam_id": f"{course_code}@{session_name}",
        "year": doc.get("year"),
    }


def weakness_for_document(document: dict[str, Any]) -> dict[str, Any]:
    """Pure helper: compute weakness directly from an in-memory analytics document.

    Used for testing with the sample JSON from your prompt without DB.
    """
    canonical = document.get("canonical_topic_performance") or document.get("topic_performance")
    # also handle your sample which has topic_performance with double-wrapped topic names
    scores = compute_weakness_scores(
        document.get("canonical_topic_performance"),
        document.get("topic_performance"),
    )
    return {
        "weakness_scores": scores,
        "ranked_weak_topics": rank_weak_topics(scores),
        "subtopic_weakness": subtopic_weakness_from_question_performance(
            document.get("question_performance", [])
        ),
    }
