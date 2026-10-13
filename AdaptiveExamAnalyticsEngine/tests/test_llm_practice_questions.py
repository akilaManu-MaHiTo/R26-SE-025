import pytest
from pydantic import ValidationError

from app.llm.roles.generate_practice import PracticeQuestions


def test_practice_questions_accepts_valid_batch():
    questions = PracticeQuestions(
        requested_count=5,
        questions=[
            {"prompt": "Explain authentication.", "bloom_level": "Understand", "topic": "SQL", "difficulty": "Medium", "hints": ["CREATE LOGIN"]}
        ],
    )
    assert questions.requested_count == 5


def test_practice_questions_rejects_unknown_difficulty():
    with pytest.raises(ValidationError):
        PracticeQuestions(
            requested_count=1,
            questions=[{"prompt": "p", "bloom_level": "Understand", "topic": "SQL", "difficulty": "Insane", "hints": []}],
        )
