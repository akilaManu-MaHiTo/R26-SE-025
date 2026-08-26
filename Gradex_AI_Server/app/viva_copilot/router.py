"""FastAPI routes for the isolated live interviewer copilot."""
from __future__ import annotations

import json
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from Gradex_AI_Server.app.auth import require_api_key, require_websocket_api_key

from Gradex_AI_Server.app.viva_copilot import events
from Gradex_AI_Server.app.viva_copilot.pipeline import (
    ask_question,
    enter_viva_phase,
    finalize_pending,
    ingest_audio_chunk,
    ingest_text,
    start_presentation,
)
from Gradex_AI_Server.app.viva_copilot.session_store import broadcast, store

router = APIRouter(prefix="/api/viva-copilot", tags=["viva-copilot"])
_AUTH = [Depends(require_api_key)]


class ProjectContextPayload(BaseModel):
    project: str = ""
    module: str = ""
    notes: str = ""


class CreateSessionPayload(BaseModel):
    projectContext: Optional[ProjectContextPayload] = None


class PhasePayload(BaseModel):
    phase: Literal["presentation", "viva"]


class AskPayload(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class ContextPayload(BaseModel):
    projectContext: ProjectContextPayload


def _session_or_404(session_id: str):
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown copilot session.")
    return session


@router.post("/sessions", dependencies=_AUTH)
async def create_session(payload: CreateSessionPayload | None = None) -> Dict[str, Any]:
    context = {}
    if payload and payload.projectContext:
        context = payload.projectContext.model_dump()
    session = store.create(context)
    return {"sessionId": session.session_id, "phase": session.phase}


@router.get("/sessions/{session_id}", dependencies=_AUTH)
async def get_session(session_id: str) -> Dict[str, Any]:
    session = _session_or_404(session_id)
    return {"sessionId": session.session_id, **session.snapshot()}


@router.post("/sessions/{session_id}/phase", dependencies=_AUTH)
async def set_phase(session_id: str, payload: PhasePayload) -> Dict[str, Any]:
    session = _session_or_404(session_id)
    if payload.phase == "presentation":
        await start_presentation(session)
    else:
        await enter_viva_phase(session)
    return {"sessionId": session.session_id, "phase": session.phase}


@router.post("/sessions/{session_id}/finalize", dependencies=_AUTH)
async def finalize_utterance(session_id: str) -> Dict[str, Any]:
    session = _session_or_404(session_id)
    await finalize_pending(session)
    return {"ok": True, "sessionId": session.session_id}


@router.post("/sessions/{session_id}/ask", dependencies=_AUTH)
async def ask(session_id: str, payload: AskPayload) -> Dict[str, Any]:
    session = _session_or_404(session_id)
    if session.phase != "viva":
        raise HTTPException(
            status_code=409,
            detail="Ask this is only available during the viva phase.",
        )
    await ask_question(session, payload.question)
    return {"sessionId": session.session_id, "currentQuestion": session.current_question}


@router.post("/sessions/{session_id}/context", dependencies=_AUTH)
async def set_context(session_id: str, payload: ContextPayload) -> Dict[str, Any]:
    session = _session_or_404(session_id)
    session.project_context = payload.projectContext.model_dump()
    return {"sessionId": session.session_id, "projectContext": session.project_context}


@router.delete("/sessions/{session_id}", dependencies=_AUTH)
async def end_session(session_id: str) -> Dict[str, Any]:
    session = _session_or_404(session_id)
    await broadcast(session, events.phase_changed(session.session_id, "ended"))
    store.delete(session_id)
    return {"ok": True}


@router.websocket("/ws/{session_id}")
async def copilot_ws(websocket: WebSocket, session_id: str) -> None:
    if not await require_websocket_api_key(websocket):
        return
    session = store.get(session_id)
    if session is None:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    session.ws_clients.add(websocket)
    await websocket.send_json(events.session_state(session.session_id, session.snapshot()))
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            data = message.get("bytes")
            if data:
                filename = "chunk.webm"
                content_type = "audio/webm"
                await ingest_audio_chunk(
                    session,
                    data,
                    filename=filename,
                    content_type=content_type,
                )
                continue
            text = message.get("text")
            if not text:
                continue
            stripped = text.strip()
            if stripped == "ping":
                await websocket.send_json({"event": "pong", "sessionId": session_id})
                continue
            # Client-side Web Speech API result: {"type": "speech", "text": "...", "isFinal": bool}
            # This is the fast path — see pipeline.ingest_text for why it
            # bypasses Groq Whisper STT entirely.
            try:
                payload = json.loads(stripped)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(payload, dict) and payload.get("type") == "speech":
                await ingest_text(
                    session,
                    str(payload.get("text") or ""),
                    is_final=bool(payload.get("isFinal")),
                )
    except WebSocketDisconnect:
        pass
    finally:
        session.ws_clients.discard(websocket)
