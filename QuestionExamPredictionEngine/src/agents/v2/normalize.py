"""Normalization of MongoDB-style source documents into canonical records.

Agents never read MongoDB directly. This module converts the source
``courses`` and ``rubricCollection`` document shapes into the canonical
records defined in ``records.py`` so that downstream analytics only depend
on stable typed contracts.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from src.agents.v2.records import (
    AssessmentRecord,
    CourseRecord,
    QuestionRecord,
    RubricCriterion,
)

_OBJECT_ID_RE = re.compile(r"[0-9a-fA-F]{24}")


def _id_to_str(value: Any) -> str:
    """Return the hex representation of a MongoDB ObjectId or its string form."""
    if value is None:
        return ""
    text = str(value).strip()
    match = _OBJECT_ID_RE.search(text)
    return match.group(0) if match else text


def normalize_question_no(value: Any) -> str:
    """Normalize question numbers so ``"01"``, ``"1"``, and integer ``1`` join."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.isdigit():
        return str(int(text))
    return text


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    return None


def _session_slug(subject_code: str, session_name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", session_name.lower()).strip("-")
    return f"{subject_code}:{base}" if base else subject_code


def normalize_course(doc: dict) -> CourseRecord:
    subject_code = str(doc.get("code", "")).strip().upper()
    return CourseRecord(
        course_id=_id_to_str(doc.get("_id")) or subject_code,
        subject_code=subject_code,
        name=str(doc.get("name", "")),
        description=str(doc.get("description", "")),
        source_collection=str(doc.get("source_collection", "courses")),
        source_document_id=str(doc.get("_id") or ""),
    )


def normalize_assessment(
    doc: dict,
    course: CourseRecord | None = None,
) -> AssessmentRecord:
    subject_code = str(doc.get("subject_code", "")).strip().upper()
    rubric_id = _id_to_str(doc.get("_id"))
    session_name = str(doc.get("session_name", ""))
    return AssessmentRecord(
        assessment_id=rubric_id or _session_slug(subject_code, session_name),
        course_id=course.course_id if course else _id_to_str(doc.get("course_id")),
        subject_code=subject_code,
        session_name=session_name,
        rubric_id=rubric_id,
        rubric_filename=str(doc.get("filename", "")) or None,
        parsed_at=_to_datetime(doc.get("parsed_at")),
        assessment_order=doc.get("assessment_order"),
    )


def normalize_question(
    doc: dict,
    assessment: AssessmentRecord,
) -> QuestionRecord:
    normalized = normalize_question_no(doc.get("question_no"))
    criteria = [
        RubricCriterion(
            point=str(item.get("point", "")),
            marks=float(item.get("marks", 0) or 0),
        )
        for item in doc.get("criteria", []) or []
        if isinstance(item, dict)
    ]
    return QuestionRecord(
        question_id=(
            f"{assessment.assessment_id}:{normalized}"
            if assessment.assessment_id
            else normalized
        ),
        assessment_id=assessment.assessment_id,
        question_no_raw=str(doc.get("question_no") or ""),
        question_no_normalized=normalized,
        question_text=str(doc.get("question_text", "")),
        max_marks=float(doc.get("max_marks", 0) or 0),
        topic_id=str(doc.get("topic") or doc.get("topic_id") or "") or None,
        model_answer=str(doc.get("model_answer") or "") or None,
        rubric_criteria=criteria,
    )
