"""In-memory copilot sessions. Not Mongo and not viva marks."""
from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Set
from uuid import uuid4

from fastapi import WebSocket

from Gradex_AI_Server.app.viva_copilot.answer_detector import answer_hash
from Gradex_AI_Server.app.viva_copilot.context_builder import MAX_QA_PAIRS


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
    last_chunk_had_speech: bool = False
    stt_busy: bool = False
    pending_audio: Deque[tuple] = field(default_factory=deque)
    pending_followups: Deque[Dict[str, Any]] = field(default_factory=deque)
    last_error_message: str = ""
    last_error_at: float = 0.0
    last_suggest_at: float = 0.0
    last_suggest_word_count: int = 0

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

    def create(self, project_context: Optional[Dict[str, Any]] = None) -> CopilotSession:
        session_id = "session_" + uuid4().hex[:12]
        session = CopilotSession(session_id=session_id, project_context=dict(project_context or {}))
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[CopilotSession]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


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
