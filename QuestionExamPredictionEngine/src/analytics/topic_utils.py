"""Helpers for resolving topic labels from exam data.

This module will prefer canonical topic names when a canonical list is
available at `data/topics.json` in the project root. If a found topic
matches (case-insensitive exact or substring) a canonical name, the
canonical form is returned.
"""

from pathlib import Path
import json


def _load_canonical_topics():
    project_root = Path(__file__).resolve().parents[2]
    topics_path = project_root / "data" / "topics.json"
    try:
        with topics_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [str(t).strip() for t in data if t]
    except Exception:
        pass

    return []


_CANONICAL_TOPICS = _load_canonical_topics()


def _normalize_to_canonical(topic):
    if not topic:
        return topic

    t = str(topic).strip()
    if not _CANONICAL_TOPICS:
        return t

    tl = t.lower()
    # exact match
    for canon in _CANONICAL_TOPICS:
        if canon.lower() == tl:
            return canon

    # substring matches (either direction)
    for canon in _CANONICAL_TOPICS:
        cl = canon.lower()
        if tl in cl or cl in tl:
            return canon

    return t


def resolve_topic(exam_data, question_number, part_id=None, default="Unknown"):
    """Return the most specific topic available for a question part.

    If a canonical topic is available it will be returned instead of the
    raw exam topic string.
    """
    for question in exam_data.get("questions", []):
        if str(question.get("question_number")) != str(question_number):
            continue

        for part in question.get("parts", []):
            if part.get("part") != part_id:
                continue

            topic = part.get("topic")
            if topic:
                return _normalize_to_canonical(topic)
            break

        topic = question.get("topic")
        if topic:
            return _normalize_to_canonical(topic)

        if part_id is not None:
            return f"Q{question_number}{part_id}"

        return f"Q{question_number}"

    return default