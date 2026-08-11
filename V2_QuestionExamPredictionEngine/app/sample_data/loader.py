import json
from pathlib import Path

SAMPLE_DIR = Path(__file__).resolve().parent


def _load(name: str) -> dict:
    path = SAMPLE_DIR / name
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _slug(value: str) -> str:
    return "_".join(v.lower() for v in value.split())


def _exam_id(rubric: dict) -> str:
    course_code = rubric.get("subject_code") or "IT2040"
    session = _slug(rubric.get("session_name", "exam"))
    return f"{course_code}-{session}"


def parse_paper(rubric: dict) -> dict:
    course_code = rubric.get("subject_code") or "IT2040"
    exam_id = _exam_id(rubric)
    questions = []
    for q in rubric["questions"]:
        questions.append(
            {
                "question_number": q["question_no"],
                "parts": [
                    {
                        "part": "a",
                        "text": q["question_text"],
                        "max_marks": float(q["max_marks"]),
                    }
                ],
            }
        )
    return {
        "exam_id": exam_id,
        "course_code": course_code,
        "year": rubric.get("year")
        or (2021 if "2021" in rubric.get("session_name", "") else 0),
        "title": rubric.get("session_name", ""),
        "questions": questions,
    }


def parse_submission(
    sub: dict, exam_id: str, course_code: str, rubric_questions: list[dict]
) -> list[dict]:
    student_key = sub.get("student_id") or sub.get("student_key") or "student-1"
    max_by_q = {
        str(m["question_no"]).zfill(2): float(m["max_marks"])
        for m in sub.get("max_marks_per_question", [])
    }
    rubric_by_qno = {
        str(q["question_no"]).zfill(2): q for q in rubric_questions
    }
    results = sub["evaluation"]["results"] if "evaluation" in sub else sub.get("results", [])
    rows = []
    for r in results:
        q_no = str(r["q_no"]).zfill(2)
        rubric_q = rubric_by_qno.get(q_no, {})
        rubric_criteria = rubric_q.get("criteria", [])
        evaluated = r.get("criteria_breakdown", [])
        assert len(rubric_criteria) == len(evaluated), (
            f"criteria count mismatch for question {q_no}"
        )
        criteria = []
        for position, rubric_criterion in enumerate(rubric_criteria):
            point = rubric_criterion.get("point", "")
            matched = next(
                (c for c in evaluated if c.get("point") == point), None
            )
            # Breakdown points are abbreviated vs rubric points, so the exact
            # match above never fires; positional fallback does the real alignment.
            if matched is None and position < len(evaluated):
                matched = evaluated[position]
            awarded = (
                float(matched.get("awarded_marks", matched.get("earned", 0.0)))
                if matched
                else 0.0
            )
            max_marks = float(rubric_criterion.get("marks", 0.0))
            criteria.append(
                {
                    "criterion": point,
                    "awarded_marks": awarded,
                    "max_marks": max_marks,
                    "met": awarded >= max_marks,
                }
            )
        rows.append(
            {
                "exam_id": exam_id,
                "course_code": course_code,
                "student_key": f"{course_code}-{student_key}",
                "question_number": q_no,
                "part": "a",
                "awarded_marks": float(r["score"]),
                "max_marks": max_by_q.get(q_no, 0.0),
                "answer_text": "",
                "feedback": r.get("feedback", ""),
                "criteria_breakdown": criteria,
            }
        )
    return rows


def course_settings(course: dict) -> dict:
    course_code = (
        course.get("code") or course.get("subject_code") or "IT2040"
    )
    course_name = (
        course.get("name")
        or course.get("course_name")
        or "Database Management Systems"
    )
    return {
        "course_code": course_code,
        "course_name": course_name,
        "settings": {
            "pass_threshold": 0.5,
            "min_students": 3,
            "min_attempts": 1,
            "topic_importance": {},
            "blueprint_targets": {},
        },
    }


def load_real() -> tuple[dict, list[dict], list[dict]]:
    course_document = _load("courses.json")
    rubric = _load("rubricCollection.json")

    paper = parse_paper(rubric)
    course = course_settings(course_document)

    submissions = []
    for sub_path in sorted(SAMPLE_DIR.glob("submission*.json")):
        sub = json.loads(sub_path.read_text(encoding="utf-8"))
        submissions.extend(
            parse_submission(
                sub, paper["exam_id"], paper["course_code"], rubric["questions"]
            )
        )
    return course, [paper], submissions