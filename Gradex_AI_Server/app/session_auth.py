"""Shared cookie sessions for the main API and standalone engines."""
from datetime import datetime, timedelta, timezone
import hashlib
import os
import re
import secrets
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError
from starlette.concurrency import run_in_threadpool
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse

COOKIE_NAME = "gradex_session"
SESSION_SECONDS = 8 * 60 * 60
LOGIN_LIMIT = 20
LOGIN_WINDOW = 15 * 60
DEFAULT_STUDENT_PASSWORD = "Student@123"
_hasher = PasswordHasher()
_dummy_hash = _hasher.hash(secrets.token_urlsafe(32))
_default_student_hash = _hasher.hash(DEFAULT_STUDENT_PASSWORD)
_client = None
router = APIRouter(prefix="/api/auth", tags=["auth"])
DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://57.159.25.221:5173",
    "https://r26-se-025-brown.vercel.app",
    "https://gradex-orpin.vercel.app",
)


def get_auth_db():
    # Qualified import avoids the engines' conflicting top-level `app` packages.
    from AdaptiveExamAnalyticsEngine.app.config import settings
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.effective_mongodb_uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    return _client[settings.mongodb_db]


async def initialize_auth():
    db = get_auth_db()
    await db["users"].create_index("email", unique=True, name="uniq_users")
    indexes = await db["users"].index_information()
    old = indexes.get("uniq_users_student_id")
    partial = {"student_id": {"$type": "string"}}
    if old and old.get("partialFilterExpression") != partial:
        await db["users"].drop_index("uniq_users_student_id")
    await db["users"].create_index("student_id", unique=True, name="uniq_users_student_id", partialFilterExpression=partial)
    await db["auth_sessions"].create_index("expires_at", expireAfterSeconds=0)
    await db["auth_login_attempts"].create_index("expires_at", expireAfterSeconds=0)


def close_auth():
    global _client
    if _client is not None:
        _client.close()
        _client = None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored: str) -> bool:
    if password == "admin123":
        return False
    try:
        if stored.startswith("pbkdf2_sha256$"):
            _, iterations, salt, expected = stored.split("$")
            count = int(iterations)
            if not 100000 <= count <= 2000000:
                return False
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), count)
            return secrets.compare_digest(actual.hex(), expected)
        return _hasher.verify(stored, password)
    except (VerificationError, InvalidHashError, ValueError, TypeError):
        return False


def allowed_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "")
    origins = [*DEFAULT_CORS_ORIGINS, *configured.split(",")]
    return list(dict.fromkeys(
        origin.strip().rstrip("/") for origin in origins if origin.strip() and origin.strip() != "*"
    ))


def trusted_origin(connection: HTTPConnection) -> bool:
    origin = connection.headers.get("origin")
    forwarded_proto = connection.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    scheme = forwarded_proto or connection.url.scheme.replace("ws", "http")
    own_origin = f"{scheme}://{connection.url.netloc}"
    return origin in [own_origin, *allowed_origins()]


def public_user(user: dict) -> dict:
    return {"email": user["email"], "role": user["role"], "student_id": user.get("student_id")}


async def session_user(connection: HTTPConnection) -> dict:
    token = connection.cookies.get(COOKIE_NAME, "")
    if not token or len(token) > 128:
        raise HTTPException(401, "Please sign in")
    db = get_auth_db()
    session = await db["auth_sessions"].find_one({
        "_id": hashlib.sha256(token.encode()).hexdigest(),
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    user = await db["users"].find_one({"email": session["email"]}) if session else None
    if not user or user.get("role") not in {"lecturer", "student"} or user.get("disabled"):
        raise HTTPException(401, "Please sign in")
    if session.get("auth_version") != user.get("auth_version", 0):
        raise HTTPException(401, "Please sign in again")
    if user["role"] == "student" and not user.get("student_id"):
        raise HTTPException(401, "Student account has no student ID")
    return public_user(user)


class SessionAuthMiddleware:
    def __init__(self, app, student_routes=True):
        self.app = app
        self.student_routes = student_routes

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"} or scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)
        connection = HTTPConnection(scope)
        path = scope["path"].rstrip("/")
        try:
            if scope["type"] == "websocket" or scope.get("method") not in {"GET", "HEAD"} or connection.headers.get("origin"):
                if not trusted_origin(connection):
                    raise HTTPException(403, "Untrusted request origin")
            public_login = scope["type"] == "http" and path == "/api/auth/login" and scope["method"] == "POST"
            if not public_login:
                user = await session_user(connection)
                scope.setdefault("state", {})["user"] = user
                if user["role"] == "student" and path not in {"/api/auth/me", "/api/auth/logout"}:
                    match = re.fullmatch(r"/api/students/([^/]+)/(exams|profile|dashboard|practice-questions)", path)
                    if not self.student_routes or not match or match[1] != user["student_id"]:
                        raise HTTPException(403, "Access denied")
        except (HTTPException, PyMongoError) as exc:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            else:
                status = exc.status_code if isinstance(exc, HTTPException) else 503
                detail = exc.detail if isinstance(exc, HTTPException) else "Authentication database unavailable"
                await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)
            return
        await self.app(scope, receive, send)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)
    role: Literal["lecturer", "student"] | None = None


