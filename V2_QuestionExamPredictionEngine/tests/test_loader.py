from app.sample_data.loader import _load, load_real, parse_submission


def test_parse_submission_reads_awarded_marks_and_rubric_maxima():
    rubric = _load("rubricCollection.json")
    sub = _load("submission.json")
    rows = parse_submission(
        sub, "IT2040-final-examination-2021", "IT2040", rubric["questions"]
    )
    q01 = next(row for row in rows if row["question_number"] == "01")
    assert q01["awarded_marks"] == 6.0
    assert q01["max_marks"] == 8.0
    first = q01["criteria_breakdown"][0]
    assert first["awarded_marks"] == 2.5
    assert first["max_marks"] == 3.0
    assert first["met"] is False


def test_load_real_builds_course_from_courses_json():
    course, papers, submissions = load_real()
    assert course["course_code"] == "IT2040"
    assert course["course_name"] == "Database Management Systems"
    assert len(papers) == 1
    assert papers[0]["year"] == 2021
    assert len(submissions) >= 5
    assert all(row["max_marks"] > 0 for row in submissions)
