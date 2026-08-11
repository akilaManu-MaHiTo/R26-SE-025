"""Normalization of graded student submissions into validated analytics input."""

from pydantic import BaseModel, Field


class StudentDataError(ValueError):
    """Raised when raw student assessment data cannot be normalized safely."""


class NormalizedCriterion(BaseModel):
    criterion: str = Field(min_length=1)
    max_marks: float = Field(gt=0)
    awarded_marks: float = Field(ge=0)


class NormalizedQuestionInput(BaseModel):
    question_no: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    criteria: list[NormalizedCriterion]


class NormalizedStudentInput(BaseModel):
    student_id: str = Field(min_length=1)
    course_code: str = Field(min_length=1)
    course_name: str = Field(min_length=1)
    session_name: str = Field(min_length=1)
    rubric_ref: str = Field(min_length=1)
    questions: list[NormalizedQuestionInput]


def normalize_question_no(value: object) -> str:
    text = str(value).strip()
    return text.zfill(2) if text.isdigit() else text


def _required(value: object, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise StudentDataError(f"missing {label}")
    return text


def _point_key(value: object) -> str:
    return str(value or "").strip().casefold()


def _as_float(value: object, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise StudentDataError(f"invalid {label}") from exc


def _criteria_for_question(rubric_question: dict, result: dict) -> list[NormalizedCriterion]:
    evaluated = result.get("criteria_breakdown") or []
    by_point = {_point_key(item.get("point")): item for item in evaluated}
    criteria: list[NormalizedCriterion] = []

    for position, criterion in enumerate(rubric_question.get("criteria") or []):
        criterion_text = _required(criterion.get("point"), "rubric criterion")
        max_marks = _as_float(criterion.get("marks"), "rubric criterion marks")
        matched = by_point.get(_point_key(criterion_text))
        if matched is None and position < len(evaluated):
            matched = evaluated[position]
        awarded_marks = _as_float(
            (matched or {}).get("earned", (matched or {}).get("awarded_marks", 0)),
            "awarded criterion marks",
        )
        if awarded_marks < 0 or awarded_marks > max_marks:
            raise StudentDataError(
                f"awarded marks for question {normalize_question_no(rubric_question.get('question_no'))} "
                f"exceeds criterion maximum"
            )
        criteria.append(
            NormalizedCriterion(
                criterion=criterion_text,
                max_marks=max_marks,
                awarded_marks=awarded_marks,
            )
        )
    return criteria


def normalize_student_submission(
    course: dict, rubric: dict, submission: dict
) -> NormalizedStudentInput:
    """Join raw course, rubric, and grading records into a trusted input model."""
    student_id = _required(
        submission.get("student_id") or submission.get("student_key"), "student identity"
    )
    course_code = _required(
        course.get("course_code")
        or course.get("code")
        or rubric.get("subject_code")
        or submission.get("subject_code"),
        "course identity",
    )
    session_name = _required(
        submission.get("session_name") or rubric.get("session_name"), "session identity"
    )
    course_name = str(course.get("course_name") or course.get("name") or "").strip()
    if not course_name:
        course_name = "Database Management Systems" if course_code == "IT2040" else course_code
    rubric_ref = str(rubric.get("_id") or submission.get("rubric_ref") or "unknown")

    rubric_by_question: dict[str, dict] = {}
    for rubric_question in rubric.get("questions") or []:
        question_no = normalize_question_no(rubric_question.get("question_no"))
        if not question_no:
            raise StudentDataError("missing rubric question identity")
        rubric_by_question[question_no] = rubric_question

    evaluation = submission.get("evaluation") or {}
    result_rows = evaluation.get("results") if isinstance(evaluation, dict) else None
    if result_rows is None:
        result_rows = submission.get("results") or []
    results_by_question: dict[str, dict] = {}
    for result in result_rows:
        question_no = normalize_question_no(result.get("q_no", result.get("question_no")))
        if not question_no or question_no not in rubric_by_question:
            raise StudentDataError(f"result references missing rubric question {question_no}")
        if question_no in results_by_question:
            raise StudentDataError(f"duplicate result for question {question_no}")
        results_by_question[question_no] = result

    questions: list[NormalizedQuestionInput] = []
    for question_no, result in results_by_question.items():
        rubric_question = rubric_by_question[question_no]
        criteria = _criteria_for_question(rubric_question, result)
        max_score = sum(criterion.max_marks for criterion in criteria)
        if max_score <= 0:
            raise StudentDataError(f"invalid maximum marks for question {question_no}")
        score = _as_float(result.get("score"), f"score for question {question_no}")
        if score < 0 or score > max_score:
            raise StudentDataError(
                f"score for question {question_no} exceeds maximum of {max_score}"
            )
        questions.append(
            NormalizedQuestionInput(
                question_no=question_no,
                question_text=_required(rubric_question.get("question_text"), "rubric question text"),
                score=score,
                max_score=max_score,
                criteria=criteria,
            )
        )

    return NormalizedStudentInput(
        student_id=student_id,
        course_code=course_code,
        course_name=course_name,
        session_name=session_name,
        rubric_ref=rubric_ref,
        questions=questions,
    )
