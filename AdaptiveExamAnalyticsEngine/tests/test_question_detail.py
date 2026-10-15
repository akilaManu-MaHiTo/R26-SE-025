import httpx
import pytest
from bson import ObjectId

from app.api import deps
from app.main import app


class Collection:
    def __init__(self, documents):
        self.documents = documents

    async def find_one(self, query):
        return next((d for d in self.documents if all(d.get(k) == v for k, v in query.items())), None)

    def find(self, query):
        documents = [d for d in self.documents if all(d.get(k) == v for k, v in query.items())]

        class Cursor:
            async def to_list(self, length=None):
                return documents

        return Cursor()


IDENTITY = dict(subject_code="IT2040", session_name="Final Examination", year=2022, month=7, semester=1)
URL = "/api/lecturers/exams/IT2040/Final%20Examination/questions/1?year=2022&month=7&semester=1"


@pytest.fixture
def database():
    def submission(student, score, **extra):
        return {**IDENTITY, "student_id": student, "status": "graded", "evaluation": {"results": [
            {"q_no": "01", "score": score, **extra},
            {"q_no": "02", "score": 99, "answer_excerpt": "Other question"},
        ]}}

    db = {
        "rubricCollection": Collection([{**IDENTITY, "questions": [
            {"question_no": "01", "question_text": "Explain normalization.", "criteria": [{"point": "Definition", "marks": 5}, {"point": "Example", "marks": 5}]},
            {"question_no": "02", "question_text": "Other question", "max_marks": 100},
        ]}]),
        "submissions": Collection([
            submission("S1", 0, answer_excerpt="", slice_source="empty"),
            submission("S2", 5, answer_excerpt="My answer", slice_source="split", feedback="Add an example."),
            submission("S3", 5),
            submission("S4", 10, answer_excerpt="Full transcript excerpt", slice_source="full"),
            {**submission("Other exam", 9), "month": 8},
            {**submission("Pending", 8), "status": "pending"},
        ]),
    }
    async def get_database():
        return db

    app.dependency_overrides[deps.get_db] = get_database
    yield db
    app.dependency_overrides.pop(deps.get_db, None)


async def get_detail(url=URL):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(url)


async def test_question_detail_joins_exact_exam_and_normalizes_question_number(database):
    response = await get_detail()
    assert response.status_code == 200
    detail = response.json()
    assert detail["question_no"] == "01"
    assert detail["question_text"] == "Explain normalization."
    assert detail["max_marks"] == 10
    assert detail["mark_distribution"] == [{"marks": 0, "count": 1}, {"marks": 5, "count": 2}, {"marks": 10, "count": 1}]
    assert [r["student_id"] for r in detail["responses"]] == ["S1", "S2", "S3", "S4"]
    assert detail["responses"][1]["answer_excerpt"] == "My answer"
    assert detail["responses"][1]["feedback"] == "Add an example."
    assert detail["responses"][2]["answer_excerpt"] is None
    assert detail["responses"][3]["slice_source"] == "full"


async def test_question_text_available_without_submissions(database):
    database["submissions"].documents.clear()
    response = await get_detail()
    assert response.status_code == 200
    assert response.json()["question_text"] == "Explain normalization."
    assert response.json()["responses"] == []
    assert response.json()["mark_distribution"] == []


async def test_unknown_question_and_session_return_404(database):
    assert (await get_detail(URL.replace("questions/1?", "questions/99?"))).status_code == 404
    assert (await get_detail(URL.replace("month=7", "month=9"))).status_code == 404


async def test_full_exam_identity_required(database):
    assert (await get_detail(URL.split("?")[0])).status_code == 422


async def test_invalid_scores_are_excluded_without_becoming_zero(database):
    database["submissions"].documents.extend([
        {**IDENTITY, "student_id": "Invalid", "status": "graded", "results": [{"q_no": "1", "score": score}]}
        for score in [None, "bad", -1, 11, "NaN", "Infinity"]
    ])
    response = await get_detail()
    assert response.status_code == 200
    assert response.json()["excluded_count"] == 6
    assert len(response.json()["responses"]) == 4


