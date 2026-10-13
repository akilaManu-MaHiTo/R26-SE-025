"""Student weakness scoring for recommendation engine - Phase 3.

Derives weakness (0..1) from canonical_topic_performance average_percentage.
Weakness = 1 - average_percentage/100, weighted for recommendation scoring.

Used by Phase 4 recommendation engine's Student Weakness component (weight 0.35).
"""
from __future__ import annotations

from typing import Any


def weakness_from_percentage(
    average_percentage: float,
    failure_rate: float | None = None,
    missed_criterion_rate: float | None = None,
) -> float:
    """Convert 0-100 percentage to 0..1 weakness. 50% -> 0.50.

    When ``failure_rate`` and/or ``missed_criterion_rate`` are supplied
    (0..1), a weighted composite is used:

        weakness = 0.6*(1-pct/100) + 0.25*failure_rate + 0.15*missed_criterion_rate

    Otherwise falls back to pure ``1 - pct/100`` for backward compat.
    """
    base = max(0.0, min(1.0, 1.0 - average_percentage / 100.0))
    if failure_rate is None and missed_criterion_rate is None:
        return round(base, 4)
    try:
        fr = float(failure_rate) if failure_rate is not None else 0.0
    except Exception:
        fr = 0.0
    try:
        mcr = float(missed_criterion_rate) if missed_criterion_rate is not None else 0.0
    except Exception:
        mcr = 0.0
    fr = max(0.0, min(1.0, fr))
    mcr = max(0.0, min(1.0, mcr))
    composite = 0.6 * base + 0.25 * fr + 0.15 * mcr
    return round(max(0.0, min(1.0, composite)), 4)


def compute_weakness_scores(
    canonical_topic_performance: list[dict[str, Any]] | None,
    topic_performance: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return {canonical_topic: {weakness, average_percentage, status, priority}}.

    Prefers canonical_topic_performance (Phase 2 normalized, 11 canonicals).
    Falls back to topic_performance (raw noisy labels) if canonical not yet computed,
    merging aliases that map to same canonical_id via app.taxonomy.normalizer.
    """
    if canonical_topic_performance:
        result: dict[str, dict[str, Any]] = {}
        for entry in canonical_topic_performance:
            topic = entry.get("topic") or entry.get("name") or "unknown"
            pct = float(entry.get("average_percentage", 0))
            fr = entry.get("failure_rate")
            mcr = entry.get("missed_criterion_rate")
            weakness = (
                weakness_from_percentage(pct, failure_rate=fr, missed_criterion_rate=mcr)
                if fr is not None or mcr is not None
                else weakness_from_percentage(pct)
            )
            result[topic] = {
                "average_percentage": pct,
                "weakness": weakness,
                "status": entry.get("status", "Unknown"),
                "priority": entry.get("priority", entry.get("status", "Unknown")),
                "question_count": entry.get("question_count", 0),
            }
        return result

    # Raw fallback: merge aliases into canonical buckets
    source = topic_performance or []
    if not source:
        return {}
    try:
        from app.taxonomy.normalizer import normalize_topic, get_canonical_topic

        # bucket: canonical_id -> list of percentages
        buckets: dict[str, list[float]] = {}
        # also keep original fragments for status derivation
        status_by_bucket: dict[str, list[str]] = {}
        for entry in source:
            raw = entry.get("topic") or entry.get("name") or ""
            pct = float(entry.get("average_percentage", 0))
            cid = normalize_topic(raw) or raw
            buckets.setdefault(cid, []).append(pct)
            status_by_bucket.setdefault(cid, []).append(entry.get("status", ""))
        result = {}
        for cid, pcts in buckets.items():
            avg_pct = round(sum(pcts) / len(pcts), 2) if pcts else 0
            topic_name = get_canonical_topic(cid) or cid
            # derive status from avg_pct via same thresholds
            from app.analytics.student_document import performance_status

            status = performance_status(avg_pct)
            # try to aggregate failure/missed rates if present in source entries for this bucket
            fr_vals = []
            mcr_vals = []
            for entry in source:
                raw = entry.get("topic") or entry.get("name") or ""
                if (normalize_topic(raw) or raw) == cid:
                    if entry.get("failure_rate") is not None:
                        try:
                            fr_vals.append(float(entry["failure_rate"]))
                        except Exception:
                            pass
                    if entry.get("missed_criterion_rate") is not None:
                        try:
                            mcr_vals.append(float(entry["missed_criterion_rate"]))
                        except Exception:
                            pass
            fr_avg = round(sum(fr_vals) / len(fr_vals), 4) if fr_vals else None
            mcr_avg = round(sum(mcr_vals) / len(mcr_vals), 4) if mcr_vals else None
            weakness = (
                weakness_from_percentage(avg_pct, failure_rate=fr_avg, missed_criterion_rate=mcr_avg)
                if fr_avg is not None or mcr_avg is not None
                else weakness_from_percentage(avg_pct)
            )
            result[topic_name] = {
                "average_percentage": avg_pct,
                "weakness": weakness,
                "status": status,
                "priority": status,
                "question_count": 0,
                "merged_fragments": len(pcts),
            }
        return result
    except Exception:
        # fallback without normalizer
        result = {}
        for entry in source:
            topic = entry.get("topic") or entry.get("name") or "unknown"
            pct = float(entry.get("average_percentage", 0))
            fr = entry.get("failure_rate")
            mcr = entry.get("missed_criterion_rate")
            weakness = (
                weakness_from_percentage(pct, failure_rate=fr, missed_criterion_rate=mcr)
                if fr is not None or mcr is not None
                else weakness_from_percentage(pct)
            )
            result[topic] = {
                "average_percentage": pct,
                "weakness": weakness,
                "status": entry.get("status", "Unknown"),
                "priority": entry.get("priority", entry.get("status", "Unknown")),
                "question_count": entry.get("question_count", 0),
            }
        return result


def subtopic_weakness_from_question_performance(
    question_performance: list[dict[str, Any]],
) -> dict[str, float]:
    """Estimate subtopic-level weakness from question_performance.

    When question topics map to subtopics (via taxonomy lookup), this gives
    finer granularity than topic-level. For now, groups by (topic, bloom).
    """
    # Weakness per question_id as proxy for subtopic weakness
    return {
        q.get("question_id", f"Q{q.get('question_no','?')}"): weakness_from_percentage(
            float(q.get("average_percentage", 0))
        )
        for q in (question_performance or [])
    }


def rank_weak_topics(
    weakness_scores: dict[str, dict[str, Any]], limit: int | None = None
) -> list[tuple[str, float]]:
    """Return topics sorted by descending weakness (weakest first)."""
    ranked = sorted(
        weakness_scores.items(),
        key=lambda kv: kv[1]["weakness"],
        reverse=True,
    )
    pairs = [(topic, info["weakness"]) for topic, info in ranked]
    return pairs[:limit] if limit else pairs
