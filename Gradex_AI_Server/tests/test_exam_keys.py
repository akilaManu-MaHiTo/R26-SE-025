"""Exam key HTTP contract, with MongoDB replaced at the collection boundary."""
from unittest.mock import MagicMock, call

import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from Gradex_AI_Server.app import exam_keys
from Gradex_AI_Server.app import mongodb


EXAM = {
    "examKey": "EXAM-2025-S1-Apr",
    "subjectCode": "IT2040",
    "subjectName": "Database Management System",
    "examYear": 2025,
    "examSemester": 1,
    "examMonth": "April",
    "session": "Final",
    "examStructure": ["Essay", "Essay", "Essay", "Essay", "Diagram"],
}
CREATE_EXAM = {key: value for key, value in EXAM.items() if key != "examKey"}


@pytest.fixture
def system(monkeypatch):
    collection = MagicMock()
    monkeypatch.setattr(exam_keys, "get_exam_keys_collection", lambda: collection)
    app = FastAPI()

    @app.middleware("http")
    async def identity(request, call_next):
        role = request.headers.get("X-Test-Role")
        if role:
            request.state.user = {"role": role}
        return await call_next(request)

    app.include_router(exam_keys.router)
    return TestClient(app), collection


def test_create_preserves_schema_and_question_order(system):
    client, collection = system
    stored = []

    def insert(document):
        stored.append(document.copy())
        document["_id"] = ObjectId()

    collection.insert_one.side_effect = insert
    response = client.post("/api/exam-keys", json=CREATE_EXAM, headers={"X-Test-Role": "lecturer"})
    assert response.status_code == 201
    expected = {**CREATE_EXAM, "examKey": "EXAM-IT2040-2025-S1-Apr-FINAL"}
    assert response.json() == expected
    assert stored == [expected]
    assert collection.create_index.call_args_list == [
        call("examKey", unique=True),
        call([
            ("subjectCode", 1), ("examYear", 1), ("examMonth", 1),
            ("examSemester", 1), ("session", 1),
        ], unique=True),
    ]


@pytest.mark.parametrize("field,value", [
    ("subjectCode", ""), ("subjectName", "  "),
    ("examYear", 0), ("examSemester", 3), ("examMonth", "Apr"),
    ("session", "unknown"), ("examStructure", []), ("examStructure", [" "]),
])
def test_invalid_exam_is_not_written(system, field, value):
    client, collection = system
    response = client.post("/api/exam-keys", json={**CREATE_EXAM, field: value}, headers={"X-Test-Role": "lecturer"})
    assert response.status_code == 422
    collection.insert_one.assert_not_called()


@pytest.mark.parametrize("operation", ["create_index", "insert_one"])
def test_duplicates_return_conflict_without_overwriting(system, operation):
    client, collection = system
    getattr(collection, operation).side_effect = DuplicateKeyError("duplicate")
    response = client.post("/api/exam-keys", json=CREATE_EXAM, headers={"X-Test-Role": "lecturer"})
    assert response.status_code == 409
    collection.update_one.assert_not_called()


def test_list_saved_keys(system):
    client, collection = system
    collection.find.return_value.sort.return_value = [EXAM]
    response = client.get("/api/exam-keys", headers={"X-Test-Role": "lecturer"})
    assert response.status_code == 200
    assert response.json() == [EXAM]


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("role,status", [(None, 401), ("student", 403)])
def test_only_lecturers_can_manage_keys(system, method, role, status):
    client, collection = system
    kwargs = {"headers": {"X-Test-Role": role}} if role else {}
    if method == "post":
        kwargs["json"] = CREATE_EXAM
    assert getattr(client, method)("/api/exam-keys", **kwargs).status_code == status
    collection.insert_one.assert_not_called()
    collection.find.assert_not_called()


def test_database_failure_does_not_expose_connection_details(system):
    client, collection = system
    collection.insert_one.side_effect = PyMongoError("private connection details")
    response = client.post("/api/exam-keys", json=CREATE_EXAM, headers={"X-Test-Role": "lecturer"})
    assert response.status_code == 503
    assert "private" not in response.text


def test_lecturer_cannot_supply_an_exam_key(system):
    client, collection = system
    response = client.post("/api/exam-keys", json={**CREATE_EXAM, "examKey": "MANUAL-KEY"}, headers={"X-Test-Role": "lecturer"})
    assert response.status_code == 422
    collection.insert_one.assert_not_called()


@pytest.mark.parametrize("changes,expected", [
    ({"subjectCode": "CS3010"}, "EXAM-CS3010-2025-S1-Apr-FINAL"),
    ({"session": "Mid Term"}, "EXAM-IT2040-2025-S1-Apr-MIDTERM"),
    ({"examSemester": 2, "examMonth": "June"}, "EXAM-IT2040-2025-S2-Jun-FINAL"),
])
def test_generated_key_identifies_subject_date_and_session(system, changes, expected):
    client, _ = system
    response = client.post("/api/exam-keys", json={**CREATE_EXAM, **changes}, headers={"X-Test-Role": "lecturer"})
    assert response.status_code == 201
    assert response.json()["examKey"] == expected


def test_grading_lookup_uses_the_server_exam_key_configuration(monkeypatch):
    monkeypatch.setenv("MONGODB_URL", "mongodb://127.0.0.1:27018")
    monkeypatch.setenv("DATABASE_NAME", "grading")
    monkeypatch.setenv("EXAM_KEYS_DATABASE_NAME", "gradev5")
    client = MagicMock()
    client.get_default_database.return_value = MagicMock()
    client.get_default_database.return_value.find_one.return_value = None
    collection = client["gradev5"]["examkeys"]
    collection.find_one.return_value = EXAM
    factory = MagicMock(return_value=client)
    monkeypatch.setattr("pymongo.MongoClient", factory)
    mongodb.get_mongo_client.cache_clear()
    mongodb.get_exam_keys_collection.cache_clear()
    try:
        assert mongodb.get_exam_key("IT2040", 2025, "April", 1, "Final") == EXAM
        factory.assert_called_once_with("mongodb://127.0.0.1:27018")
        collection.find_one.assert_called_once_with({
            "subjectCode": "IT2040", "examYear": 2025, "examMonth": "April",
            "examSemester": 1, "session": "Final",
        }, {"_id": 0})
    finally:
        mongodb.get_mongo_client.cache_clear()
        mongodb.get_exam_keys_collection.cache_clear()
