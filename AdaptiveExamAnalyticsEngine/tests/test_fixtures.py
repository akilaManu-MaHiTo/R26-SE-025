from tests.fixtures.fixture_data import expected_attempt_records, sample_papers, sample_submissions


def test_fixtures_have_two_papers():
    assert len(sample_papers) == 2


def test_fixtures_have_students_across_two_papers():
    exams = {s["exam_id"] for s in sample_submissions}
    assert exams == {"exam-2023", "exam-2024"}


def test_expected_attempt_records_sum_to_known_values():
    total_marks = sum(r["max_marks"] for r in expected_attempt_records)
    assert total_marks > 0
    assert all(0.0 <= r["normalized_score"] <= 1.0 for r in expected_attempt_records)