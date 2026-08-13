from app.sample_data.loader import _load, load_real, parse_submission


def test_parse_submission_reads_awarded_marks_and_rubric_maxima():
    rubric = _load("rubricCollection/rubricCollection.json")
    sub = _load("submissions/submission.json")[0]
    rows = parse_submission(
        sub, "IT2040-Final Examination", "IT2040", rubric["questions"]
    )
    q01 = next(row for row in rows if row["question_number"] == "01")
    assert q01["awarded_marks"] == 11.0
    assert q01["max_marks"] == 20.0
    first = q01["criteria_breakdown"][0]
    assert first["awarded_marks"] == 2.0
    assert first["max_marks"] == 4.0
    assert first["met"] is False


def test_load_real_builds_course_from_courses_json():
    course, papers, submissions = load_real()
    assert course["course_code"] == "IT2040"
    assert course["course_name"] == "Database Management Systems"
    assert len(papers) == 1
    assert papers[0]["year"] == 2022
    assert len(submissions) >= 5
    assert all(row["max_marks"] > 0 for row in submissions)
