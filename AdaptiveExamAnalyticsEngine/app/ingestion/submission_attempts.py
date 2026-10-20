"""Select replacement essay grades without deleting submission history."""

from collections import defaultdict
from datetime import datetime, timezone


def _processed_at(record):
    value = record.get("processed_at")
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def current_essay_attempts(records):
    from app.services.exam_paper import _identity

    groups = defaultdict(list)
    for index, record in enumerate(records):
        if record.get("archived_at") is not None or record.get("archived_reason") == "superseded_by_new_batch":
            continue
        identity, student = _identity(record), record.get("student_id")
        # Incomplete exam identities must not merge unrelated attempts.
        key = (identity, record.get("examKey"), student) if None not in identity and student else (index,)
        groups[key].append(record)
    selected = set()
    for attempts in groups.values():
        graded = [r for r in attempts if r.get("status") == "graded"]
        if len(graded) == 1:
            attempts = graded
        elif len(graded) > 1:
            dates = [_processed_at(r) for r in graded]
            if all(d is not None for d in dates) and dates.count(max(dates)) == 1:
                attempts = [graded[dates.index(max(dates))]]
        selected.update(id(r) for r in attempts)
    return [r for r in records if id(r) in selected]


def current_essay_sources(sources):
    records = sources.get("submissions", [])
    selected = current_essay_attempts(records)
    selected_refs = {str(r.get("rubric_ref")) for r in selected}
    superseded_refs = {str(r.get("rubric_ref")) for r in records} - selected_refs if selected else set()
    return {**sources, "submissions": selected,
            "superseded_rubrics": sources.get("superseded_rubrics", []) + [
                r for r in sources.get("rubrics", []) if str(r.get("_id")) in superseded_refs],
            "rubrics": [r for r in sources.get("rubrics", []) if str(r.get("_id")) not in superseded_refs]}