async def test_legacy_results_and_fractional_marks(database):
    database["submissions"].documents = [{**IDENTITY, "student_id": "Legacy", "status": "graded", "results": [
        {"question_no": "1", "score": 2.5, "answer_excerpt": "Legacy excerpt"},
    ]}]
    response = await get_detail()
    assert response.status_code == 200
    assert response.json()["mark_distribution"] == [{"marks": 2.5, "count": 1}]


async def test_archived_grades_do_not_duplicate_current_responses(database):
    database["submissions"].documents.append({
        **database["submissions"].documents[1], "archived_at": "2026-10-12T00:00:00Z",
    })
    response = await get_detail()
    assert response.status_code == 200
    assert len(response.json()["responses"]) == 4
    assert response.json()["mark_distribution"][1] == {"marks": 5, "count": 2}


async def test_question_uses_the_rubric_referenced_by_graded_submissions(database):
    rubric = database["rubricCollection"].documents[0]
    rubric["_id"] = "active-rubric"
    database["rubricCollection"].documents.insert(0, {
        **IDENTITY, "_id": "old-rubric", "questions": [
            {"question_no": "01", "question_text": "Old question", "max_marks": 2},
        ],
    })
    for submission in database["submissions"].documents:
        submission["rubric_ref"] = "active-rubric"
    response = await get_detail()
    assert response.status_code == 200
    assert response.json()["question_text"] == "Explain normalization."
    assert response.json()["max_marks"] == 10
    assert len(response.json()["responses"]) == 4


async def test_mixed_active_rubric_versions_are_not_combined(database):
    database["submissions"].documents[0]["rubric_ref"] = "rubric-a"
    database["submissions"].documents[1]["rubric_ref"] = "rubric-b"
    response = await get_detail()
    assert response.status_code == 409
    assert "rubric" in response.json()["detail"].lower()


async def test_string_rubric_reference_matches_mongodb_object_id(database):
    rubric_id = ObjectId("6c1149ab7d0e5c1a3f2b8d40")
    database["rubricCollection"].documents[0]["_id"] = rubric_id
    for submission in database["submissions"].documents:
        submission["rubric_ref"] = str(rubric_id)
    response = await get_detail()
    assert response.status_code == 200
    assert response.json()["question_text"] == "Explain normalization."
    assert len(response.json()["responses"]) == 4


async def test_missing_excerpt_is_recovered_from_selected_ocr_question(database):
    submission = database["submissions"].documents[2]
    submission["raw_ocr_transcript"] = "Student ID: S3\r\nQ1\r\nMy normalization answer.\r\nQuestion 2\r\nOther answer."
    response = await get_detail()
    recovered = response.json()["responses"][2]
    assert recovered["answer_excerpt"] == "My normalization answer."
    assert recovered["slice_source"] == "ocr"


@pytest.mark.parametrize("transcript", ["Whole paper without question headings", "Q2\nOnly another question", "Q1\n\nQuestion 2\nOther answer"])
async def test_ocr_fallback_does_not_present_other_answers_as_selected_question(database, transcript):
    database["submissions"].documents[2]["raw_ocr_transcript"] = transcript
    response = await get_detail()
    assert response.json()["responses"][2]["answer_excerpt"] is None


async def test_saved_excerpt_takes_precedence_over_ocr_fallback(database):
    database["submissions"].documents[1]["raw_ocr_transcript"] = "Q1\nDifferent OCR text"
    response = await get_detail()
    assert response.json()["responses"][1]["answer_excerpt"] == "My answer"


async def test_ocr_fallback_limits_excerpt_length(database):
    database["submissions"].documents[2]["raw_ocr_transcript"] = "Question 01:\n" + "a" * 1500 + "\nQ2\nOther answer"
    response = await get_detail()
    assert response.json()["responses"][2]["answer_excerpt"] == "a" * 1200
