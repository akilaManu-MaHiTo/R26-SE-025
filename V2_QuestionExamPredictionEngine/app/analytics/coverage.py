from app.analytics.taxonomy import BLOOM_LEVELS, TOPICS


def observed_frequency(attempts: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    seen_questions: set[str] = set()
    for a in attempts:
        qid = a["question_id"]
        if qid in seen_questions:
            continue
        seen_questions.add(qid)
        if field == "bloom_level":
            key = a["bloom_level"]
        else:
            key = field
            if not any(assign["topic"] == field for assign in a.get("topic_assignments", [])):
                continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def observed_share(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    if total == 0:
        return {}
    return {k: v / total for k, v in counts.items()}


def _normalize(target: dict[str, float]) -> dict[str, float]:
    total = sum(target.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in target.items()}


def coverage_gap(
    observed_share: dict[str, float],
    target: dict[str, float] | None,
) -> float | None:
    if not target or sum(target.values()) <= 0:
        return None
    norm_target = _normalize(target)
    keys = set(observed_share) | set(norm_target)
    deviations = [
        abs(observed_share.get(k, 0.0) - norm_target.get(k, 0.0)) for k in keys
    ]
    return sum(deviations) / len(deviations) if deviations else None


def detect_gaps(
    attempts: list[dict],
    topics: list[str] | None = None,
    targets: dict[str, dict[str, float]] | None = None,
) -> dict[str, list[str]]:
    topics = topics or TOPICS
    targets = targets or {}
    bloom_targets = targets.get("bloom", {})
    gaps: dict[str, list[str]] = {"coverage_gaps": [], "bloom_gaps": []}

    topic_share = observed_share(observed_frequency(attempts, "topic"))
    for topic in topics:
        if topic_share.get(topic, 0.0) == 0.0:
            gaps["coverage_gaps"].append(topic)

    bloom_share = observed_share(observed_frequency(attempts, "bloom_level"))
    for bloom in BLOOM_LEVELS:
        if bloom_targets and bloom_share.get(bloom, 0.0) == 0.0 and bloom_targets.get(bloom, 0.0) > 0:
            gaps["bloom_gaps"].append(bloom)

    return gaps