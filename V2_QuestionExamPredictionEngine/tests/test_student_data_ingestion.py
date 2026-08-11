import pytest

from app.sample_data.loader import _load

from app.ingestion.student_data import (
    StudentDataError,
    normalize_student_submission,
)


def minimal_course() -> dict:
    return {"course_code": "IT2040", "course_name": "Database Management Systems"}


def minimal_rubric() -> dict:
    return {
        "_id": "rubric-1",
        "session_name": "Final Examination",
        "subject_code": "IT2040",
        "questions": [
            {
                "question_no": "01",
                "question_text": "State the answer.",
                "max_marks": 5,
                "criteria": [{"point": "Correct answer", "marks": 5}],
            }
        ],
    }


def minimal_submission(q_no: str, score: float, max_score: float) -> dict:
    return {
        "rubric_ref": "rubric-1",
        "session_name": "Final Examination",
        "subject_code": "IT2040",
        "student_id": "IT21001234",
        "evaluation": {
            "results": [
                {
                    "q_no": q_no,
                    "score": score,
                    "criteria_breakdown": [
                        {"point": "Correct answer", "marks": max_score, "earned": score}
                    ],
                }
            ]
        },
    }


def test_normalize_submission_joins_questions_and_criteria():
    rubric = _load("rubricCollection.json")
    submission = _load("submission.json")
    normalized = normalize_student_submission(
        {"course_code": "IT2040", "course_name": "Database Management Systems"},
        rubric,
        submission,
    )
    assert normalized.student_id == "IT21001234"
    assert normalized.course_code == "IT2040"
    assert normalized.course_name == "Database Management Systems"
    assert len(normalized.questions) == 11
    assert normalized.questions[0].question_no == "01"
    assert normalized.questions[0].score == 6.0
    assert normalized.questions[0].max_score == 8.0
    assert normalized.questions[0].criteria[0].awarded_marks == 2.5


def test_normalize_submission_rejects_result_without_rubric_question():
    submission = minimal_submission(q_no="99", score=1, max_score=1)
    with pytest.raises(StudentDataError, match="question 99"):
        normalize_student_submission(minimal_course(), minimal_rubric(), submission)


def test_normalize_submission_rejects_awarded_marks_above_maximum():
    submission = minimal_submission(q_no="01", score=6, max_score=5)
    with pytest.raises(StudentDataError, match="exceeds"):
        normalize_student_submission(minimal_course(), minimal_rubric(), submission)
