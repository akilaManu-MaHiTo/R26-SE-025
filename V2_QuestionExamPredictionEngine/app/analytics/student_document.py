"""Pure, deterministic calculations for the student analytics document."""

from collections.abc import Iterable

from pydantic import BaseModel

from app.ingestion.student_data import NormalizedStudentInput
from app.llm.roles.student_analysis import QuestionSemantics
from app.schemas.student import (
    AssessmentInfo,
    BloomAnalysis,
    BloomLevel,
    BloomPerformance,
    CriterionPerformance,
    LearningAnalysis,
    NextQuestionGeneration,
    Performance,
    PerformanceStatus,
    QuestionAnalysis,
    Recommendation,
    TopicPerformance,
)

STRONG_THRESHOLD = 75.0
IMPROVEMENT_THRESHOLD = 50.0


class NumericStudentAnalysis(BaseModel):
    """Backend-owned numeric analysis plus deterministic semantic fallbacks."""

    assessment: AssessmentInfo
    question_analysis: list[QuestionAnalysis]
    topic_performance: list[TopicPerformance]
    bloom_performance: list[BloomPerformance]
    learning_analysis: LearningAnalysis
    recommendations: list[Recommendation]
    next_question_generation: NextQuestionGeneration

    def evidence(self) -> dict:
        """Return compact backend evidence suitable for the LLM insight prompt.

        Rule-computed summaries and verbose per-question records are excluded:
        their keys collide with the insight output schema, which causes models
        to echo them. A flat topic/bloom summary plus the list of lost criteria
        lets the model derive qualitative insights instead.
        """
        return {
            "assessment": {
                "session_name": self.assessment.session_name,
                "percentage": self.assessment.percentage,
            },
            "topic_performance": [
                {
                    "topic": topic.topic,
                    "percentage": topic.percentage,
                    "status": topic.status,
                }
                for topic in self.topic_performance
            ],
            "bloom_performance": [
                {
                    "level": level.level,
                    "average_score": level.average_score,
                    "status": level.status,
                }
                for level in self.bloom_performance
            ],
            "weak_criteria": [
                {
                    "topic": question.topic,
                    "criterion": criterion.criterion,
                }
                for question in self.question_analysis
                for criterion in question.criteria_performance
                if criterion.awarded_marks < criterion.max_marks
            ],
        }


def percentage(score: float, max_score: float) -> float:
    if max_score <= 0:
        raise ValueError("max_score must be positive")
    return round(score / max_score * 100.0, 2)


def performance_status(value: float) -> PerformanceStatus:
    if value >= STRONG_THRESHOLD:
        return "Strong"
    if value >= IMPROVEMENT_THRESHOLD:
        return "Needs Improvement"
    return "Critical"


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _question_analysis(
    normalized: NormalizedStudentInput,
    semantics_by_question: dict[str, QuestionSemantics],
) -> list[QuestionAnalysis]:
    records: list[QuestionAnalysis] = []
    for question in sorted(normalized.questions, key=lambda item: item.question_no):
        try:
            semantics = semantics_by_question[question.question_no]
        except KeyError as exc:
            raise ValueError(
                f"missing semantics for question {question.question_no}"
            ) from exc
        records.append(
            QuestionAnalysis(
                question_no=question.question_no,
                question=question.question_text,
                topic=semantics.topic,
                subtopic=semantics.subtopic,
                bloom_analysis=BloomAnalysis(
                    level=semantics.level,
                    confidence=semantics.confidence,
                    reason=semantics.reason,
                ),
                performance=Performance(
                    score=question.score,
                    max_score=question.max_score,
                    percentage=percentage(question.score, question.max_score),
                ),
                criteria_performance=[
                    CriterionPerformance(
                        criterion=criterion.criterion,
                        max_marks=criterion.max_marks,
                        awarded_marks=criterion.awarded_marks,
                        achieved=criterion.awarded_marks > 0,
                    )
                    for criterion in question.criteria
                ],
            )
        )
    return records


def _topic_performance(questions: list[QuestionAnalysis]) -> list[TopicPerformance]:
    grouped: dict[str, list[QuestionAnalysis]] = {}
    for question in questions:
        grouped.setdefault(question.topic, []).append(question)

    records: list[TopicPerformance] = []
    for topic, members in grouped.items():
        score = sum(item.performance.score for item in members)
        max_score = sum(item.performance.max_score for item in members)
        value = percentage(score, max_score)
        records.append(
            TopicPerformance(
                topic=topic,
                questions_attempted=len(members),
                score=round(score, 2),
                max_score=round(max_score, 2),
                percentage=value,
                status=performance_status(value),
            )
        )
    return records


