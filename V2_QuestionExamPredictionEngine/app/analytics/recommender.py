from app.analytics.taxonomy import DEFAULT_PRIORITY_WEIGHTS
from app.schemas.derived import CellMetrics


def weakness_component(
    mastery: float | None,
    failure_rate: float | None,
    missed_criterion_rate: float | None,
) -> float:
    low_mastery = 0.0 if mastery is None else (1.0 - mastery)
    fail = 0.0 if failure_rate is None else failure_rate
    missed = 0.0 if missed_criterion_rate is None else missed_criterion_rate
    return max(0.0, min(1.0, 0.5 * low_mastery + 0.3 * fail + 0.2 * missed))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def compute_priority(
    weakness: float,
    coverage_gap: float | None,
    bloom_gap: float | None,
    topic_importance: float,
    weights: dict[str, float] | None = None,
) -> float:
    weights = weights or DEFAULT_PRIORITY_WEIGHTS
    cg = 0.0 if coverage_gap is None else coverage_gap
    bg = 0.0 if bloom_gap is None else bloom_gap
    return _clamp01(
        weights["weakness"] * weakness
        + weights["coverage_gap"] * cg
        + weights["bloom_gap"] * bg
        + weights["topic_importance"] * topic_importance
    )


def rank_recommendations(
    cells: list[CellMetrics],
    topic_gaps: dict[str, float] | None = None,
    bloom_gaps: dict[str, float] | None = None,
    topic_importance: dict[str, float] | None = None,
    weights: dict[str, float] | None = None,
) -> list[tuple[CellMetrics, dict, float]]:
    topic_gaps = topic_gaps or {}
    bloom_gaps = bloom_gaps or {}
    topic_importance = topic_importance or {}
    ranked = []
    for cell in cells:
        if cell.attempt_count == 0:
            continue
        importance = topic_importance.get(cell.topic, 1.0)
        cg = topic_gaps.get(cell.topic)
        bg = bloom_gaps.get(cell.bloom_level)
        weakness = weakness_component(cell.mastery, cell.failure_rate, cell.missed_criterion_rate)
        breakdown = {
            "weakness": weakness,
            "coverage_gap": cg,
            "bloom_gap": bg,
            "topic_importance": importance,
        }
        priority = compute_priority(weakness, cg, bg, importance, weights)
        ranked.append((cell, breakdown, priority))
    ranked.sort(key=lambda item: item[2], reverse=True)
    return ranked