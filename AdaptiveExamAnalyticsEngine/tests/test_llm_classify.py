import pydantic
import pytest

from app.llm.roles.classify import ClassificationResponse

VALID = {
    "primary_topic": "Schema Refinement",
    "topic_weights": {"Schema Refinement": 0.8, "Logical Database Design": 0.2},
    "bloom_level": "Analyze",
    "question_type": "problem_solving",
    "key_concepts": ["functional dependency", "attribute closure"],
    "rationale": "Uses attribute closure to find a candidate key",
}


def test_valid_classification_passes():
    result = ClassificationResponse(**VALID)
    assert result.primary_topic == "Schema Refinement"
    assert result.review_flag is False


def test_weights_must_sum_to_one():
    with pytest.raises(pydantic.ValidationError):
        ClassificationResponse(**{**VALID, "topic_weights": {"SQL": 0.5}})


def test_topic_must_be_in_taxonomy():
    with pytest.raises(pydantic.ValidationError):
        ClassificationResponse(**{**VALID, "primary_topic": "Not a Topic"})


def test_bloom_must_be_in_levels():
    with pytest.raises(pydantic.ValidationError):
        ClassificationResponse(**{**VALID, "bloom_level": "Memorize"})
