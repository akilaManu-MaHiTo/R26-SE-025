"""Pure, deterministic calculations for the student analytics document."""

from pydantic import BaseModel

from app.ingestion.student_data import NormalizedStudentInput
from app.llm.roles.student_analysis import QuestionSemantics
from app.schemas.student import (
    BloomAnalysis,
    BloomLevel,
    BloomPerformance,
    CriterionPerformance,
    LearningAnalysis,
    LearningGap,
    NextQuestionStrategy,
    OverallPerformance,
    Performance,
    PerformanceStatus,
    QuestionPerformance,
    Recommendation,
    TopicPerformance,
)

STRONG_THRESHOLD = 80.0
DEVELOPING_THRESHOLD = 60.0
IMPROVEMENT_THRESHOLD = 40.0

_PRIORITY_BY_STATUS = {
    "Critical": "Critical",
    "Needs Improvement": "High",
    "Developing": "Medium",
    "Strong": "Low",
}


class NumericStudentAnalysis(BaseModel):
    """Backend-owned numeric analysis plus deterministic semantic fallbacks."""

    overall_performance: OverallPerformance
    question_performance: list[QuestionPerformance]
    topic_performance: list[TopicPerformance]
    bloom_performance: list[BloomPerformance]
    learning_analysis: LearningAnalysis
    recommendations: list[Recommendation]
    next_question_strategy: NextQuestionStrategy

    def evidence(self) -> dict:
        """Return compact backend evidence suitable for the LLM insight prompt.

        Rule-computed summaries and verbose per-question records are excluded:
        their keys collide with the insight output schema, which causes models
        to echo them. A flat topic/bloom summary plus the list of lost criteria
        lets the model derive qualitative insights instead.
        """
        return {
            "assessment": {
                "percentage": self.overall_performance.percentage,
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
                for question in self.question_performance
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
    if value >= DEVELOPING_THRESHOLD:
        return "Developing"
    if value >= IMPROVEMENT_THRESHOLD:
        return "Needs Improvement"
    return "Critical"


def _question_analysis(
    normalized: NormalizedStudentInput,
    semantics_by_question: dict[str, QuestionSemantics],
) -> list[QuestionPerformance]:
    records: list[QuestionPerformance] = []
    for question in sorted(normalized.questions, key=lambda item: item.question_no):
        try:
            semantics = semantics_by_question[question.question_no]
        except KeyError as exc:
            raise ValueError(
                f"missing semantics for question {question.question_no}"
            ) from exc
        records.append(
            QuestionPerformance(
                question_id=f"Q{question.question_no}",
                question_no=question.question_no,
                question_text=question.question_text,
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


def _topic_performance(
    questions: list[QuestionPerformance],
) -> list[TopicPerformance]:
    grouped: dict[str, list[QuestionPerformance]] = {}
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


def _bloom_performance(
    questions: list[QuestionPerformance],
) -> list[BloomPerformance]:
    grouped: dict[BloomLevel, list[QuestionPerformance]] = {}
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


def fallback_learning_gaps(
    questions: list[QuestionPerformance],
) -> list[LearningGap]:
    seen: set[tuple[str, str]] = set()
    gaps: list[LearningGap] = []
    for question in questions:
        missed = [
            criterion
            for criterion in question.criteria_performance
            if criterion.awarded_marks < criterion.max_marks
        ]
        priority = _PRIORITY_BY_STATUS[performance_status(question.performance.percentage)]
        for criterion in missed:
            key = (question.topic, criterion.criterion)
            if key in seen:
                continue
            seen.add(key)
            gaps.append(
                LearningGap(
                    topic=question.topic,
                    subtopic=criterion.criterion,
                    priority=priority,
                )
            )
        if not missed and priority != "Low":
            key = (question.topic, question.subtopic)
            if key in seen:
                continue
            seen.add(key)
            gaps.append(
                LearningGap(
                    topic=question.topic,
                    subtopic=question.subtopic,
                    priority=priority,
                )
            )
    return gaps


def weakest_bloom(
    _topic: TopicPerformance, blooms: list[BloomPerformance]
) -> str:
    return min(blooms, key=lambda bloom: bloom.average_score).level


def fallback_recommendations(
    topics: list[TopicPerformance], blooms: list[BloomPerformance]
) -> list[Recommendation]:
    weak_topics = [topic for topic in topics if topic.status != "Strong"]
    if not weak_topics:
        return []
    return [
        Recommendation(
            topic=topic.topic,
            priority=_PRIORITY_BY_STATUS[topic.status],
            action=f"Review {topic.topic} and practice {weakest_bloom(topic, blooms)} questions.",
        )
        for topic in weak_topics
    ]


def fallback_generation_target(
    topics: list[TopicPerformance], blooms: list[BloomPerformance]
) -> NextQuestionStrategy:
    if not topics or not blooms:
        raise ValueError("topic and Bloom performance are required")
    weakest = min(blooms, key=lambda bloom: bloom.average_score)
    weak_topics = [topic.topic for topic in topics if topic.status != "Strong"]
    recommended_topics = weak_topics or [
        min(topics, key=lambda topic: topic.percentage).topic
    ]
    recommended_bloom_levels = [weakest.level] + [
        bloom.level
        for bloom in blooms
        if bloom.level != weakest.level and bloom.status != "Strong"
    ]
    difficulty = {
        "Critical": "Easy",
        "Needs Improvement": "Medium",
        "Developing": "Medium",
        "Strong": "Hard",
    }[weakest.status]
    return NextQuestionStrategy(
        recommended_topics=recommended_topics,
        recommended_bloom_levels=recommended_bloom_levels,
        recommended_difficulty=difficulty,
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

    strong_topics = [topic.topic for topic in topics if topic.status == "Strong"]
    developing_topics = [
        topic.topic for topic in topics if topic.status == "Developing"
    ]
    weak_topics = [
        topic.topic
        for topic in topics
        if topic.status == "Needs Improvement"
    ]
    critical_topics = [
        topic.topic for topic in topics if topic.status == "Critical"
    ]

    return NumericStudentAnalysis(
        overall_performance=OverallPerformance(
            score=round(total_score, 2),
            maximum=round(max_score, 2),
            percentage=overall_percentage,
            status=performance_status(overall_percentage),
        ),
        question_performance=questions,
        topic_performance=topics,
        bloom_performance=blooms,
        learning_analysis=LearningAnalysis(
            overall_performance=performance_status(overall_percentage),
            strong_topics=strong_topics,
            developing_topics=developing_topics,
            weak_topics=weak_topics,
            critical_topics=critical_topics,
            learning_gaps=fallback_learning_gaps(questions),
        ),
        recommendations=fallback_recommendations(topics, blooms),
        next_question_strategy=fallback_generation_target(topics, blooms),
    )
