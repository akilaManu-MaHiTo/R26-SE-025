"""In-memory copilot sessions. Not Mongo and not viva marks."""
from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Set
from uuid import uuid4

from fastapi import WebSocket

from Gradex_AI_Server.app.viva_copilot.answer_detector import answer_hash
from Gradex_AI_Server.app.viva_copilot.context_builder import MAX_QA_PAIRS

_DEFAULT_SESSION_TTL_SECONDS = 14400.0


def session_ttl_seconds() -> float:
    raw = (os.getenv("VIVA_COPILOT_SESSION_TTL_SECONDS") or "14400").strip()
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_SESSION_TTL_SECONDS
    if value <= 0:
        return 0.0
    return max(60.0, value)


@dataclass
class CopilotSession:
    session_id: str
    phase: str = "idle"
    project_context: Dict[str, Any] = field(default_factory=dict)
    presentation_parts: List[str] = field(default_factory=list)
    main_points: List[str] = field(default_factory=list)
    current_question: Optional[str] = None
    utterance_buffer: str = ""
    recent_hashes: Deque[str] = field(default_factory=lambda: deque(maxlen=24))
    recent_qa: Deque[Dict[str, str]] = field(default_factory=lambda: deque(maxlen=MAX_QA_PAIRS))
    asked_questions: List[str] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    analysis: Dict[str, Any] = field(default_factory=dict)
    transcript_log: List[Dict[str, Any]] = field(default_factory=list)
    ws_clients: Set[WebSocket] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    busy_llm: bool = False
    created_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)
    last_chunk_had_speech: bool = False
    stt_busy: bool = False
    pending_audio: Deque[tuple] = field(default_factory=deque)
    pending_followups: Deque[Dict[str, Any]] = field(default_factory=deque)
    last_error_message: str = ""
    last_error_at: float = 0.0
    last_suggest_at: float = 0.0
    last_suggest_word_count: int = 0
    # Raw accepted utterances, for near-duplicate rejection (hashes alone miss
    # a growing utterance finalized twice by the two independent STT paths).
    recent_texts: Deque[str] = field(default_factory=lambda: deque(maxlen=12))
    # Answers accepted since the last viva-phase suggestion run. They are
    # joined into one block so the LLM reasons over a full stretch of speech
    # rather than a single fragment.
    pending_answer_parts: List[str] = field(default_factory=list)

    def touch(self) -> None:
        self.last_activity_at = time.time()

    def is_expired(self) -> bool:
        ttl = session_ttl_seconds()
        if ttl <= 0:
            return False
        return time.time() - self.last_activity_at > ttl

    def seconds_until_expiry(self) -> Optional[float]:
        ttl = session_ttl_seconds()
        if ttl <= 0:
            return None
        remaining = ttl - (time.time() - self.last_activity_at)
        return max(0.0, remaining)

    def presentation_text(self) -> str:
        return " ".join(self.presentation_parts).strip()

    def snapshot(self) -> Dict[str, Any]:
        analysis = dict(self.analysis or {})
        return {
            "phase": self.phase,
            "projectContext": self.project_context,
            "mainPoints": list(self.main_points),
            "currentQuestion": self.current_question,
            "suggestions": list(self.suggestions),
            "analysis": {
                "topics": list(analysis.get("topics") or []),
                "concepts": list(analysis.get("concepts") or []),
                "technologies": list(analysis.get("technologies") or []),
                "claims": list(analysis.get("claims") or []),
                "gaps": list(analysis.get("gaps") or []),
            },
            "transcript": list(self.transcript_log)[-80:],
            "askedQuestions": list(self.asked_questions),
        }

    def remember_hash(self, text: str) -> None:
        digest = answer_hash(text)
        if digest:
            self.recent_hashes.append(digest)
        if text and text.strip():
            self.recent_texts.append(text.strip())

    def pending_answer_text(self) -> str:
        return " ".join(part for part in self.pending_answer_parts if part).strip()

    def append_transcript(self, speaker: str, text: str, final: bool) -> None:
        self.transcript_log.append(
            {
                "speaker": speaker,
                "text": text,
                "final": final,
                "timestamp": int(time.time()),
            }
        )
        if len(self.transcript_log) > 200:
            self.transcript_log = self.transcript_log[-200:]


class SessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, CopilotSession] = {}

    def _purge_expired(self) -> None:
        ttl = session_ttl_seconds()
        if ttl <= 0:
            return
        now = time.time()
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session.last_activity_at > ttl
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)

    def _is_expired(self, session: CopilotSession) -> bool:
        ttl = session_ttl_seconds()
        if ttl <= 0:
            return False
        return time.time() - session.last_activity_at > ttl

    def create(self, project_context: Optional[Dict[str, Any]] = None) -> CopilotSession:
        self._purge_expired()
        session_id = "session_" + uuid4().hex[:12]
        session = CopilotSession(session_id=session_id, project_context=dict(project_context or {}))
        session.touch()
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[CopilotSession]:
        self._purge_expired()
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if self._is_expired(session):
            self._sessions.pop(session_id, None)
            return None
        session.touch()
        return session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def expire_if_idle(self, session_id: str) -> bool:
        """Remove session when idle past TTL. Returns True if it was expired."""
        session = self._sessions.get(session_id)
        if session is None:
            return True
        if not session.is_expired():
            return False
        self._sessions.pop(session_id, None)
        return True


store = SessionStore()


async def broadcast(session: CopilotSession, event: Dict[str, Any]) -> None:
    dead: List[WebSocket] = []
    for client in list(session.ws_clients):
        try:
            await client.send_json(event)
        except Exception:
            dead.append(client)
    for client in dead:
        session.ws_clients.discard(client)
