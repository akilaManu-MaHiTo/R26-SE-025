"""Normalization of graded student submissions into validated analytics input."""

from pydantic import BaseModel, Field
from math import isfinite, isclose


class StudentDataError(ValueError):
    """Raised when raw student assessment data cannot be normalized safely."""


def saved_total_score(submission: dict) -> dict:
    """Read a saved total without treating a missing award as a maximum or zero."""
    evaluation = submission.get("evaluation") or {}
    if not isinstance(evaluation, dict):
        evaluation = {}
    maximum = evaluation.get("max_score")
    if maximum is None:
        maximum = submission.get("max_marks_paper_total")
    try:
        maximum = _as_float(maximum, "maximum marks")
        if maximum <= 0:
            maximum = None
    except StudentDataError:
        maximum = None
    try:
        obtained = _as_float(evaluation.get("total_score"), "awarded marks")
        if maximum is None or not 0 <= obtained <= maximum:
            obtained = None
    except StudentDataError:
        obtained = None
    return {"obtained": obtained, "maximum": maximum,
            "percentage": round(obtained / maximum * 100, 2) if obtained is not None and maximum is not None else None}


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
    approved_topic: str | None = None


class NormalizedStudentInput(BaseModel):
    student_id: str = Field(min_length=1)
    course_code: str = Field(min_length=1)
    course_name: str = Field(min_length=1)
    subject_name: str = Field(min_length=1)
    session_name: str = Field(min_length=1)
    year: int
    month: int
    semester: int
    rubric_ref: str = Field(min_length=1)
    questions: list[NormalizedQuestionInput]


def normalize_question_no(value: object) -> str:
    if value is None:
        return ""
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
        number = float(value)
        if isinstance(value, bool) or not isfinite(number):
            raise ValueError("nonfinite or boolean marks")
        return number
    except (TypeError, ValueError) as exc:
        raise StudentDataError(f"invalid {label}") from exc


