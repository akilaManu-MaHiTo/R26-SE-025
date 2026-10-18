"""Re-exports for backward compatibility. Prefer importing from app.schemas.student / exam_analytics directly."""

from app.schemas.catalog import CriteriaEvidence, QuestionAttempt, QuestionCatalog, TopicAssignment

__all__ = ["CriteriaEvidence", "QuestionAttempt", "QuestionCatalog", "TopicAssignment"]