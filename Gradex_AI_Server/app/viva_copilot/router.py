"""FastAPI routes for the isolated live interviewer copilot."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field

from Gradex_AI_Server.app.auth import require_api_key, require_websocket_api_key

from Gradex_AI_Server.app.core.database import db_instance
from Gradex_AI_Server.app.viva_analysis_runner import (
    MAX_VIVA_UPLOAD_BYTES,
    UPLOAD_DIR,
    VIDEO_SUFFIXES,
    normalize_mode,
)
from Gradex_AI_Server.app.viva_copilot import events
from Gradex_AI_Server.app.viva_copilot.analysis import analyze_live_session, build_live_transcript
from Gradex_AI_Server.app.viva_copilot.pipeline import (
    ask_question,
    enter_viva_phase,
    finalize_pending,
    ingest_audio_chunk,
    ingest_text,
    start_presentation,
)
from Gradex_AI_Server.app.viva_copilot.session_store import broadcast, session_ttl_seconds, store
from VivaEvaluationEngine.services.assessment_scoring import MODE_WITHOUT

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
        raise HTTPException(
            status_code=404,
            detail="Unknown or expired copilot session. Create a new session.",
        )
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


@router.get("/sessions/{session_id}/transcript", dependencies=_AUTH)
async def get_transcript(session_id: str) -> Dict[str, Any]:
    """The live session as JSON, for export or a client-side draft."""
    session = _session_or_404(session_id)
    return build_live_transcript(session)


@router.post("/sessions/{session_id}/analyze", dependencies=_AUTH)
async def analyze_session(
    session_id: str,
    video: UploadFile = File(...),
    assessment_mode: str = Form(default=MODE_WITHOUT),
    subject_code: Optional[str] = Form(default=None),
    student_id: Optional[str] = Form(default=None),
    progress_id: Optional[str] = Form(default=None),
) -> Dict[str, Any]:
    """Score a finished live viva from its full session recording.

    Runs the identical chain as POST /api/viva-analyze — the live transcript
    is attached as evidence, but the official mark comes from the recording so
    the engagement/acoustic/face-coverage families and their quality gates all
    behave exactly as they do for an uploaded video.

    The session is NOT deleted here; the client still calls DELETE afterwards.
    """
    session = _session_or_404(session_id)

    filename = video.filename or ""
    suffix = Path(filename).suffix.lower()
    content_type = (video.content_type or "").lower()
    if not (content_type.startswith("video/") or suffix in VIDEO_SUFFIXES):
        raise HTTPException(status_code=400, detail="Only video recordings are supported.")

    contents = await video.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty recording — nothing was captured.")
    if len(contents) > MAX_VIVA_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File size must be less than 1 GB.")

    ext = suffix if suffix in VIDEO_SUFFIXES else ".webm"
    file_path = UPLOAD_DIR / f"copilot_{uuid4().hex}{ext}"
    file_path.write_bytes(contents)

    mode = normalize_mode(assessment_mode)
    code = subject_code.strip() if isinstance(subject_code, str) else None
    sid = student_id.strip() if isinstance(student_id, str) and student_id.strip() else None

    await broadcast(session, events.phase_changed(session.session_id, "analyzing"))
    try:
        from Gradex_AI_Server.app.viva_progress import normalize_progress_id

        job_id = normalize_progress_id(progress_id)
        result = await analyze_live_session(
            session,
            str(file_path),
            db_instance=db_instance,
            mode=mode,
            video_filename=filename or file_path.name,
            subject_code=code,
            student_id=sid,
            progress_id=job_id,
        )
        result["sessionId"] = session.session_id
        await broadcast(
            session,
            events.phase_changed(session.session_id, "analyzed"),
        )
        return result
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Analysis timed out. The session recording may be too long.",
        ) from exc
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Viva analysis unavailable: {exc}") from exc
    except FileNotFoundError as exc:
        message = str(exc)
        if "Could not open video" in message or "video file" in message.lower():
            raise HTTPException(
                status_code=400,
                detail="The session recording could not be opened as a video.",
            ) from exc
        raise HTTPException(status_code=503, detail=f"Viva model file not found: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        if exc.__class__.__name__ == "VideoUnreadableError" or "could not be opened as a video" in str(exc).lower():
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=f"Viva analysis failed: {exc}") from exc
    finally:
        # Same policy as /api/viva-analyze: the recording is transient; the
        # mark and its transcript are what persist. Set VIVA_KEEP_UPLOADS=1 to
        # retain the file for debugging a bad analysis.
        if (os.getenv("VIVA_KEEP_UPLOADS") or "").strip() in {"1", "true", "yes"}:
            print(f"[VIVA] Kept live recording for debugging: {file_path}")
        else:
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception:
                pass


@router.delete("/sessions/{session_id}", dependencies=_AUTH)
async def end_session(session_id: str) -> Dict[str, Any]:
    session = _session_or_404(session_id)
    await broadcast(session, events.phase_changed(session.session_id, "ended"))
    store.delete(session_id)
    return {"ok": True}


async def _close_expired_copilot_session(session, session_id: str, websocket: WebSocket) -> None:
    ttl = session_ttl_seconds()
    await broadcast(session, events.session_expired(session.session_id, ttl_seconds=ttl))
    store.delete(session_id)
    await websocket.close(code=1008)


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
            if session.is_expired():
                await _close_expired_copilot_session(session, session_id, websocket)
                break
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=60.0)
            except asyncio.TimeoutError:
                continue
            if message.get("type") == "websocket.disconnect":
                break
            data = message.get("bytes")
            if data:
                session.touch()
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
                if session.is_expired():
                    await _close_expired_copilot_session(session, session_id, websocket)
                    break
                session.touch()
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
