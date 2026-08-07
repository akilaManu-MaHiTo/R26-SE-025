import statistics

from app.schemas.derived import CellMetrics, TopicMetrics

GRADE_BANDS = [
    ("A", 0.85),
    ("B", 0.70),
    ("C", 0.55),
    ("D", 0.40),
    ("F", -1.0),
]


def evidence_status(
    mean: float | None,
    student_count: int,
    attempt_count: int,
    pass_threshold: float,
    min_students: int,
    min_attempts: int,
) -> str:
    if mean is None or student_count < min_students or attempt_count < min_attempts:
        return "insufficient_evidence"
    if mean < pass_threshold:
        return "confirmed_weakness"
    return "strength"


def grade_of(score: float) -> str:
    for band, floor in GRADE_BANDS:
        if score >= floor:
            return band
    return "F"


def cohort_summary(attempts: list[dict]) -> dict:
    scores = [a["normalized_score"] for a in attempts]
    distribution: dict[str, int] = {}
    for s in scores:
        band = grade_of(s)
        distribution[band] = distribution.get(band, 0) + 1
    failure_rate = sum(1 for s in scores if s < 0.5) / len(scores) if scores else None
    return {
        "mean": statistics.fmean(scores) if scores else None,
        "median": statistics.median(scores) if scores else None,
        "pass_rate": (1.0 - failure_rate) if failure_rate is not None else None,
        "failure_rate": failure_rate,
        "student_count": len({a["student_key"] for a in attempts}),
        "attempt_count": len(scores),
        "grade_distribution": distribution,
    }


def apply_evidence_statuses(
    metrics: list[CellMetrics] | list[TopicMetrics],
    pass_threshold: float,
    min_students: int,
    min_attempts: int,
) -> None:
    for m in metrics:
        m.evidence_status = evidence_status(
            m.mean, m.student_count, m.attempt_count, pass_threshold, min_students, min_attempts
        )