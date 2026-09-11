from pathlib import Path
import os

from dotenv import dotenv_values, load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Unlike GradingEngine (run from its own directory), this server is run from
# the repo root (see ../main.py / ../../CLAUDE.md), so a bare load_dotenv()
# would search upward from the repo root and miss this app/.env entirely.
_APP_DIR = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _APP_DIR.parents[1]
_APP_ENV = _APP_DIR / ".env"
_GRADING_ENV = _PROJECT_ROOT / "GradingEngine" / ".env"
_ENV_LOADED = False


class Database:
    client: AsyncIOMotorClient = None
    db = None
    # Stores one document per completed viva analysis (see app/viva_service.py).
    marks_col = None
    last_error: str | None = None
    mongo_source: str | None = None
    # When False, ensure_marks_collection() will never dial Atlas. Tests inject
    # marks_col directly and must not reach the real cluster — without this the
    # reconnect below silently replaces the injected double and writes live rows.
    allow_autoconnect: bool = True


db_instance = Database()


def _strip_env(value: str | None) -> str:
    return (value or "").strip().strip('"').strip("'")


def _load_env_files() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    load_dotenv(dotenv_path=_APP_ENV)
    if _GRADING_ENV.is_file():
        # Fill missing keys only — GradingEngine is the shared working Atlas config locally.
        load_dotenv(dotenv_path=_GRADING_ENV, override=False)


def _mongo_url_from_file(path: Path) -> str:
    if not path.is_file():
        return ""
    values = dotenv_values(path)
    return _strip_env(values.get("MONGODB_URL"))


def _mongo_url() -> str:
    _load_env_files()
    return _strip_env(os.getenv("MONGODB_URL"))


def _database_name() -> str:
    _load_env_files()
    return _strip_env(os.getenv("DATABASE_NAME")) or "vivamark"


def _mongo_url_candidates() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    for label, url in (
        ("Gradex_AI_Server/app/.env", _mongo_url_from_file(_APP_ENV)),
        ("GradingEngine/.env", _mongo_url_from_file(_GRADING_ENV)),
        ("process environment", _mongo_url()),
    ):
        if not url or url in seen:
            continue
        seen.add(url)
        candidates.append((label, url))
    return candidates


async def _ensure_marks_indexes() -> None:
    if db_instance.marks_col is None:
        return
    await db_instance.marks_col.create_index([("processed_at", -1)])
    await db_instance.marks_col.create_index([("student_id", 1), ("processed_at", -1)])
    await db_instance.marks_col.create_index([("published", 1), ("processed_at", -1)])


async def _try_connect(source: str, url: str, db_name: str) -> None:
    client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=10000)
    await client.admin.command("ping")
    db_instance.client = client
    db_instance.db = client[db_name]
    db_instance.marks_col = db_instance.db["marks"]
    db_instance.mongo_source = source
    db_instance.last_error = None
    await _ensure_marks_indexes()


async def connect_to_mongo():
    db_instance.client = None
    db_instance.db = None
    db_instance.marks_col = None
    db_instance.last_error = None
    db_instance.mongo_source = None

    db_name = _database_name()
    if not db_name:
        db_instance.last_error = "DATABASE_NAME is missing."
        print(f"[MONGO] Skipped: {db_instance.last_error}")
        return

    candidates = _mongo_url_candidates()
    if not candidates:
        db_instance.last_error = "MONGODB_URL is missing."
        print(f"[MONGO] Skipped: {db_instance.last_error}")
        return

    errors: list[str] = []
    for source, url in candidates:
        try:
            await _try_connect(source, url, db_name)
            print(f"Connected to MongoDB Atlas ({source}, db={db_name})")
            return
        except Exception as exc:
            message = f"{source}: {type(exc).__name__}"
            errors.append(message)
            print(f"[MONGO] {message} — trying next credential source.")
            if db_instance.client is not None:
                try:
                    db_instance.client.close()
                except Exception:
                    pass
            db_instance.client = None
            db_instance.db = None
            db_instance.marks_col = None

    db_instance.last_error = errors[-1] if errors else "Unknown"
    print(
        "[MONGO] Unavailable. Marks will not persist; publish is disabled. "
        "Set MONGODB_URL in Gradex_AI_Server/app/.env or GradingEngine/.env."
    )


async def ensure_marks_collection() -> bool:
    """Ping Mongo before a write; reconnect if the Atlas session dropped mid-request."""
    if db_instance.marks_col is not None and db_instance.client is not None:
        try:
            await db_instance.client.admin.command("ping")
            return True
        except Exception as exc:
            db_instance.last_error = type(exc).__name__
            print(f"[MONGO] Ping failed before write ({db_instance.last_error}) — reconnecting.")
    if not db_instance.allow_autoconnect:
        # Offline mode (tests): report whatever collection was injected, never dial.
        return db_instance.marks_col is not None
    await connect_to_mongo()
    return db_instance.marks_col is not None


async def close_mongo_connection():
    if db_instance.client is not None:
        db_instance.client.close()
        print("MongoDB connection closed.")
    db_instance.client = None
    db_instance.db = None
    db_instance.marks_col = None
    db_instance.mongo_source = None
