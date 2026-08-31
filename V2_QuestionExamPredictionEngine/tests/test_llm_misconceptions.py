import pydantic
import pytest

from app.llm.roles.misconceptions import MisconceptionItem, MisconceptionSummary


def test_confirmed_vs_inferred_confidence():
    summary = MisconceptionSummary(
        topic="Schema Refinement",
        misconceptions=[
            MisconceptionItem(statement="s", evidence="e", confidence="confirmed"),
            MisconceptionItem(statement="s2", evidence="e2", confidence="inferred_low_confidence"),
        ],
    )
    assert len(summary.misconceptions) == 2


def test_invalid_confidence_rejected():
    with pytest.raises(pydantic.ValidationError):
        MisconceptionItem(statement="s", evidence="e", confidence="definite")
