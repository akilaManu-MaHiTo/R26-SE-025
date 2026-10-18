from app.llm.roles.study_actions import StudyAction, StudyActions


def test_study_actions_shape():
    result = StudyActions(
        student_key="stu-001",
        actions=[StudyAction(action="review", topic="SQL", rationale="r", practice_topics=["joins"])],
    )
    assert result.bounded_language is True
