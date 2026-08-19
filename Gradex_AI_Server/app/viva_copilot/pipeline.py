"""Session orchestration: STT → answer detection → context → LLM → events."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from Gradex_AI_Server.app.viva_copilot import events
from Gradex_AI_Server.app.viva_copilot.answer_detector import detect_final_answer, word_count
from Gradex_AI_Server.app.viva_copilot.context_builder import build_llm_context
from Gradex_AI_Server.app.viva_copilot.followup_llm import generate_followups
from Gradex_AI_Server.app.viva_copilot.session_store import CopilotSession, broadcast
from Gradex_AI_Server.app.viva_copilot.stt import transcribe_chunk

GenerateFn = Callable[[Dict[str, Any], Optional[list]], Dict[str, Any]]
TranscribeFn = Callable[..., str]

# Bulk LLM during presentation: not every STT chunk. Free Groq is ~30k TPM / low RPM.
PRESENTATION_SUGGEST_MIN_WORDS = 28
PRESENTATION_SUGGEST_MIN_SECONDS = 40.0


def should_refresh_presentation_suggestions(
    *,
    word_count_value: int,
    last_word_count: int,
    last_at: float,
    now: Optional[float] = None,
    min_words: int = PRESENTATION_SUGGEST_MIN_WORDS,
    min_seconds: float = PRESENTATION_SUGGEST_MIN_SECONDS,
) -> bool:
    current_time = time.time() if now is None else now
    if word_count_value < min_words:
        return False
    if word_count_value - last_word_count < min_words:
        return False
    if last_at and current_time - last_at < min_seconds:
        return False
    return True


def _append_utterance(buffer: str, piece: str) -> str:
    piece = (piece or "").strip()
    if not piece:
        return buffer
    if not buffer:
        return piece
    if piece.lower() in buffer.lower():
        return buffer
    return f"{buffer} {piece}".strip()


async def ingest_audio_chunk(
    session: CopilotSession,
    audio_bytes: bytes,
    *,
    filename: str = "chunk.webm",
    content_type: str = "audio/webm",
    transcribe: Optional[TranscribeFn] = None,
    generate: Optional[GenerateFn] = None,
) -> None:
    if session.phase not in {"presentation", "viva"}:
        return
    async with session.lock:
        if session.stt_busy:
            session.pending_audio = audio_bytes
            session.pending_filename = filename
            session.pending_content_type = content_type
            return
        session.stt_busy = True
    text = ""
    failed = False
    try:
        text = await asyncio.to_thread(
            transcribe or transcribe_chunk,
            audio_bytes,
            filename=filename,
            content_type=content_type,
        )
    except Exception as exc:
        failed = True
        message = str(exc)
        now = asyncio.get_event_loop().time()
        if message != session.last_error_message or (now - session.last_error_at) > 12:
            session.last_error_message = message
            session.last_error_at = now
            await broadcast(session, events.copilot_error(session.session_id, message))
    finally:
        pending = None
        pending_name = filename
        pending_type = content_type
        async with session.lock:
            session.stt_busy = False
            pending = session.pending_audio
            pending_name = session.pending_filename
            pending_type = session.pending_content_type
            session.pending_audio = None

    if not failed:
        text = (text or "").strip()
        to_finalize = None
        async with session.lock:
            if text:
                session.utterance_buffer = _append_utterance(session.utterance_buffer, text)
                session.last_chunk_had_speech = True
                await broadcast(
                    session,
                    events.transcript_partial(session.session_id, session.utterance_buffer),
                )
            else:
                had_speech = session.last_chunk_had_speech
                session.last_chunk_had_speech = False
                pending_utterance = session.utterance_buffer.strip()
                if had_speech and pending_utterance:
                    session.utterance_buffer = ""
                    to_finalize = pending_utterance
        if to_finalize:
            await _finalize_utterance(session, to_finalize, generate=generate)

    if pending:
        await ingest_audio_chunk(
            session,
            pending,
            filename=pending_name,
            content_type=pending_type,
            transcribe=transcribe,
            generate=generate,
        )


async def _finalize_utterance(
    session: CopilotSession,
    text: str,
    *,
    generate: Optional[GenerateFn] = None,
) -> None:
    min_words = 4 if session.phase == "presentation" else 5
    cleaned = detect_final_answer(text, session.recent_hashes, min_words=min_words)
    if not cleaned:
        return

    session.remember_hash(cleaned)
    session.append_transcript("candidate", cleaned, True)
    await broadcast(session, events.transcript_final(session.session_id, cleaned, "candidate"))

    if session.phase == "presentation":
        session.presentation_parts.append(cleaned)
        await _maybe_presentation_followups(session, generate=generate)
        return

    answer_id = "answer_" + uuid4().hex[:8]
    await broadcast(session, events.candidate_answer_final(session.session_id, answer_id, cleaned))
    if session.current_question:
        session.recent_qa.append({"question": session.current_question, "answer": cleaned})
    await _run_followups(session, answer_id, candidate_answer=cleaned, generate=generate)


async def enter_viva_phase(
    session: CopilotSession,
    *,
    generate: Optional[GenerateFn] = None,
) -> None:
    async with session.lock:
        leftover = session.utterance_buffer.strip()
        session.utterance_buffer = ""
        session.phase = "viva"
    if leftover and word_count(leftover) >= 4:
        session.presentation_parts.append(leftover)
        session.remember_hash(leftover)
        session.append_transcript("candidate", leftover, True)
        await broadcast(session, events.transcript_final(session.session_id, leftover, "candidate"))

    await broadcast(session, events.phase_changed(session.session_id, "viva"))
    presentation = session.presentation_text()
    if not presentation:
        await broadcast(
            session,
            events.copilot_error(session.session_id, "No presentation transcript yet — suggestions will wait for an answer."),
        )
        return
    # Skip a second LLM hit if we just generated during the talk.
    if session.suggestions and session.last_suggest_at and (time.time() - session.last_suggest_at) < 90:
        await broadcast(
            session,
            events.followup_suggestions(
                session.session_id,
                "answer_presentation",
                session.suggestions,
                session.analysis,
            ),
        )
        if session.main_points:
            await broadcast(session, events.presentation_points(session.session_id, session.main_points, session.analysis))
        return
    await _run_followups(
        session,
        "answer_presentation",
        candidate_answer=presentation,
        from_presentation=True,
        generate=generate,
    )


async def start_presentation(session: CopilotSession) -> None:
    async with session.lock:
        session.phase = "presentation"
        session.utterance_buffer = ""
    await broadcast(session, events.phase_changed(session.session_id, "presentation"))


async def finalize_pending(
    session: CopilotSession,
    *,
    generate: Optional[GenerateFn] = None,
) -> None:
    async with session.lock:
        pending = session.utterance_buffer.strip()
        session.utterance_buffer = ""
        session.last_chunk_had_speech = False
    if pending:
        await _finalize_utterance(session, pending, generate=generate)


async def ask_question(session: CopilotSession, question: str) -> None:
    cleaned = (question or "").strip()
    if not cleaned:
        return
    async with session.lock:
        session.current_question = cleaned
        session.utterance_buffer = ""
        if cleaned not in session.asked_questions:
            session.asked_questions.append(cleaned)
        session.append_transcript("interviewer", cleaned, True)
    await broadcast(session, events.interviewer_asked(session.session_id, cleaned))
    await broadcast(session, events.transcript_final(session.session_id, cleaned, "interviewer"))


async def _maybe_presentation_followups(
    session: CopilotSession,
    *,
    generate: Optional[GenerateFn] = None,
) -> None:
    text = session.presentation_text()
    words = word_count(text)
    if not should_refresh_presentation_suggestions(
        word_count_value=words,
        last_word_count=session.last_suggest_word_count,
        last_at=session.last_suggest_at,
    ):
        return
    await _run_followups(
        session,
        "answer_presentation",
        candidate_answer=text,
        from_presentation=True,
        generate=generate,
    )


async def _run_followups(
    session: CopilotSession,
    answer_id: str,
    *,
    candidate_answer: str,
    from_presentation: bool = False,
    generate: Optional[GenerateFn] = None,
) -> None:
    if session.busy_llm:
        return
    session.busy_llm = True
    context = build_llm_context(
        session_id=session.session_id,
        project_context=session.project_context,
        current_question=None if from_presentation else session.current_question,
        candidate_answer=candidate_answer,
        recent_qa=list(session.recent_qa),
        presentation_points=session.main_points,
        presentation_excerpt=session.presentation_text(),
    )
    generate_fn = generate or generate_followups
    try:
        result = await asyncio.to_thread(generate_fn, context, list(session.asked_questions))
        analysis = result.get("analysis") or {}
        suggestions = result.get("suggestions") or []
        points = result.get("main_points") or []
        session.analysis = analysis
        session.suggestions = suggestions
        if from_presentation and points:
            session.main_points = points
            await broadcast(session, events.presentation_points(session.session_id, points, analysis))
        elif from_presentation and not session.main_points:
            fallback = (analysis.get("topics") or [])[:8]
            session.main_points = fallback
            await broadcast(session, events.presentation_points(session.session_id, fallback, analysis))

        await broadcast(
            session,
            events.followup_suggestions(session.session_id, answer_id, suggestions, analysis),
        )
        session.last_suggest_at = time.time()
        session.last_suggest_word_count = word_count(candidate_answer)
    except Exception as exc:
        await broadcast(session, events.copilot_error(session.session_id, f"Suggestion generation failed: {exc}"))
    finally:
        session.busy_llm = False
