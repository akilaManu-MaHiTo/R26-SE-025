import pytest

from app.analytics.student_document import (
    build_numeric_analysis,
    fallback_generation_target,
    fallback_learning_gaps,
    fallback_recommendations,
    performance_status,
)
from app.ingestion.student_data import (
    NormalizedCriterion,
    NormalizedQuestionInput,
    NormalizedStudentInput,
)
from app.llm.roles.student_analysis import QuestionSemantics


def two_question_input(
    first: tuple[float, float] = (3.0, 5.0),
    second: tuple[float, float] = (1.0, 5.0),
    *,
    reverse: bool = False,
) -> NormalizedStudentInput:
    questions = [
        NormalizedQuestionInput(
            question_no="01",
            question_text="Apply two-phase locking.",
            score=first[0],
            max_score=first[1],
            criteria=[
                NormalizedCriterion(
                    criterion="Identifies the growing phase",
                    awarded_marks=1.0,
                    max_marks=2.0,
                ),
                NormalizedCriterion(
                    criterion="Applies the shrinking phase",
                    awarded_marks=2.0,
                    max_marks=3.0,
                ),
            ],
        ),
        NormalizedQuestionInput(
            question_no="02",
            question_text="Resolve a deadlock.",
            score=second[0],
            max_score=second[1],
            criteria=[
                NormalizedCriterion(
                    criterion="Builds the wait-for graph",
                    awarded_marks=0.0,
                    max_marks=4.0,
                ),
                NormalizedCriterion(
                    criterion="Selects a victim",
                    awarded_marks=1.0,
                    max_marks=1.0,
                ),
            ],
        ),
    ]
    return NormalizedStudentInput(
        student_id="IT22145976",
        course_code="IT2040",
        course_name="Database Management Systems",
        session_name="Final Examination",
        rubric_ref="rubric-1",
        questions=list(reversed(questions)) if reverse else questions,
    )


def semantics() -> dict[str, QuestionSemantics]:
    return {
        "01": QuestionSemantics(
            level="Apply",
            topic="Transaction Management",
            subtopic="Two-Phase Locking",
            confidence=0.92,
            reason="The question asks the student to apply a locking protocol.",
        ),
        "02": QuestionSemantics(
            level="Apply",
            topic="Transaction Management",
            subtopic="Deadlocks",
            confidence=0.88,
            reason="The question asks the student to resolve a deadlock.",
        ),
    }


def test_numeric_analysis_recalculates_totals_and_weighted_groups():
    normalized = two_question_input(first=(3.0, 5.0), second=(1.0, 5.0))

    analysis = build_numeric_analysis(normalized, semantics())

    assert analysis.assessment.total_score == 4.0
    assert analysis.assessment.max_score == 10.0
    assert analysis.assessment.percentage == 40.0
    assert analysis.topic_performance[0].score == 4.0
    assert analysis.topic_performance[0].max_score == 10.0
    assert analysis.topic_performance[0].percentage == 40.0
    assert analysis.bloom_performance[0].average_score == 40.0


def test_numeric_evidence_excludes_rule_computed_summaries():
    normalized = two_question_input(first=(3.0, 5.0), second=(1.0, 5.0))

    evidence = build_numeric_analysis(normalized, semantics()).evidence()

    assert "assessment" in evidence
    assert "topic_performance" in evidence
    assert "bloom_performance" in evidence
    assert "weak_criteria" in evidence
    assert "question_analysis" not in evidence
    assert "learning_analysis" not in evidence
    assert "recommendations" not in evidence
    assert "next_question_generation" not in evidence


def test_numeric_evidence_lists_only_lost_criteria():
    normalized = two_question_input(first=(3.0, 5.0), second=(5.0, 5.0))
    evidence = build_numeric_analysis(normalized, semantics()).evidence()

    assert any(
        item["criterion"] == "Identifies the growing phase"
        for item in evidence["weak_criteria"]
    )
    assert all(
        item["criterion"] != "Selects a victim"
        for item in evidence["weak_criteria"]
    )


def test_group_percentages_are_weighted_by_maximum_marks():
    normalized = two_question_input(first=(5.0, 5.0), second=(1.0, 5.0))
    normalized.questions[1].max_score = 15.0
    normalized.questions[1].criteria = [
        NormalizedCriterion(
            criterion="Builds the wait-for graph",
            awarded_marks=1.0,
            max_marks=15.0,
        )
    ]

    analysis = build_numeric_analysis(normalized, semantics())

    assert analysis.assessment.percentage == 30.0
    assert analysis.topic_performance[0].percentage == 30.0
    assert analysis.bloom_performance[0].average_score == 30.0