@router.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response, db=Depends(get_auth_db)):
    now = datetime.now(timezone.utc)
    bucket = int(now.timestamp()) // LOGIN_WINDOW
    address = request.client.host if request.client else "unknown"
    attempt_id = hashlib.sha256(f"{address}:{bucket}".encode()).hexdigest()
    attempt = await db["auth_login_attempts"].find_one_and_update(
        {"_id": attempt_id},
        {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": now + timedelta(seconds=LOGIN_WINDOW * 2)}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    if attempt["count"] > LOGIN_LIMIT:
        raise HTTPException(429, "Too many login attempts. Try again in 15 minutes.")
    email = payload.email.strip().lower()
    user = await db["users"].find_one({"email": email})
    original_hash = (user or {}).get("password_hash")
    use_default = bool(user and user.get("role") == "student" and not original_hash)
    stored = original_hash or (_default_student_hash if use_default else _dummy_hash)
    valid = await run_in_threadpool(verify_password, payload.password, stored)
    if not valid or not user or user.get("disabled") or user.get("role") not in {"lecturer", "student"}:
        raise HTTPException(401, "Invalid email or password")
    if user["role"] == "student" and not user.get("student_id"):
        raise HTTPException(401, "Invalid email or password")
    if user["role"] != "student" and payload.password == DEFAULT_STUDENT_PASSWORD:
        raise HTTPException(401, "Invalid email or password")
    if payload.role is not None and payload.role != user["role"]:
        raise HTTPException(403, f"Use the {user['role']} sign-in page for this account.")
    if use_default or not stored.startswith("$argon2id$") or _hasher.check_needs_rehash(stored):
        upgraded = await run_in_threadpool(hash_password, payload.password)
        result = await db["users"].update_one(
            {"email": email, "password_hash": original_hash}, {"$set": {"password_hash": upgraded}},
        )
        if not result.matched_count:
            raise HTTPException(401, "Credentials changed. Please sign in again")
    old_token = request.cookies.get(COOKIE_NAME)
    if old_token:
        await db["auth_sessions"].delete_one({"_id": hashlib.sha256(old_token.encode()).hexdigest()})
    token = secrets.token_urlsafe(32)
    await db["auth_sessions"].insert_one({
        "_id": hashlib.sha256(token.encode()).hexdigest(), "email": email,
        "auth_version": user.get("auth_version", 0),
        "expires_at": now + timedelta(seconds=SESSION_SECONDS),
    })
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=os.getenv("AUTH_COOKIE_SECURE", "true").lower() != "false", samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return public_user(user)


@router.get("/me")
async def me(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return request.state.user


@router.post("/logout", status_code=204)
async def logout(request: Request, db=Depends(get_auth_db)):
    token = request.cookies.get(COOKIE_NAME, "")
    await db["auth_sessions"].delete_one({"_id": hashlib.sha256(token.encode()).hexdigest()})
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(COOKIE_NAME, httponly=True, samesite="lax",
                           secure=os.getenv("AUTH_COOKIE_SECURE", "true").lower() != "false")
    return response


def setup_auth(app: FastAPI, *, student_routes=True):
    app.add_middleware(SessionAuthMiddleware, student_routes=student_routes)
    app.include_router(router)

    @app.exception_handler(PyMongoError)
    async def database_unavailable(request, exc):
        return JSONResponse({"detail": "Database unavailable"}, status_code=503)