def _bloom_performance(questions: list[QuestionAnalysis]) -> list[BloomPerformance]:
    grouped: dict[BloomLevel, list[QuestionAnalysis]] = {}
    for question in questions:
        grouped.setdefault(question.bloom_analysis.level, []).append(question)

    records: list[BloomPerformance] = []
    for level, members in grouped.items():
        score = sum(item.performance.score for item in members)
        max_score = sum(item.performance.max_score for item in members)
        value = percentage(score, max_score)
        records.append(
            BloomPerformance(
                level=level,
                questions_attempted=len(members),
                average_score=value,
                status=performance_status(value),
            )
        )
    return records


def fallback_learning_gaps(questions: list[QuestionAnalysis]) -> list[str]:
    """Describe missed criteria, falling back to the weak question's subtopic."""
    gaps: list[str] = []
    for question in questions:
        missed = [
            criterion
            for criterion in question.criteria_performance
            if criterion.awarded_marks < criterion.max_marks
        ]
        if missed:
            gaps.extend(
                f"Review {criterion.criterion} in {question.subtopic}."
                for criterion in missed
            )
        elif performance_status(question.performance.percentage) != "Strong":
            gaps.append(f"Review {question.subtopic}.")
    return _unique(gaps)


def fallback_recommendations(
    topics: list[TopicPerformance], blooms: list[BloomPerformance]
) -> list[Recommendation]:
    weak_topics = [topic for topic in topics if topic.status != "Strong"]
    if not weak_topics:
        return []
    weakest_bloom = min(blooms, key=lambda bloom: bloom.average_score)
    return [
        Recommendation(
            priority="High",
            topic=topic.topic,
            bloom_level=weakest_bloom.level,
            action=f"Review {topic.topic} and practice {weakest_bloom.level} questions.",
        )
        for topic in weak_topics
    ]


def fallback_generation_target(
    topics: list[TopicPerformance], blooms: list[BloomPerformance]
) -> NextQuestionGeneration:
    if not topics or not blooms:
        raise ValueError("topic and Bloom performance are required")
    weakest_bloom = min(blooms, key=lambda bloom: bloom.average_score)
    weak_topics = [topic.topic for topic in topics if topic.status != "Strong"]
    recommended_topics = weak_topics or [min(topics, key=lambda topic: topic.percentage).topic]
    difficulty = {
        "Critical": "Easy",
        "Needs Improvement": "Medium",
        "Strong": "Hard",
    }[weakest_bloom.status]
    return NextQuestionGeneration(
        recommended_bloom_level=weakest_bloom.level,
        recommended_difficulty=difficulty,
        recommended_topics=recommended_topics,
        number_of_questions=5,
    )


def build_numeric_analysis(
    normalized: NormalizedStudentInput,
    semantics_by_question: dict[str, QuestionSemantics],
) -> NumericStudentAnalysis:
    """Build all numeric fields solely from normalized grading evidence."""
    questions = _question_analysis(normalized, semantics_by_question)
    total_score = sum(question.performance.score for question in questions)
    max_score = sum(question.performance.max_score for question in questions)
    overall_percentage = percentage(total_score, max_score)
    topics = _topic_performance(questions)
    blooms = _bloom_performance(questions)

    weak_topics = [topic.topic for topic in topics if topic.status != "Strong"]
    strong_topics = [topic.topic for topic in topics if topic.status == "Strong"]
    weak_blooms = [bloom.level for bloom in blooms if bloom.status != "Strong"]
    weak_subtopics = _unique(
        question.subtopic
        for question in questions
        if performance_status(question.performance.percentage) != "Strong"
    )
    learning_gaps = fallback_learning_gaps(questions)

    return NumericStudentAnalysis(
        assessment=AssessmentInfo(
            session_name=normalized.session_name,
            rubric_ref=normalized.rubric_ref,
            total_score=round(total_score, 2),
            max_score=round(max_score, 2),
            percentage=overall_percentage,
        ),
        question_analysis=questions,
        topic_performance=topics,
        bloom_performance=blooms,
        learning_analysis=LearningAnalysis(
            overall_performance=performance_status(overall_percentage),
            weak_topics=weak_topics,
            strong_topics=strong_topics,
            weak_bloom_levels=weak_blooms,
            weak_subtopics=weak_subtopics,
            learning_gaps=learning_gaps,
        ),
        recommendations=fallback_recommendations(topics, blooms),
        next_question_generation=fallback_generation_target(topics, blooms),
    )
