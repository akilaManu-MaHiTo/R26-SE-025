from app.config import settings


def test_default_threshold_is_50_percent():
    assert settings.pass_threshold == 0.5


def test_default_evidence_minima():
    assert settings.min_students == 10
    assert settings.min_attempts == 2
