"""Phase 4: Recommendation engine - retrieval + ranking.

Reads question_bank.json (Phase 1) + weakness_scores (Phase 3) +
computes Lecture/Tutorial/Exam/Bloom signals, scores candidates,
returns ranked recommendations for lecturer.

Candidate pool = tutorial + lecture questions (not exams) that are
teachable and optionally not recently examined.
"""
from __future__ import annotations

import json
import pathlib
from collections import Counter
from typing import Any

from app.analytics.recommendation_score import (
    DEFAULT_WEIGHTS,
    ScoreWeights,
    bloom_gap_for_level,
    priority_from_score,
    recommendation_score,
)
from app.services.weakness_scoring import weakness_for_document

QUESTION_BANK_PATH = pathlib.Path(__file__).resolve().parents[2] / "datasets" / "bloom_dataset" / "question_bank.json"

# Target bloom distribution for a balanced exam (tunable per lecturer)
DEFAULT_BLOOM_TARGET: dict[str, float] = {
    "Remember": 0.10,
    "Understand": 0.20,
    "Apply": 0.40,
    "Analyze": 0.25,
    "Evaluate": 0.05,
    "Create": 0.0,
}


def _load_question_bank() -> list[dict[str, Any]]:
    if not QUESTION_BANK_PATH.exists():
        return []
    with open(QUESTION_BANK_PATH, encoding="utf-8") as f:
        return json.load(f)


