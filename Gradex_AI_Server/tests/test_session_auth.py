"""Offline HTTP tests: real middleware/routes, in-memory Mongo substitute."""
import copy
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from Gradex_AI_Server.app import session_auth as auth


class Collection:
    def __init__(self):
        self.docs = []

    async def create_index(self, *args, **kwargs):
        pass

    async def index_information(self):
        return {}

    async def find_one(self, query):
        return next((copy.deepcopy(d) for d in self.docs if self.matches(d, query)), None)

    @staticmethod
    def matches(doc, query):
        return all(doc.get(k) > v["$gt"] if isinstance(v, dict) else doc.get(k) == v for k, v in query.items())

    async def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))

    async def delete_one(self, query):
        self.docs = [d for d in self.docs if not self.matches(d, query)]

    async def delete_many(self, query):
        await self.delete_one(query)

    async def update_one(self, query, update, **kwargs):
        for doc in self.docs:
            if self.matches(doc, query):
                doc.update(update.get("$set", {}))
                for key, value in update.get("$inc", {}).items():
                    doc[key] = doc.get(key, 0) + value
                return SimpleNamespace(matched_count=1)
        if kwargs.get("upsert"):
            self.docs.append({**query, **update.get("$setOnInsert", {}), **update.get("$set", {}), **update.get("$inc", {})})
        return SimpleNamespace(matched_count=0)

    async def find_one_and_update(self, query, update, **kwargs):
        doc = next((d for d in self.docs if self.matches(d, query)), None)
        if doc is None:
            doc = {**query, **update.get("$setOnInsert", {})}
            self.docs.append(doc)
        for key, value in update.get("$inc", {}).items():
            doc[key] = doc.get(key, 0) + value
        return copy.deepcopy(doc)


@pytest.fixture
def system(monkeypatch):
    db = {name: Collection() for name in ("users", "auth_sessions", "auth_login_attempts")}
    for email, role, sid in [("teacher@example.edu", "lecturer", None), ("student@example.edu", "student", "IT001")]:
        db["users"].docs.append({"email": email, "role": role, "student_id": sid, "password_hash": auth.hash_password("UniquePassword123!")})
    original_get_db = auth.get_auth_db
    monkeypatch.setattr(auth, "get_auth_db", lambda: db)
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    app = FastAPI()
    app.dependency_overrides[original_get_db] = lambda: db
    auth.setup_auth(app)

    @app.get("/api/lecturers/exams")
    async def lecturer():
        return {"ok": True}

    @app.get("/api/students/{student_id}/profile")
    async def student(student_id: str):
        return {"student_id": student_id}

    @app.websocket("/api/viva-copilot/ws/test")
    async def socket(ws: WebSocket):
        await ws.accept()
        await ws.send_text("ok")
        await ws.close()

    grading = FastAPI()

    @grading.get("/submissions")
    async def submissions():
        return []

    app.mount("/api/grading", grading)
    return TestClient(app), db


def login(client, email="teacher@example.edu", password="UniquePassword123!"):
    return client.post("/api/auth/login", json={"email": email, "password": password}, headers={"Origin": "http://testserver"})


def test_login_restores_identity_and_logout_revokes_session(system):
    client, db = system
    response = login(client)
    assert response.status_code == 200
    assert response.json() == {"email": "teacher@example.edu", "role": "lecturer", "student_id": None}
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    token = client.cookies.get(auth.COOKIE_NAME)
    assert db["auth_sessions"].docs[0]["_id"] != token
    assert client.get("/api/auth/me").json()["role"] == "lecturer"
    assert client.get("/api/grading/submissions").status_code == 200
    assert client.post("/api/auth/logout", headers={"Origin": "http://testserver"}).status_code == 204
    client.cookies.set(auth.COOKIE_NAME, token)
    assert client.get("/api/auth/me").status_code == 401


def test_invalid_credentials_and_api_keys_cannot_authenticate(system):
    client, _ = system
    assert login(client, password="wrong").status_code == 401
    assert login(client, email="absent@example.edu").status_code == 401
    assert not client.cookies.get(auth.COOKIE_NAME)
    assert client.get("/api/lecturers/exams", headers={"X-API-Key": "anything"}).status_code == 401
    assert client.post("/api/students/login", json={"email": "student@example.edu", "password": "wrong"}).status_code != 200


def test_student_cannot_read_another_student_or_teaching_routes(system):
    client, _ = system
    assert login(client, "student@example.edu").status_code == 200
    assert client.get("/api/students/IT001/profile").status_code == 200
    for path in ("/api/students/IT002/profile", "/api/lecturers/exams", "/api/grading/submissions", "/api/analytics/exams", "/api/students/IT001/profile/extra"):
        assert client.get(path).status_code == 403


def test_expired_sessions_and_deleted_users_are_rejected(system):
    client, db = system
    login(client)
    db["auth_sessions"].docs[0]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert client.get("/api/auth/me").status_code == 401
    login(client)
    db["users"].docs.clear()
    assert client.get("/api/auth/me").status_code == 401


