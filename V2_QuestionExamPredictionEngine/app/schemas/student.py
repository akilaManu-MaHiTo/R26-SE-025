from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MissedCriterion(BaseModel):
    criterion: str
    awarded_marks: float
    max_marks: float


class QuestionPerformance(BaseModel):
    question_id: str
    question_number: str
    part: str
    question_text: str
    topic: str
    bloom_level: str
    question_type: str
    awarded_marks: float
    max_marks: float
    normalized_score: float
    passed: bool
    feedback: str
    missed_criteria: list[MissedCriterion] = []


class StudentExamPerformance(BaseModel):
    exam_id: str
    total_awarded: float
    total_max: float
    percentage: float
    grade: str
    attempt_count: int
    question_performances: list[QuestionPerformance] = []


class StudentBloomSkill(BaseModel):
    bloom_level: str
    mastery: float | None = None
    mean: float | None = None
    attempt_count: int = 0
    evidence_status: str = "insufficient_evidence"


class StudentTopicSkill(BaseModel):
    topic: str
    mastery: float | None = None
    mean: float | None = None
    attempt_count: int = 0
    evidence_status: str = "insufficient_evidence"
    rank: int = 0
    priority_score: float = 0.0


class StudentStudyAction(BaseModel):
    action: str
    topic: str
    rationale: str = ""
    practice_topics: list[str] = []
    source: Literal["llm", "deterministic"] = "deterministic"


class StudentDashboard(BaseModel):
    student_key: str
    course_code: str
    run_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    exams: list[StudentExamPerformance] = []
    bloom_skills: list[StudentBloomSkill] = []
    topic_skills: list[StudentTopicSkill] = []
    weakest_topics: list[str] = []
    cohort_comparison: dict = {}
    recommendations: list[StudentStudyAction] = []