def _compute_signals(question_bank: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive Lecture Coverage, Tutorial Evidence, Exam Relevance maps.

    Returns:
      lecture_coverage: {canonical_topic: 0|1}
      tutorial_evidence: {canonical_topic: 0..1 normalized count}
      exam_relevance: {canonical_topic: 0..1 = 1 - recent_appear_rate}
      bloom_distribution: {bloom_level: proportion in recent exams}
    """
    lecture_topics = {
        r["canonical_topic"] for r in question_bank if r["source_type"] == "lecture"
    }
    # tutorial counts per topic (include generated as teachable evidence)
    tut_counts: Counter = Counter(
        r["canonical_topic"] for r in question_bank if r["source_type"] in ("tutorial", "generated")
    )
    max_tut = max(tut_counts.values()) if tut_counts else 1

    # exam counts - last 2 years as recent (2023,2024)
    recent_exams = [r for r in question_bank if r["source_type"] == "exam" and r["year"] >= 2023]
    recent_by_topic: Counter = Counter(r["canonical_topic"] for r in recent_exams)
    max_recent = max(recent_by_topic.values()) if recent_by_topic else 1

    # bloom distribution in recent exams (from bank, fallback)
    bloom_counts: Counter = Counter(r["bloom_level"] for r in recent_exams)
    total_recent = len(recent_exams) if recent_exams else 1
    bloom_dist = {k: v / total_recent for k, v in bloom_counts.items()}
    # normalize tutorial evidence with threshold: >=3 practices = full evidence
    tut_ev_thresholded = {}
    for topic, count in tut_counts.items():
        # at least 1 question = 0.6, 3+ = 1.0, scales linearly 1..3
        if count >= 3:
            tut_ev_thresholded[topic] = 1.0
        elif count >= 1:
            tut_ev_thresholded[topic] = 0.6 + 0.4 * (count / 3)
        else:
            tut_ev_thresholded[topic] = 0.0

    return {
        "lecture_coverage": {topic: 1.0 for topic in lecture_topics},
        "tutorial_counts": dict(tut_counts),
        "tutorial_evidence": tut_ev_thresholded,
        "exam_recent_counts": dict(recent_by_topic),
        "exam_relevance": {
            topic: round(1.0 - min(1.0, count / max(2, max_recent)), 4)
            for topic, count in recent_by_topic.items()
        },
        "bloom_distribution": bloom_dist,
        "bloom_distribution_bank": bloom_dist,
        "total_exam_recent": len(recent_exams),
    }


def recommend_questions(
    analytics_document: dict[str, Any],
    question_bank: list[dict[str, Any]] | None = None,
    bloom_target: dict[str, float] | None = None,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
    limit: int = 10,
    exclude_recent_exam_topics: bool = False,
) -> list[dict[str, Any]]:
    """Rank candidate questions for lecturer.

    Args:
      analytics_document: exam analytics doc with topic_performance/question_performance
      question_bank: optional override (loads from disk if None)
      bloom_target: desired bloom distribution, defaults to DEFAULT_BLOOM_TARGET
      limit: top N to return
    """
    if question_bank is None:
        question_bank = _load_question_bank()
    if bloom_target is None:
        bloom_target = DEFAULT_BLOOM_TARGET

    # Phase 3 weakness
    weakness_res = weakness_for_document(analytics_document)
    weakness_scores: dict[str, dict] = weakness_res["weakness_scores"]

    signals = _compute_signals(question_bank)

    # Prefer bloom gap from analytics document's bloom_performance (actual student weakness)
    # if available, else fall back to recent exam bank distribution
    analytics_bloom_gap_cache: dict[str, float] = {}
    bloom_perf = analytics_document.get("bloom_performance") or []
    if bloom_perf:
        # Use weakness per bloom level: gap = weakness (1 - avg_pct/100)
        for entry in bloom_perf:
            lvl = entry.get("level")
            pct = float(entry.get("average_percentage", 0))
            weakness_bloom = 1.0 - pct / 100.0
            analytics_bloom_gap_cache[lvl] = round(max(0.0, weakness_bloom), 4)

    # Candidates: tutorial + generated questions (lecture rows are coverage signals, not exam candidates)
    # Generated fills 0-coverage gaps (JDBC/Indexes/Transaction etc. via qwen3:8b)
    candidates = [r for r in question_bank if r["source_type"] in ("tutorial", "generated")]
    if not candidates:
        candidates = [r for r in question_bank if r["source_type"] == "lecture"]

    ranked: list[dict[str, Any]] = []
    for cand in candidates:
        topic = cand["canonical_topic"]
        w_info = weakness_scores.get(topic, {"weakness": 0.0})
        weakness = float(w_info.get("weakness", 0.0))

        lecture_cov = signals["lecture_coverage"].get(topic, 0.0)
        tut_ev = signals["tutorial_evidence"].get(topic, 0.0)
        # exam relevance: if topic not in recent, relevance = 1.0 (good to assess)
        exam_rel = signals["exam_relevance"].get(topic, 1.0)

        # Use analytics bloom weakness if available (more accurate for student need)
        cand_bloom = cand.get("bloom_level", "Apply")
        if analytics_bloom_gap_cache:
            # If bloom level was measured in analytics, use its weakness; otherwise 0 (no evidence)
            bloom_gap = analytics_bloom_gap_cache.get(cand_bloom, 0.0)
        else:
            bloom_gap = bloom_gap_for_level(
                cand_bloom,
                signals["bloom_distribution"],
                bloom_target,
            )

        score = recommendation_score(
            weakness, lecture_cov, tut_ev, exam_rel, bloom_gap, weights
        )

        ranked.append(
            {
                "question_id": cand["question_id"],
                "source_type": cand["source_type"],
                "source_id": cand["source_id"],
                "canonical_topic": topic,
                "subtopic": cand.get("subtopic", "")[:500],
                "bloom_level": cand.get("bloom_level"),
                "difficulty": cand.get("difficulty"),
                "marks": cand.get("marks", 0),
                "text": cand.get("text", "")[:2000],
                "weakness": weakness,
                "lecture_coverage": lecture_cov,
                "tutorial_evidence": tut_ev,
                "exam_relevance": exam_rel,
                "bloom_gap": bloom_gap,
                "recommendation_score": score,
                "priority": priority_from_score(score),
                "reason": {
                    "weakness_pct": round(weakness * 100, 1),
                    "lecture": bool(lecture_cov),
                    "tutorial_count": signals["tutorial_counts"].get(topic, 0),
                    "exam_recent_count": signals["exam_recent_counts"].get(topic, 0),
                    "bloom_gap": bloom_gap,
                },
            }
        )

    # optionally deprioritize topics heavily examined recently
    if exclude_recent_exam_topics:
        ranked = [r for r in ranked if r["exam_relevance"] > 0.3]

    ranked.sort(key=lambda x: x["recommendation_score"], reverse=True)
    return ranked[:limit]


def recommend_for_weak_areas(
    analytics_document: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """High-level helper: returns weak areas + recommendations.

    Used by lecturer dashboard.
    """
    weakness_res = weakness_for_document(analytics_document)
    recs = recommend_questions(analytics_document, **kwargs)
    return {
        "weakness_scores": weakness_res["weakness_scores"],
        "ranked_weak_topics": weakness_res["ranked_weak_topics"],
        "recommendations": recs,
        "high_priority": [r for r in recs if r["priority"] == "High"],
        "medium_priority": [r for r in recs if r["priority"] == "Medium"],
    }
