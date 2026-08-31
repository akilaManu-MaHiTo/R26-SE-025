"""
Mount GradingEngine at /api/grading on Gradex AI Server.

V2_QuestionExamPredictionEngine also uses a top-level ``app`` package on sys.path.
Load GradingEngine *before* those imports and keep direct references to its FastAPI
app and Mongo helpers so later ``app.*`` imports do not break grading.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Callable, Awaitable

from dotenv import load_dotenv
from fastapi import FastAPI

_APP_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _APP_DIR.parents[1]
GRADING_ROOT = _PROJECT_ROOT / "GradingEngine"
GRADING_MOUNT_PATH = "/api/grading"

_grading_app: FastAPI | None = None
_grading_connect: Callable[[], Awaitable[None]] | None = None
_grading_close: Callable[[], Awaitable[None]] | None = None
_grading_db: Any = None
_grading_enabled = False


def grading_enabled() -> bool:
    return _grading_enabled


def _snapshot_app_modules() -> dict[str, Any]:
    return {
        key: sys.modules[key]
        for key in list(sys.modules)
        if key == "app" or key.startswith("app.")
    }


def _clear_app_modules() -> None:
    for key in list(sys.modules):
        if key == "app" or key.startswith("app."):
            del sys.modules[key]


def _restore_app_modules(snapshot: dict[str, Any]) -> None:
    _clear_app_modules()
    sys.modules.update(snapshot)


def _ensure_grading_on_path() -> None:
    path_str = str(GRADING_ROOT)
    if path_str in sys.path:
        sys.path.remove(path_str)
    sys.path.insert(0, path_str)


def _load_grading_env_file() -> None:
    env_path = GRADING_ROOT / ".env"
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path, override=False)


def preload_grading_engine() -> bool:
    """
    Import GradingEngine while ``app`` is not owned by V2.
    Call this before ``analytics_api`` (or any ``from app...`` V2 import).
    """
    global _grading_app, _grading_connect, _grading_close, _grading_db, _grading_enabled

    if _grading_enabled and _grading_app is not None:
        return True

    if not GRADING_ROOT.is_dir():
        print(f"[GRADING] Skipped: missing {GRADING_ROOT}")
        return False

    _load_grading_env_file()

    snapshot = _snapshot_app_modules()
    _clear_app_modules()
    _ensure_grading_on_path()

    try:
        main_mod = importlib.import_module("app.main")
        db_mod = importlib.import_module("app.core.database")
        _grading_app = main_mod.app
        _grading_connect = db_mod.connect_to_mongo
        _grading_close = db_mod.close_mongo_connection
        _grading_db = db_mod.db_instance
        _grading_enabled = True
        print("[GRADING] Preloaded GradingEngine (isolated from V2 app package).")
        return True
    except Exception as exc:
        print(f"[GRADING] Preload failed ({exc})")
        _grading_app = None
        _grading_connect = None
        _grading_close = None
        _grading_db = None
        _grading_enabled = False
        return False
    finally:
        _restore_app_modules(snapshot)
        path_str = str(GRADING_ROOT)
        if path_str in sys.path:
            sys.path.remove(path_str)


def register_grading_routes(app: FastAPI) -> bool:
    """Mount preloaded GradingEngine at GRADING_MOUNT_PATH."""
    global _grading_enabled
    if getattr(app.state, "grading_mounted", False):
        return True

    if not _grading_enabled or _grading_app is None:
        preload_grading_engine()
    if not _grading_enabled or _grading_app is None:
        return False

    app.mount(GRADING_MOUNT_PATH, _grading_app)
    app.state.grading_mounted = True
    print(f"[GRADING] Mounted at {GRADING_MOUNT_PATH}")
    return True


async def connect_grading_mongo() -> None:
    if not _grading_enabled or _grading_connect is None:
        return
    try:
        await _grading_connect()
    except Exception as exc:
        print(f"[GRADING] Mongo connect failed ({exc}). Grading persistence may be unavailable.")


async def close_grading_mongo() -> None:
    if not _grading_enabled or _grading_close is None or _grading_db is None:
        return
    try:
        if _grading_db.client is not None:
            await _grading_close()
    except Exception as exc:
        print(f"[GRADING] Mongo close warning: {exc}")