@pytest.mark.parametrize(
    ("percentage", "expected"),
    [
        (49.99, "Critical"),
        (50.0, "Needs Improvement"),
        (74.99, "Needs Improvement"),
        (75.0, "Strong"),
    ],
)
def test_performance_status_boundaries(percentage, expected):
    assert performance_status(percentage) == expected


def test_partial_criterion_marks_count_as_achieved():
    analysis = build_numeric_analysis(two_question_input(), semantics())

    criterion = analysis.question_analysis[0].criteria_performance[0]

    assert criterion.awarded_marks == 1.0
    assert criterion.max_marks == 2.0
    assert criterion.achieved is True


def test_question_output_is_sorted_and_weak_lists_preserve_first_appearance():
    analysis = build_numeric_analysis(two_question_input(reverse=True), semantics())

    assert [item.question_no for item in analysis.question_analysis] == ["01", "02"]
    assert analysis.learning_analysis.weak_topics == ["Transaction Management"]
    assert analysis.learning_analysis.weak_bloom_levels == ["Apply"]
    assert analysis.learning_analysis.weak_subtopics == [
        "Two-Phase Locking",
        "Deadlocks",
    ]
    assert analysis.learning_analysis.strong_topics == []


def test_strong_topics_are_not_reported_as_weak():
    normalized = two_question_input(first=(5.0, 5.0), second=(5.0, 5.0))
    for question in normalized.questions:
        question.criteria = [
            NormalizedCriterion(
                criterion="Complete answer",
                awarded_marks=5.0,
                max_marks=5.0,
            )
        ]

    analysis = build_numeric_analysis(normalized, semantics())

    assert analysis.learning_analysis.strong_topics == ["Transaction Management"]
    assert analysis.learning_analysis.weak_topics == []
    assert analysis.learning_analysis.weak_bloom_levels == []
    assert analysis.learning_analysis.weak_subtopics == []


def test_fallbacks_use_missed_criteria_high_priority_and_five_questions():
    analysis = build_numeric_analysis(two_question_input(), semantics())

    gaps = fallback_learning_gaps(analysis.question_analysis)
    recommendations = fallback_recommendations(
        analysis.topic_performance, analysis.bloom_performance
    )
    generation_target = fallback_generation_target(
        analysis.topic_performance, analysis.bloom_performance
    )

    assert gaps == [
        "Review Identifies the growing phase in Two-Phase Locking.",
        "Review Applies the shrinking phase in Two-Phase Locking.",
        "Review Builds the wait-for graph in Deadlocks.",
    ]
    assert recommendations[0].priority == "High"
    assert recommendations[0].topic == "Transaction Management"
    assert recommendations[0].bloom_level == "Apply"
    assert generation_target.number_of_questions == 5
    assert generation_target.recommended_topics == ["Transaction Management"]


def test_fallback_gap_uses_subtopic_when_no_criterion_was_missed():
    normalized = two_question_input(first=(3.0, 5.0), second=(5.0, 5.0))
    normalized.questions[0].criteria = [
        NormalizedCriterion(
            criterion="Complete rubric criterion",
            awarded_marks=5.0,
            max_marks=5.0,
        )
    ]
    normalized.questions[1].criteria = [
        NormalizedCriterion(
            criterion="Complete rubric criterion",
            awarded_marks=5.0,
            max_marks=5.0,
        )
    ]

    analysis = build_numeric_analysis(normalized, semantics())

    assert fallback_learning_gaps(analysis.question_analysis) == [
        "Review Two-Phase Locking."
    ]


def test_aggregation_rounds_only_after_summing_source_marks():
    normalized = two_question_input(first=(0.004, 1.0), second=(0.004, 1.0))

    analysis = build_numeric_analysis(normalized, semantics())

    assert analysis.assessment.total_score == 0.01
    assert analysis.assessment.max_score == 2.0
    assert analysis.assessment.percentage == 0.4
    assert analysis.topic_performance[0].score == 0.01
    assert analysis.topic_performance[0].percentage == 0.4
    assert analysis.bloom_performance[0].average_score == 0.4


def test_fallback_gap_keeps_missed_criterion_from_strong_question():
    normalized = two_question_input(first=(4.0, 5.0), second=(5.0, 5.0))
    normalized.questions[1].criteria = [
        NormalizedCriterion(
            criterion="Complete rubric criterion",
            awarded_marks=5.0,
            max_marks=5.0,
        )
    ]

    analysis = build_numeric_analysis(normalized, semantics())

    assert analysis.question_analysis[0].performance.percentage == 80.0
    assert fallback_learning_gaps(analysis.question_analysis) == [
        "Review Identifies the growing phase in Two-Phase Locking.",
        "Review Applies the shrinking phase in Two-Phase Locking.",
    ]
