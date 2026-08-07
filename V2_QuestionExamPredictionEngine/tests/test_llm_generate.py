import pydantic
import pytest

from app.llm.roles.generate import CandidateQuestion, CandidateQuestions


def test_valid_candidate():
    result = CandidateQuestions(
        target_topic="SQL",
        target_bloom="Apply",
        requested_count=1,
        candidates=[
            CandidateQuestion(
                text="Write a JOIN query",
                topic="SQL",
                bloom_level="Apply",
                marks=4.0,
                rationale="r",
                model_answer="SELECT ...",
                rubric_criteria=["correct join"],
            )
        ],
    )
    assert result.candidates[0].marks == 4.0


def test_marks_must_be_positive():
    with pytest.raises(pydantic.ValidationError):
        CandidateQuestion(text="t", topic="SQL", bloom_level="Apply", marks=0.0)