def _criteria_for_question(rubric_question: dict, result: dict) -> list[NormalizedCriterion]:
    evaluated = result.get("criteria_breakdown") or []
    rubric_criteria = rubric_question.get("criteria") or []
    if not isinstance(evaluated, list) or not isinstance(rubric_criteria, list) or not all(isinstance(c, dict) for c in evaluated + rubric_criteria):
        raise StudentDataError("Unreadable criterion evidence")
    by_point = {_point_key(item.get("point")): item for item in evaluated}
    rubric_keys = [_point_key(c.get("point")) for c in rubric_question.get("criteria") or []]
    if (not rubric_keys or len(set(rubric_keys)) != len(rubric_keys)
            or len(by_point) != len(evaluated) or set(by_point) != set(rubric_keys)):
        raise StudentDataError("missing, duplicate or mismatched evaluation criterion")
    criteria: list[NormalizedCriterion] = []

    for criterion in rubric_question.get("criteria") or []:
        criterion_text = _required(criterion.get("point"), "rubric criterion")
        max_marks = _as_float(criterion.get("marks"), "rubric criterion marks")
        if max_marks <= 0:
            raise StudentDataError("invalid rubric criterion maximum")
        matched = by_point.get(_point_key(criterion_text))
        if matched is None:
            raise StudentDataError(
                f"missing evaluation criterion for question "
                f"{normalize_question_no(rubric_question.get('question_no'))}"
            )
        awarded_marks = _as_float(
            matched.get("awarded_marks", matched.get("earned")),
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
    from app.services.exam_paper import _identity
    if not all(isinstance(doc, dict) for doc in (course, rubric, submission)):
        raise StudentDataError("Unreadable course, rubric or submission")
    if any(a is not None and b is not None and a != b for a, b in zip(_identity(rubric), _identity(submission))):
        raise StudentDataError("Submission and rubric refer to different exams")
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
    subject_name = str(rubric.get("subject_name") or course_name or "").strip() or course_code
    try:
        year = int(rubric.get("year") or 0)
        month = int(rubric.get("month") or 0)
        semester = int(rubric.get("semester") or 0)
    except (TypeError, ValueError) as exc:
        raise StudentDataError("invalid rubric session identity") from exc
    rubric_ref = str(rubric.get("_id") or submission.get("rubric_ref") or "unknown")

    rubric_by_question: dict[str, dict] = {}
    rubric_questions = rubric.get("questions") or []
    if not isinstance(rubric_questions, list) or not all(isinstance(q, dict) for q in rubric_questions):
        raise StudentDataError("Unreadable rubric questions")
    for rubric_question in rubric_questions:
        question_no = normalize_question_no(rubric_question.get("question_no"))
        if not question_no:
            raise StudentDataError("missing rubric question identity")
        if question_no in rubric_by_question:
            raise StudentDataError(f"duplicate rubric question {question_no}")
        rubric_by_question[question_no] = rubric_question

    evaluation = submission.get("evaluation") or {}
    if not isinstance(evaluation, dict):
        raise StudentDataError("Unreadable evaluation")
    result_rows = evaluation.get("results") if isinstance(evaluation, dict) else None
    if result_rows is None:
        result_rows = submission.get("results") or []
    if not isinstance(result_rows, list) or not all(isinstance(r, dict) for r in result_rows):
        raise StudentDataError("Unreadable question results")
    results_by_question: dict[str, dict] = {}
    for result in result_rows:
        question_no = normalize_question_no(result.get("q_no", result.get("question_no")))
        if not question_no or question_no not in rubric_by_question:
            raise StudentDataError(f"result references missing rubric question {question_no}")
        if question_no in results_by_question:
            raise StudentDataError(f"duplicate result for question {question_no}")
        results_by_question[question_no] = result

    missing_questions = set(rubric_by_question) - set(results_by_question)
    if not results_by_question or missing_questions:
        missing_list = ", ".join(sorted(missing_questions)) or "all questions"
        raise StudentDataError(f"missing result for rubric question {missing_list}")

    questions: list[NormalizedQuestionInput] = []
    for question_no, result in results_by_question.items():
        if result.get("error"):
            raise StudentDataError(f"Question {question_no} has a grading error")
        rubric_question = rubric_by_question[question_no]
        criteria = _criteria_for_question(rubric_question, result)
        max_score = sum(criterion.max_marks for criterion in criteria)
        if max_score <= 0:
            raise StudentDataError(f"invalid maximum marks for question {question_no}")
        if rubric_question.get("max_marks") is not None and not isclose(_as_float(rubric_question["max_marks"], "question maximum"), max_score, abs_tol=0.01):
            raise StudentDataError(f"Question {question_no} maximum differs from rubric criteria")
        score = _as_float(result.get("score"), f"score for question {question_no}")
        if score < 0 or score > max_score:
            raise StudentDataError(
                f"score for question {question_no} exceeds maximum of {max_score}"
            )
        if not isclose(score, sum(c.awarded_marks for c in criteria), abs_tol=0.01):
            raise StudentDataError(f"score for question {question_no} differs from awarded criterion marks")
        questions.append(
            NormalizedQuestionInput(
                question_no=question_no,
                question_text=_required(rubric_question.get("question_text"), "rubric question text"),
                score=score,
                max_score=max_score,
                criteria=criteria,
                approved_topic=rubric_question.get("approved_topic"),
            )
        )

    for field, actual in (("total_score", sum(q.score for q in questions)), ("max_score", sum(q.max_score for q in questions))):
        if evaluation.get(field) is not None and not isclose(_as_float(evaluation[field], field), actual, abs_tol=0.01):
            raise StudentDataError(f"Evaluation {field} differs from question totals")

    return NormalizedStudentInput(
        student_id=student_id,
        course_code=course_code,
        course_name=course_name,
        subject_name=subject_name,
        session_name=session_name,
        year=year,
        month=month,
        semester=semester,
        rubric_ref=rubric_ref,
        questions=questions,
    )
