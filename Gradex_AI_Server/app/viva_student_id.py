"""Student ID rules for vivas, in one place.

Every student ID in the system (sample data, accounts, exams) is "IT" followed by 8 digits, for
example IT22557056. The web client mirrors this rule in viva/studentId.ts so a typo is caught
as it is typed, but the server is the authority and re-checks every ID it receives.
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import HTTPException

STUDENT_ID_PATTERN = re.compile(r"^IT\d{8}$")
STUDENT_ID_HINT = "Student ID must look like IT22557056 (IT followed by 8 digits)."


def normalize_student_id(value: Optional[str], *, required: bool = True) -> Optional[str]:
    """Trim, upper-case and validate a student ID; raise 400 when it is wrong.

    Returns None for a blank value when the ID is optional.
    """
    cleaned = (value or "").strip().upper()
    if not cleaned:
        if required:
            raise HTTPException(status_code=400, detail="student_id is required.")
        return None
    if not STUDENT_ID_PATTERN.fullmatch(cleaned):
        raise HTTPException(status_code=400, detail=STUDENT_ID_HINT)
    return cleaned
