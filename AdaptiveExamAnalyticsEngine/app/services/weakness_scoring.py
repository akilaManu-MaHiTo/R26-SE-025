"""Weakness summaries from an existing analytics document."""
from __future__ import annotations

from typing import Any

from app.analytics.weakness import (
    compute_weakness_scores,
    rank_weak_topics,
    subtopic_weakness_from_question_performance,
)


def weakness_for_document(document: dict[str, Any]) -> dict[str, Any]:
    """Pure helper: compute weakness directly from an in-memory analytics document.

    Used for testing with the sample JSON from your prompt without DB.
    """
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
