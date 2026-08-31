"""Optional shared API key for viva analyze, publish, and copilot.

Set GRADEX_API_KEY (or VIVA_API_KEY) in Gradex_AI_Server/app/.env.
The Vite client sends it as X-API-Key / WebSocket query api_key.
If no key is configured, requests stay open (local demo).
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request, WebSocket, status
from dotenv import load_dotenv

_ENV_LOADED = False


def _load_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


def configured_api_key() -> Optional[str]:
    _load_env()
    for name in ("GRADEX_API_KEY", "VIVA_API_KEY"):
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return None


def ensure_dev_api_key() -> Optional[str]:
    """Create GRADEX_API_KEY in app/.env if neither key is set, so auth is on."""
    existing = configured_api_key()
    if existing:
        return existing
    env_path = Path(__file__).resolve().parent / ".env"
    generated = secrets.token_urlsafe(24)
    try:
        previous = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""
        if not previous.endswith("\n") and previous:
            previous += "\n"
        env_path.write_text(
            previous + f"GRADEX_API_KEY={generated}\n",
            encoding="utf-8",
        )
    except OSError:
        return None
    os.environ["GRADEX_API_KEY"] = generated
    _sync_client_key(generated)
    print("[AUTH] Wrote GRADEX_API_KEY to app/.env and VITE_GRADEX_API_KEY to Gradex_AI_Client/.env.local.")
    return generated


def _sync_client_key(key: str) -> None:
    client_env = Path(__file__).resolve().parents[2] / "Gradex_AI_Client" / ".env.local"
    try:
        text = client_env.read_text(encoding="utf-8") if client_env.is_file() else ""
        lines = text.splitlines()
        replaced = False
        out: list[str] = []
        for line in lines:
            if line.startswith("VITE_GRADEX_API_KEY="):
                out.append(f"VITE_GRADEX_API_KEY={key}")
                replaced = True
            else:
                out.append(line)
        if not replaced:
            if out and out[-1] != "":
                out.append("")
            out.append(f"VITE_GRADEX_API_KEY={key}")
        client_env.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    except OSError:
        pass


def _extract_key(header_value: Optional[str], query_value: Optional[str]) -> str:
    if header_value and header_value.strip():
        return header_value.strip()
    if query_value and query_value.strip():
        return query_value.strip()
    return ""


async def require_api_key(request: Request) -> None:
    expected = configured_api_key()
    if not expected:
        return
    got = _extract_key(request.headers.get("x-api-key"), request.query_params.get("api_key"))
    if not secrets.compare_digest(got, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key. Set X-API-Key (GRADEX_API_KEY).",
        )


async def require_websocket_api_key(websocket: WebSocket) -> bool:
    """Return True if the socket may continue. Closes with 1008 on failure."""
    expected = configured_api_key()
    if not expected:
        return True
    header = websocket.headers.get("x-api-key")
    query = websocket.query_params.get("api_key")
    got = _extract_key(header, query)
    if got and secrets.compare_digest(got, expected):
        return True
    await websocket.close(code=1008, reason="Missing or invalid API key")
    return False
