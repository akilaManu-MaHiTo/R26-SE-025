"""Recover a question excerpt from legacy saved OCR transcripts."""

import re

from app.ingestion.student_data import normalize_question_no


def question_excerpt(transcript: str, question_no: str) -> str | None:
    # shortcut: standalone numeric Q/Question headings only; extend when other OCR formats need recovery.
    headings = list(re.finditer(r"(?im)^[ \t]*(?:question|q)[ \t]*[.:-]?[ \t]*(\d+)[ \t]*[:.)-]?[ \t]*\r?$", transcript))
    for index, heading in enumerate(headings):
        if normalize_question_no(heading.group(1)) == question_no:
            end = headings[index + 1].start() if index + 1 < len(headings) else len(transcript)
            return transcript[heading.end():end].strip()[:1200] or None
    return None
