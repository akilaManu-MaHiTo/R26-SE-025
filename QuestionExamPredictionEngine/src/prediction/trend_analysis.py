"""Trend analysis helpers for future grading workflow work.

This module provides a small set of utilities to compute per-year and
per-topic/question aggregates and a simple linear trend estimate across
years. The goal is to be dependency-free and produce JSON-serializable
summaries usable by downstream reporting code.
"""
from collections import defaultdict
from typing import List, Dict, Any


def _mean(nums):
    return sum(nums) / len(nums) if nums else 0.0


def _linear_slope(xs, ys):
    # simple least-squares slope; xs and ys are lists of numbers and len>=2
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return num / den


def analyze_trends(reports: List[Dict[str, Any]], by: str = "topic", time_key: str = "year") -> Dict[str, Any]:
    """Analyze trends across `reports`.

    Parameters:
    - reports: list of report dicts (expected keys include `year`, `learning_score` and grouping key such as `topic` or `question`)
    - by: grouping field to analyze trends for (default: `topic`)
    - time_key: the field to use for time (default: `year`)

    Returns a dict mapping group -> summary with per-year averages, counts,
    simple linear slope across years, earliest/latest values and change.
    """
    # organize data: group -> year -> list(scores)
    data = defaultdict(lambda: defaultdict(list))

    for r in reports:
        group = r.get(by) or r.get("topic") or r.get("question")
        year = r.get(time_key)
        try:
            year = int(year)
        except Exception:
            # fallback: try parsing as string, keep as-is for grouping
            pass
        score = r.get("learning_score")
        try:
            score = float(score)
        except Exception:
            continue
        data[group][year].append(score)

    result = {}
    for group, years_map in data.items():
        years = sorted(years_map.keys())
        yearly_summary = {}
        xs = []
        ys = []
        for y in years:
            vals = years_map[y]
            avg = round(_mean(vals), 4)
            yearly_summary[str(y)] = {"avg_learning_score": avg, "count": len(vals)}
            # for slope calculation require numeric x
            try:
                xs.append(int(y))
                ys.append(avg)
            except Exception:
                # skip non-numeric time keys for slope calc
                pass

        slope = _linear_slope(xs, ys) if len(xs) >= 2 else 0.0
        earliest = yearly_summary[str(years[0])] if years else {"avg_learning_score": 0}
        latest = yearly_summary[str(years[-1])] if years else {"avg_learning_score": 0}

        result[group] = {
            "years": yearly_summary,
            "slope": round(float(slope), 6),
            "earliest_year": str(years[0]) if years else None,
            "latest_year": str(years[-1]) if years else None,
            "earliest_avg": earliest.get("avg_learning_score"),
            "latest_avg": latest.get("avg_learning_score"),
            "change": round(latest.get("avg_learning_score", 0) - earliest.get("avg_learning_score", 0), 4),
        }

    return result


__all__ = ["analyze_trends"]