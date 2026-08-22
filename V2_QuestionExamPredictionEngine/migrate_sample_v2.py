"""Regenerate the checked-in sample documents in the v2 data structure.

Reads the current JSON files under app/sample_data/ (one folder per MongoDB
collection) and rewrites them to the v2 shape (criteria as
{point, awarded_marks, reason}, paper_key, subject metadata, exam roster,
lecturer_note) while preserving every existing value. Re-running is a no-op
for already-migrated files.

Run from the repository root:
    python migrate_sample_v2.py
"""

import json
from pathlib import Path

SAMPLE_DIR = Path(__file__).resolve().parent / "app" / "sample_data"

COURSES_FILE = "courses/courses.json"
RUBRIC_FILE = "rubricCollection/rubricCollection.json"
SUBMISSIONS_DIR = "submissions"

SUBJECT_CODE = "IT2040"
SUBJECT_NAME = "Database Management Systems"
YEAR = 2021
MONTH = "December"
SEMESTER = "Semester 1"
SESSION_NAME = "Final Examination 2021"
PAPER_KEY = "IT2040-FE-2021"
COURSE_DESCRIPTION = (
    "Database design and implementation: ER/EER modeling, relational schema "
    "design and normalization, SQL and T-SQL, transaction management, "
    "concurrency control, and SQL Server user/role administration."
)


def _load(name: str) -> object:
    with open(SAMPLE_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def _save(name: str, document: object) -> None:
    with open(SAMPLE_DIR / name, "w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _reason(awarded: float, max_marks: float) -> str:
    if awarded <= 0:
        return "No marks awarded"
    if awarded >= max_marks:
        return "Full marks"
    return "Partial credit"


def _reshape_criterion(criterion: dict) -> dict:
    if "awarded_marks" in criterion and "reason" in criterion:
        return criterion
    awarded = float(criterion.pop("awarded_marks", criterion.pop("earned", 0.0)))
    max_marks = float(criterion.pop("marks", awarded))
    criterion["awarded_marks"] = awarded
    criterion["reason"] = _reason(awarded, max_marks)
    return criterion


def course_v2(existing: dict) -> dict:
    return {
        "_id": existing.get("_id", "ObjectId('...')"),
        "code": existing.get("code", existing.get("subject_code", SUBJECT_CODE)),
        "name": existing.get("name", SUBJECT_NAME),
        "description": existing.get("description", COURSE_DESCRIPTION),
    }


def rubric_v2(existing: dict, roster: list[str]) -> dict:
    document = {k: v for k, v in existing.items() if k != "_id"}
    document["_id"] = existing.get("_id", "ObjectId('...')")
    document["subject_code"] = SUBJECT_CODE
    document["subject_name"] = SUBJECT_NAME
    document["year"] = existing.get("year", YEAR)
    document["month"] = existing.get("month", MONTH)
    document["semester"] = existing.get("semester", SEMESTER)
    document["session_name"] = existing.get("session_name", SESSION_NAME)
    if "exam_roster" not in existing:
        document["exam_roster"] = sorted(roster)
    return document


def submission_v2(existing: dict) -> dict:
    document = {k: v for k, v in existing.items() if k != "_id"}
    document["_id"] = existing.get("_id", "ObjectId('...')")
    document["rubric_ref"] = existing.get("rubric_ref", "ObjectId('...')")
    document["paper_key"] = existing.get("paper_key", PAPER_KEY)
    document["subject_code"] = SUBJECT_CODE
    document["subject_name"] = SUBJECT_NAME
    document["year"] = existing.get("year", YEAR)
    document["month"] = existing.get("month", MONTH)
    document["semester"] = existing.get("semester", SEMESTER)
    document["session_name"] = existing.get("session_name", SESSION_NAME)
    if "lecturer_note" not in document:
        document["lecturer_note"] = ""
    evaluation = document.setdefault("evaluation", {})
    for result in evaluation.get("results", []):
        result["criteria_breakdown"] = [
            _reshape_criterion(c) for c in result.get("criteria_breakdown", [])
        ]
    return document


def main() -> None:
    courses = _load(COURSES_FILE)
    raw_rubric = _load(RUBRIC_FILE)
    submission_paths = sorted((SAMPLE_DIR / SUBMISSIONS_DIR).glob("submission*.json"))
    submissions = [
        sub
        for path in submission_paths
        for sub in json.loads(path.read_text(encoding="utf-8"))
    ]
    roster = [sub["student_id"] for sub in submissions]
    _save(COURSES_FILE, [course_v2(course) for course in courses])
    # Support both dict and list storage for rubric
    if isinstance(raw_rubric, list):
        migrated = [rubric_v2(r, roster) for r in raw_rubric]
        _save(RUBRIC_FILE, migrated)
    else:
        _save(RUBRIC_FILE, rubric_v2(raw_rubric, roster))
    for path in submission_paths:
        _save(
            f"{SUBMISSIONS_DIR}/{path.name}",
            [
                submission_v2(sub)
                for sub in json.loads(path.read_text(encoding="utf-8"))
            ],
        )


if __name__ == "__main__":
    main()
