import statistics

from app.analytics.taxonomy import BLOOM_LEVELS, TOPICS
from app.schemas.derived import CellMetrics, TopicMetrics


def normalized_score(awarded: float, max_marks: float) -> float:
    if max_marks <= 0:
        raise ValueError("max_marks must be positive")
    return awarded / max_marks


def topic_weight_for(attempt: dict, topic: str) -> float:
    for assign in attempt.get("topic_assignments", []):
        if assign["topic"] == topic:
            return assign["weight"]
    return 0.0


def _qualifying(attempts: list[dict], topic: str, bloom: str | None) -> list[dict]:
    return [
        a
        for a in attempts
        if topic_weight_for(a, topic) > 0
        and (bloom is None or a["bloom_level"] == bloom)
    ]


def compute_mastery(attempts: list[dict], topic: str, bloom: str | None = None) -> float | None:
    subset = _qualifying(attempts, topic, bloom)
    if not subset:
        return None
    numerator = sum(
        a["normalized_score"] * a["max_marks"] * topic_weight_for(a, topic) for a in subset
    )
    denominator = sum(a["max_marks"] * topic_weight_for(a, topic) for a in subset)
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def compute_cell_metrics(attempts: list[dict], topic: str, bloom: str | None) -> CellMetrics:
    subset = _qualifying(attempts, topic, bloom)
    student_count = len({a["student_key"] for a in subset})
    scores = [a["normalized_score"] for a in subset]
    mean = statistics.fmean(scores) if scores else None
    median = statistics.median(scores) if scores else None
    failure_rate = (
        sum(1 for s in scores if s < 0.5) / len(scores) if scores else None
    )
    pass_rate = 1.0 - failure_rate if failure_rate is not None else None
    std_dev = statistics.pstdev(scores) if len(scores) > 1 else None

    missed = []
    for a in subset:
        for c in a.get("criteria_breakdown", []):
            missed.append(c["met"])
    missed_criterion_rate = (
        (sum(1 for m in missed if not m) / len(missed)) if missed else None
    )

    return CellMetrics(
        topic=topic,
        bloom_level=bloom or "",
        mastery=compute_mastery(subset, topic, bloom),
        mean=mean,
        median=median,
        pass_rate=pass_rate,
        failure_rate=failure_rate,
        student_count=student_count,
        attempt_count=len(subset),
        std_dev=std_dev,
        missed_criterion_rate=missed_criterion_rate,
        evidence_status="insufficient_evidence",
    )


def compute_topic_metrics(attempts: list[dict], topic: str) -> TopicMetrics:
    subset = _qualifying(attempts, topic, None)
    student_count = len({a["student_key"] for a in subset})
    scores = [a["normalized_score"] for a in subset]
    return TopicMetrics(
        topic=topic,
        mastery=compute_mastery(subset, topic, None),
        mean=statistics.fmean(scores) if scores else None,
        student_count=student_count,
        attempt_count=len(subset),
        evidence_status="insufficient_evidence",
    )


def compute_topic_bloom_matrix(attempts: list[dict]) -> list[CellMetrics]:
    cells: list[CellMetrics] = []
    for topic in TOPICS:
        for bloom in BLOOM_LEVELS:
            cells.append(compute_cell_metrics(attempts, topic, bloom))
    return cells