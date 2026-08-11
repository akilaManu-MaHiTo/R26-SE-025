from run_sample import load_raw_sample_documents


def test_courses_have_v2_shape():
    courses, _, _ = load_raw_sample_documents()
    assert len(courses) == 1
    course = courses[0]
    assert course["code"] == "IT2040"
    assert course["name"]
    assert course["description"]


def test_rubric_has_v2_metadata():
    _, rubrics, _ = load_raw_sample_documents()
    rubric = rubrics[0]
    assert rubric["subject_code"] == "IT2040"
    assert rubric["subject_name"]
    assert rubric["year"] == 2021
    assert rubric["month"]
    assert rubric["semester"]
    assert rubric["session_name"]
    assert len(rubric["exam_roster"]) == 5


def test_submissions_have_v2_shape_and_graded_status():
    _, _, submissions = load_raw_sample_documents()
    assert len(submissions) == 5
    for sub in submissions:
        assert sub["status"] == "graded"
        assert sub["paper_key"]
        assert sub["subject_code"] == "IT2040"
        assert sub["subject_name"]
        assert sub["year"] == 2021
        assert sub["month"]
        assert sub["semester"]
        assert sub["session_name"]
        assert "lecturer_note" in sub
        for result in sub["evaluation"]["results"]:
            for criterion in result["criteria_breakdown"]:
                assert "earned" not in criterion
                assert "marks" not in criterion
                assert "awarded_marks" in criterion
                assert criterion["awarded_marks"] >= 0
                assert "reason" in criterion
