"""Session orchestration: STT → answer detection → context → LLM → events."""
from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from Gradex_AI_Server.app.viva_copilot import events
from Gradex_AI_Server.app.viva_copilot import events
from Gradex_AI_Server.app.viva_copilot.answer_detector import detect_final_answer, word_count
from Gradex_AI_Server.app.viva_copilot.context_builder import build_llm_context
from Gradex_AI_Server.app.viva_copilot.followup_llm import generate_followups
from Gradex_AI_Server.app.viva_copilot.session_store import CopilotSession, broadcast, session_ttl_seconds, store
from Gradex_AI_Server.app.viva_copilot.stt import transcribe_chunk

GenerateFn = Callable[[Dict[str, Any], Optional[list]], Dict[str, Any]]
TranscribeFn = Callable[..., str]

# Bulk LLM during presentation: tuned for faster live feedback.
PRESENTATION_SUGGEST_MIN_WORDS = 5
PRESENTATION_SUGGEST_MIN_SECONDS = 3.0



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


def _accepts_on_partial_suggestion(fn: Callable[..., Any]) -> bool:
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    params = signature.parameters.values()
    return any(
        p.name == "on_partial_suggestion" or p.kind == inspect.Parameter.VAR_KEYWORD
        for p in params
    )


def _append_utterance(buffer: str, piece: str) -> str:
    piece = (piece or "").strip()
    if not piece:
        return buffer
    if not buffer:
        return piece
    if piece.lower() in buffer.lower():
        return buffer
    return f"{buffer} {piece}".strip()


MAX_PENDING_AUDIO = 8
MAX_PENDING_FOLLOWUPS = 4


async def ingest_audio_chunk(
    session: CopilotSession,
    audio_bytes: bytes,
    *,
    filename: str = "chunk.webm",
    content_type: str = "audio/webm",
    transcribe: Optional[TranscribeFn] = None,
    generate: Optional[GenerateFn] = None,
) -> None:
    if session.is_expired():
        ttl = session_ttl_seconds()
        await broadcast(session, events.session_expired(session.session_id, ttl_seconds=ttl))
        store.delete(session.session_id)
        return
    session.touch()
    if session.phase not in {"presentation", "viva"}:
        return
    overflow = False
    async with session.lock:
        if session.stt_busy:
            if len(session.pending_audio) >= MAX_PENDING_AUDIO:
                session.pending_audio.popleft()
                overflow = True
            session.pending_audio.append((audio_bytes, filename, content_type))
            queued = True
        else:
            session.stt_busy = True
            queued = False
    if overflow:
        await broadcast(
            session,
            events.copilot_error(
                session.session_id,
                "Audio backlog was full; the oldest unpublished slice was dropped.",
            ),
        )
    if queued:
        return
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
        next_chunk = None
        async with session.lock:
            session.stt_busy = False
            if session.pending_audio:
                next_chunk = session.pending_audio.popleft()

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

    if next_chunk:
        await ingest_audio_chunk(
            session,
            next_chunk[0],
            filename=next_chunk[1],
            content_type=next_chunk[2],
            transcribe=transcribe,
            generate=generate,
        )


async def ingest_text(
    session: CopilotSession,
    text: str,
    *,
    is_final: bool,
    generate: Optional[GenerateFn] = None,
) -> None:
    """Ingest a transcript fragment produced client-side (browser Web Speech
    API) instead of server-side Groq Whisper STT.

    This is the fast path: the browser's on-device/network speech engine
    returns text with ~0 network latency, so we can display it and — once a
    final segment arrives — kick off follow-up generation immediately,
    without waiting for an audio chunk to be uploaded and transcribed by
    Groq. Groq STT (``ingest_audio_chunk``) keeps running in parallel as an
    accuracy backstop; whichever path finalizes an utterance first wins
    because ``detect_final_answer`` de-dupes by content hash.
    """
    if session.phase not in {"presentation", "viva"}:
        return
    cleaned = (text or "").strip()
    if not cleaned:
        return

    if not is_final:
        # Browser SpeechRecognition interim results already contain the full
        # accumulated utterance-so-far, so we show it directly rather than
        # appending (unlike the Groq audio-chunk path, which sees only the
        # newly-transcribed slice each time).
        async with session.lock:
            session.utterance_buffer = cleaned
        await broadcast(session, events.transcript_partial(session.session_id, cleaned))
        return

    async with session.lock:
        session.utterance_buffer = ""
        session.last_chunk_had_speech = False
    await _finalize_utterance(session, cleaned, generate=generate)


async def _finalize_utterance(
    session: CopilotSession,
    text: str,
    *,
    generate: Optional[GenerateFn] = None,
) -> None:
    min_words = 3
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
    overflow = False
    async with session.lock:
        if session.busy_llm:
            if len(session.pending_followups) >= MAX_PENDING_FOLLOWUPS:
                session.pending_followups.popleft()
                overflow = True
            session.pending_followups.append(
                {
                    "answer_id": answer_id,
                    "candidate_answer": candidate_answer,
                    "from_presentation": from_presentation,
                }
            )
            queued = True
        else:
            session.busy_llm = True
            queued = False
    if overflow:
        await broadcast(
            session,
            events.copilot_error(
                session.session_id,
                "Suggestion backlog was full; the oldest pending follow-up was dropped.",
            ),
        )
    if queued:
        return
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
    loop = asyncio.get_event_loop()

    def _on_partial_suggestion(suggestion: Dict[str, Any]) -> None:
        # Called from the worker thread running generate_fn (via
        # asyncio.to_thread). Hop back onto the event loop to broadcast so
        # the interviewer sees the first suggestion the moment Groq streams
        # it, instead of waiting for the whole follow-up JSON to finish.
        asyncio.run_coroutine_threadsafe(
            broadcast(
                session,
                events.followup_suggestion_partial(session.session_id, answer_id, suggestion),
            ),
            loop,
        )

    supports_partial = _accepts_on_partial_suggestion(generate_fn)
    try:
        if supports_partial:
            result = await asyncio.to_thread(
                generate_fn,
                context,
                list(session.asked_questions),
                on_partial_suggestion=_on_partial_suggestion,
            )
        else:
            # Backwards compatible with test doubles / custom generate_fn
            # implementations that do not accept on_partial_suggestion.
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
        next_job = None
        async with session.lock:
            session.busy_llm = False
            if session.pending_followups:
                next_job = session.pending_followups.popleft()
        if next_job:
            await _run_followups(
                session,
                next_job["answer_id"],
                candidate_answer=next_job["candidate_answer"],
                from_presentation=bool(next_job.get("from_presentation")),
                generate=generate,
            )