def test_csrf_and_login_throttling(system):
    client, _ = system
    for origin in (None, "https://evil.example"):
        headers = {"Origin": origin} if origin else {}
        assert client.post("/api/auth/login", json={"email": "teacher@example.edu", "password": "UniquePassword123!"}, headers=headers).status_code == 403
    for _ in range(auth.LOGIN_LIMIT):
        assert login(client, password="wrong").status_code == 401
    assert login(client).status_code == 429


def test_deployed_frontend_origin_is_trusted(system):
    client, _ = system
    response = client.post(
        "/api/auth/login",
        json={"email": "teacher@example.edu", "password": "UniquePassword123!"},
        headers={"Origin": "https://gradex-orpin.vercel.app"},
    )
    assert response.status_code == 200


def test_forwarded_https_scheme_is_used_for_same_host_origin(system):
    client, _ = system
    response = client.post(
        "/api/auth/login",
        json={"email": "teacher@example.edu", "password": "UniquePassword123!"},
        headers={
            "Origin": "https://testserver",
            "X-Forwarded-Proto": "https",
        },
    )
    assert response.status_code == 200


def test_database_failure_does_not_expose_details_or_allow_login(system, monkeypatch):
    from pymongo.errors import ServerSelectionTimeoutError
    client, db = system

    async def unavailable(query):
        raise ServerSelectionTimeoutError("private database connection details")

    monkeypatch.setattr(db["users"], "find_one", unavailable)
    response = login(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert not client.cookies.get(auth.COOKIE_NAME)


def test_websocket_requires_lecturer_session_and_trusted_origin(system):
    client, _ = system
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/viva-copilot/ws/test", headers={"Origin": "http://testserver"}):
            pass
    login(client)
    with client.websocket_connect("/api/viva-copilot/ws/test", headers={"Origin": "http://testserver"}) as ws:
        assert ws.receive_text() == "ok"
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/viva-copilot/ws/test", headers={"Origin": "https://evil.example"}):
            pass


def test_shared_demo_password_is_rejected(system):
    import hashlib
    client, db = system
    salt = b"legacy-salt"
    digest = hashlib.pbkdf2_hmac("sha256", b"Student@123", salt, 100000).hex()
    db["users"].docs[1]["password_hash"] = f"pbkdf2_sha256$100000${salt.hex()}${digest}"
    assert login(client, "student@example.edu", "Student@123").status_code == 401


def test_secure_cookie_in_production(system, monkeypatch):
    client, _ = system
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    assert "secure" in login(client).headers["set-cookie"].lower()


def test_provision_and_password_reset_revoke_old_sessions(system, monkeypatch):
    import asyncio
    from Gradex_AI_Server.scripts import provision_user as provision
    client, db = system
    login(client)
    # These functions use the same database accessor as the real CLI.
    monkeypatch.setattr(provision, "get_auth_db", auth.get_auth_db)
    asyncio.run(provision.provision_user("teacher@example.edu", "lecturer", "ReplacementPassword123!"))
    assert not db["auth_sessions"].docs
    assert login(client).status_code == 401
    assert login(client, password="ReplacementPassword123!").status_code == 200
    asyncio.run(provision.provision_user("new@example.edu", "student", "NewStudentPassword123!", "IT002"))
    assert login(client, "new@example.edu", "NewStudentPassword123!").json()["student_id"] == "IT002"
    with pytest.raises(ValueError):
        asyncio.run(provision.provision_user("new@example.edu", "lecturer", "ReplacementPassword123!"))
    with pytest.raises(ValueError):
        asyncio.run(provision.provision_user("invalid", "lecturer", "short"))


@pytest.mark.parametrize("legacy", [False, True])
def test_password_reset_during_login_cannot_create_a_usable_session(system, monkeypatch, legacy):
    import hashlib
    from Gradex_AI_Server.scripts import provision_user as provision
    client, db = system
    monkeypatch.setattr(provision, "get_auth_db", auth.get_auth_db)
    if legacy:
        salt = b"legacy-salt"
        digest = hashlib.pbkdf2_hmac("sha256", b"UniquePassword123!", salt, 100000).hex()
        db["users"].docs[0]["password_hash"] = f"pbkdf2_sha256$100000${salt.hex()}${digest}"

    async def verify_then_reset(func, *args):
        result = func(*args)
        if func is auth.verify_password:
            await provision.provision_user("teacher@example.edu", "lecturer", "ReplacementPassword123!")
        return result

    monkeypatch.setattr(auth, "run_in_threadpool", verify_then_reset)
    assert login(client).status_code == (401 if legacy else 200)
    assert client.get("/api/auth/me").status_code == 401
    assert auth.verify_password("ReplacementPassword123!", db["users"].docs[0]["password_hash"])
