"""AI 1: classify a labeled viva transcript into conversation segments.

Does not grade. Timestamps are taken from real turns (turn IDs), never from
the model. Heuristic pairing remains the fallback when Groq is missing or
returns invalid JSON.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Sequence

from services.conversation import (
    MAX_PAIRS,
    PRESENTATION_PHASES,
    QA_PHASES,
    assign_turn_ids,
    full_transcript_text,
    pair_question_answers,
)
from services.llm_judge import _api_key, _extract_json_object, _model_candidates, _model_name


SEGMENT_TYPES = frozenset(
    {
        "presentation",
        "panel_interruption",
        "panel_question",
        "student_answer",
        "follow_up_question",
        "follow_up_answer",
        "student_question",
        "instruction",
        "return_to_presentation",
    }
)
QUESTION_TYPES = frozenset({"panel_question", "follow_up_question"})
ANSWER_TYPES = frozenset({"student_answer", "follow_up_answer"})
CHAR_BUDGET = 40_000
WINDOW_SECONDS = 8 * 60
OVERLAP_SECONDS = 30

_SYSTEM_PROMPT = """You are analyzing a university viva (oral exam) conversation.

You receive a chronological transcript. Each turn has an ID (T00, T01, ...),
timestamps, and a role: STUDENT, PANEL_01, PANEL_02, ...

Your job is ONLY to classify conversation structure.
Do not grade the student.
Do not invent turns, speakers, or text.
Use only the given turn IDs.

Segment types (use these exact strings):
- presentation: student presenting project material
- panel_interruption: panel cuts in without a real question
- panel_question: panel asks a question
- student_answer: student answers a panel question
- follow_up_question: panel follow-up on the previous Q&A
- follow_up_answer: student answers that follow-up
- student_question: student asks the panel something
- instruction: panel direction, backchannel, or "okay / continue / move to X"
- return_to_presentation: student resumes presenting after an interruption or instruction

Rules:
- "Okay, move to the deployment section." is instruction, NOT a question.
- Backchannels like "mm-hmm", "okay", "right" are instruction.
- A question with no following student speech is still panel_question or
  follow_up_question; do not invent an answer.
- Do not copy timestamps. Return turn_ids only.
- Cover every turn exactly once, in chronological order.

Return strict JSON only (no markdown):
{
  "segments": [
    {"type": "presentation", "turn_ids": ["T00"]},
    {"type": "panel_question", "turn_ids": ["T01"]},
    {"type": "student_answer", "turn_ids": ["T02"]}
  ]
}
"""

GroqCall = Callable[[str, str, str], str]


def _as_turn_ids(value: Any) -> List[str]:
    if isinstance(value, str):
        token = value.strip()
        return [token] if token else []
    if isinstance(value, dict):
        return _as_turn_ids(value.get("turn_ids") or value.get("turn_id"))
    if not isinstance(value, (list, tuple)):
        return []
    ids: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            ids.append(item.strip())
        elif isinstance(item, dict):
            ids.extend(_as_turn_ids(item.get("turn_id") or item.get("id")))
    return ids


def _flatten_raw_segments(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    flattened: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "").strip().lower()
        if kind == "qa":
            question_ids = _as_turn_ids(
                item.get("question_turn_ids") or item.get("question")
            )
            answer_ids = _as_turn_ids(item.get("answer_turn_ids") or item.get("answer"))
            if question_ids:
                flattened.append({"type": "panel_question", "turn_ids": question_ids})
            if answer_ids:
                flattened.append({"type": "student_answer", "turn_ids": answer_ids})
            continue
        flattened.append(item)
    return flattened


def _turns_by_id(turns: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    for turn in turns:
        tid = str(turn.get("turn_id") or "").strip()
        if tid:
            mapping[tid] = turn
    return mapping


def _join_text(turns: Sequence[Dict[str, Any]]) -> str:
    parts = [str(turn.get("text") or "").strip() for turn in turns]
    return " ".join(part for part in parts if part).strip()


def resolve_segment(
    raw: Dict[str, Any],
    turns_by_id: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    kind = str(raw.get("type") or "").strip().lower()
    if kind not in SEGMENT_TYPES:
        return None
    turn_ids = [tid for tid in _as_turn_ids(raw.get("turn_ids")) if tid in turns_by_id]
    if not turn_ids:
        return None
    matched = [turns_by_id[tid] for tid in turn_ids]
    start = matched[0].get("start")
    end = matched[-1].get("end")
    try:
        start = round(float(start), 3)
    except (TypeError, ValueError):
        start = None
    try:
        end = round(float(end), 3)
    except (TypeError, ValueError):
        end = start
    speaker = str(matched[0].get("label") or ("STUDENT" if matched[0].get("role") == "student" else "PANEL_01"))
    return {
        "type": kind,
        "turn_ids": turn_ids,
        "speaker": speaker,
        "start": start,
        "end": end,
        "text": _join_text(matched),
    }


def resolve_segments(
    raw_segments: Any,
    turns: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    turns_by_id = _turns_by_id(turns)
    resolved: List[Dict[str, Any]] = []
    for item in _flatten_raw_segments(raw_segments):
        segment = resolve_segment(item, turns_by_id)
        if segment:
            resolved.append(segment)
    return resolved


def merge_turn_types(
    window_segments: Sequence[Sequence[Dict[str, Any]]],
    turns: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Later windows overwrite overlapping turn IDs, then rebuild consecutive segments."""
    type_by_id: Dict[str, str] = {}
    for segments in window_segments:
        for segment in segments:
            kind = str(segment.get("type") or "").strip().lower()
            if kind not in SEGMENT_TYPES:
                continue
            for tid in segment.get("turn_ids") or []:
                token = str(tid).strip()
                if token:
                    type_by_id[token] = kind
    rebuilt: List[Dict[str, Any]] = []
    current_type: Optional[str] = None
    current_ids: List[str] = []
    turns_by_id = _turns_by_id(turns)

    def flush() -> None:
        nonlocal current_type, current_ids
        if current_type and current_ids:
            resolved = resolve_segment(
                {"type": current_type, "turn_ids": current_ids},
                turns_by_id,
            )
            if resolved:
                rebuilt.append(resolved)
        current_type = None
        current_ids = []

    for turn in turns:
        tid = str(turn.get("turn_id") or "").strip()
        kind = type_by_id.get(tid)
        if not kind:
            flush()
            continue
        if current_type != kind:
            flush()
            current_type = kind
            current_ids = [tid]
        else:
            current_ids.append(tid)
    flush()
    return rebuilt


def time_windows(
    turns: Sequence[Dict[str, Any]],
    window_seconds: float = WINDOW_SECONDS,
    overlap_seconds: float = OVERLAP_SECONDS,
) -> List[List[Dict[str, Any]]]:
    if not turns:
        return []
    try:
        start = float(turns[0].get("start") or 0.0)
        end = float(turns[-1].get("end") or start)
    except (TypeError, ValueError):
        return [list(turns)]
    windows: List[List[Dict[str, Any]]] = []
    cursor = start
    while cursor < end:
        window_end = cursor + window_seconds
        chunk = [
            turn
            for turn in turns
            if float(turn.get("end") or turn.get("start") or 0.0) > cursor
            and float(turn.get("start") or 0.0) < window_end
        ]
        if chunk:
            windows.append(chunk)
        if window_end >= end:
            break
        cursor = window_end - overlap_seconds
    return windows or [list(turns)]


def split_until_fits(
    turns: Sequence[Dict[str, Any]],
    char_budget: int = CHAR_BUDGET,
) -> List[List[Dict[str, Any]]]:
    prompt = full_transcript_text(turns, include_turn_ids=True)
    if len(turns) <= 1 or len(prompt) <= char_budget:
        return [list(turns)]
    mid = max(1, len(turns) // 2)
    return split_until_fits(turns[:mid], char_budget) + split_until_fits(turns[mid:], char_budget)


def chunks_for_budget(
    turns: Sequence[Dict[str, Any]],
    char_budget: int = CHAR_BUDGET,
    window_seconds: float = WINDOW_SECONDS,
    overlap_seconds: float = OVERLAP_SECONDS,
) -> List[List[Dict[str, Any]]]:
    prompt = full_transcript_text(turns, include_turn_ids=True)
    if len(prompt) <= char_budget:
        return [list(turns)]
    chunks: List[List[Dict[str, Any]]] = []
    for window in time_windows(turns, window_seconds, overlap_seconds):
        chunks.extend(split_until_fits(window, char_budget))
    return chunks or [list(turns)]


def pairs_from_segments(
    segments: Sequence[Dict[str, Any]],
    turns: Sequence[Dict[str, Any]],
    max_pairs: int = MAX_PAIRS,
) -> List[Dict[str, Any]]:
    turns_by_id = _turns_by_id(turns)
    pairs: List[Dict[str, Any]] = []
    index = 0
    while index < len(segments) and len(pairs) < max_pairs:
        segment = segments[index]
        if str(segment.get("type") or "") not in QUESTION_TYPES:
            index += 1
            continue
        answer: Optional[Dict[str, Any]] = None
        if index + 1 < len(segments) and str(segments[index + 1].get("type") or "") in ANSWER_TYPES:
            answer = segments[index + 1]
        question_turns = [turns_by_id[tid] for tid in (segment.get("turn_ids") or []) if tid in turns_by_id]
        first_q = question_turns[0] if question_turns else {}
        answer_turns = []
        if answer:
            answer_turns = [turns_by_id[tid] for tid in (answer.get("turn_ids") or []) if tid in turns_by_id]
        pairs.append(
            {
                "question": str(segment.get("text") or "").strip(),
                "answer": str((answer or {}).get("text") or "").strip(),
                "question_start": segment.get("start"),
                "question_end": segment.get("end"),
                "answer_start": answer.get("start") if answer else None,
                "answer_end": answer.get("end") if answer else None,
                "panel_speaker": first_q.get("speaker_id"),
                "panel_label": segment.get("speaker") or first_q.get("label") or "PANEL_01",
            }
        )
        index += 2 if answer else 1
    return pairs


def apply_structure_to_turns(
    turns: Sequence[Dict[str, Any]],
    segments: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    type_by_id: Dict[str, str] = {}
    for segment in segments:
        kind = str(segment.get("type") or "").strip().lower()
        if kind not in SEGMENT_TYPES:
            continue
        for tid in segment.get("turn_ids") or []:
            type_by_id[str(tid)] = kind
    updated: List[Dict[str, Any]] = []
    for turn in turns:
        row = dict(turn)
        tid = str(row.get("turn_id") or "").strip()
        if tid in type_by_id:
            row["phase"] = type_by_id[tid]
        updated.append(row)
    return updated


def heuristic_segments(
    turns: Sequence[Dict[str, Any]],
    pairs: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Fallback structure from the one-way panel-voice heuristic."""
    if not turns:
        return []
    pair_list = list(pairs) if pairs is not None else pair_question_answers(turns)
    turns_by_id = _turns_by_id(turns)
    used: set[str] = set()
    segments: List[Dict[str, Any]] = []

    qa_start = None
    for turn in turns:
        if str(turn.get("role")) == "panel":
            qa_start = turn.get("start")
            break
    opening = [
        turn
        for turn in turns
        if qa_start is None or turn.get("start") is None or float(turn.get("start")) < float(qa_start)
    ]
    if opening:
        resolved = resolve_segment(
            {"type": "presentation", "turn_ids": [str(t.get("turn_id")) for t in opening if t.get("turn_id")]},
            turns_by_id,
        )
        if resolved:
            segments.append(resolved)
            used.update(resolved["turn_ids"])

    for pair in pair_list:
        q_turn = next(
            (
                turn
                for turn in turns
                if str(turn.get("role")) == "panel"
                and turn.get("start") == pair.get("question_start")
                and str(turn.get("turn_id") or "") not in used
            ),
            None,
        )
        if q_turn and q_turn.get("turn_id"):
            resolved = resolve_segment(
                {"type": "panel_question", "turn_ids": [str(q_turn["turn_id"])]},
                turns_by_id,
            )
            if resolved:
                segments.append(resolved)
                used.update(resolved["turn_ids"])
        if pair.get("answer"):
            a_ids = [
                str(turn.get("turn_id"))
                for turn in turns
                if str(turn.get("role")) == "student"
                and turn.get("turn_id")
                and str(turn.get("turn_id")) not in used
                and pair.get("answer_start") is not None
                and pair.get("answer_end") is not None
                and turn.get("start") is not None
                and turn.get("end") is not None
                and float(turn["start"]) >= float(pair["answer_start"])
                and float(turn["end"]) <= float(pair["answer_end"]) + 1e-6
            ]
            if a_ids:
                resolved = resolve_segment({"type": "student_answer", "turn_ids": a_ids}, turns_by_id)
                if resolved:
                    segments.append(resolved)
                    used.update(resolved["turn_ids"])

    leftover_ids: List[str] = []
    leftover_type: Optional[str] = None
    for turn in turns:
        tid = str(turn.get("turn_id") or "")
        if not tid or tid in used:
            if leftover_ids and leftover_type:
                resolved = resolve_segment(
                    {"type": leftover_type, "turn_ids": leftover_ids},
                    turns_by_id,
                )
                if resolved:
                    segments.append(resolved)
                leftover_ids = []
                leftover_type = None
            continue
        kind = "presentation" if str(turn.get("phase")) in PRESENTATION_PHASES else "panel_question" if str(turn.get("role")) == "panel" else "student_answer"
        if leftover_type != kind:
            if leftover_ids and leftover_type:
                resolved = resolve_segment(
                    {"type": leftover_type, "turn_ids": leftover_ids},
                    turns_by_id,
                )
                if resolved:
                    segments.append(resolved)
            leftover_type = kind
            leftover_ids = [tid]
        else:
            leftover_ids.append(tid)
    if leftover_ids and leftover_type:
        resolved = resolve_segment({"type": leftover_type, "turn_ids": leftover_ids}, turns_by_id)
        if resolved:
            segments.append(resolved)

    segments.sort(key=lambda item: (item.get("start") is None, item.get("start") or 0.0))
    return segments


def _refresh_counts(conversation: Dict[str, Any]) -> Dict[str, Any]:
    turns = conversation.get("turns") or []
    pairs = conversation.get("pair_candidates") or []
    conversation["turn_count"] = len(turns)
    conversation["pair_count"] = len(pairs)
    conversation["has_panel"] = any(turn.get("role") == "panel" for turn in turns)
    conversation["qa_start"] = next(
        (turn.get("start") for turn in turns if str(turn.get("phase")) in QA_PHASES),
        None,
    )
    conversation["presentation_turn_count"] = sum(
        1 for turn in turns if str(turn.get("phase")) in PRESENTATION_PHASES
    )
    conversation["qa_turn_count"] = sum(1 for turn in turns if str(turn.get("phase")) in QA_PHASES)
    labeled = full_transcript_text(turns)
    conversation["full_transcript"] = labeled
    conversation["labeled_transcript"] = labeled
    return conversation


def _chat_url() -> str:
    _load_env_files()
    base = (os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL") or os.getenv("VIVA_LLM_BASE_URL") or "https://api.groq.com/openai/v1").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _call_groq_structure(transcript: str, api_key: str, model: str) -> str:
    last_error: Optional[BaseException] = None
    for candidate in _model_candidates(model):
        body = {
            "model": candidate,
            "temperature": 0.1,
            "stream": False,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Classify this viva transcript. Use only the given turn IDs.\n\n"
                        + transcript
                    ),
                },
            ],
        }
        request = urllib.request.Request(
            _chat_url(),
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "GradexVivaEvaluationEngine/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                raw = json.loads(response.read().decode("utf-8"))
            return str(raw["choices"][0]["message"]["content"])
        except urllib.error.HTTPError as exc:
            last_error = exc
            try:
                err_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = str(exc.reason or exc)
            lowered = err_body.lower()
            if exc.code == 404 or (
                exc.code == 400 and ("model" in lowered or "not exist" in lowered or "not found" in lowered)
            ):
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("Groq structure call failed")


def _analyze_chunk(
    turns: Sequence[Dict[str, Any]],
    *,
    api_key: str,
    model: str,
    groq_call: GroqCall,
    debug: bool = False,
) -> Optional[List[Dict[str, Any]]]:
    transcript = full_transcript_text(turns, include_turn_ids=True)
    last_error = "LLM response failed schema validation"
    for attempt in range(2):
        try:
            content = groq_call(transcript, api_key, model)
            parsed = _extract_json_object(content)
            if not isinstance(parsed, dict):
                last_error = "LLM response was not a JSON object"
                if debug:
                    print(f"[conversation_understanding] attempt {attempt + 1}: {last_error}")
                continue
            resolved = resolve_segments(parsed.get("segments"), turns)
            if not resolved:
                last_error = "LLM response had no valid segments"
                if debug:
                    print(f"[conversation_understanding] attempt {attempt + 1}: {last_error}")
                continue
            return resolved
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
            TypeError,
        ) as exc:
            last_error = str(exc)
            if debug:
                print(f"[conversation_understanding] attempt {attempt + 1} failed: {exc}")
    if debug:
        print(f"[conversation_understanding] chunk failed: {last_error}")
    return None


def understand_conversation(
    turns: Sequence[Dict[str, Any]],
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    groq_call: GroqCall = _call_groq_structure,
    debug: bool = False,
    char_budget: int = CHAR_BUDGET,
    window_seconds: float = WINDOW_SECONDS,
    overlap_seconds: float = OVERLAP_SECONDS,
) -> Dict[str, Any]:
    labeled_turns = assign_turn_ids(turns) if turns and not turns[0].get("turn_id") else list(turns)
    if not any(str(turn.get("role")) == "panel" for turn in labeled_turns):
        return {
            "status": "skipped",
            "source": "heuristic",
            "reason": "no_panel",
            "segments": heuristic_segments(labeled_turns, []),
            "model": None,
        }

    key = api_key if api_key is not None else _api_key()
    chosen_model = model or _model_name()
    if not key:
        return {
            "status": "fallback",
            "source": "heuristic",
            "error": "No LLM API key configured (set AI_API_KEY or GROQ_API_KEY)",
            "segments": heuristic_segments(labeled_turns),
            "model": None,
        }

    chunks = chunks_for_budget(
        labeled_turns,
        char_budget=char_budget,
        window_seconds=window_seconds,
        overlap_seconds=overlap_seconds,
    )
    window_results: List[List[Dict[str, Any]]] = []
    for chunk in chunks:
        resolved = _analyze_chunk(
            chunk,
            api_key=key,
            model=chosen_model,
            groq_call=groq_call,
            debug=debug,
        )
        if resolved is None:
            return {
                "status": "fallback",
                "source": "heuristic",
                "error": "Conversation analyzer unavailable or returned invalid JSON",
                "segments": heuristic_segments(labeled_turns),
                "model": chosen_model,
            }
        window_results.append(resolved)

    segments = merge_turn_types(window_results, labeled_turns) if len(window_results) > 1 else window_results[0]
    return {
        "status": "success",
        "source": "llm",
        "model": chosen_model,
        "segments": segments,
        "window_count": len(chunks),
    }


def apply_conversation_understanding(
    conversation: Dict[str, Any],
    *,
    debug: bool = False,
    groq_call: GroqCall = _call_groq_structure,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    updated = dict(conversation)
    turns = list(updated.get("turns") or [])
    if turns and not turns[0].get("turn_id"):
        turns = assign_turn_ids(turns)
        updated["turns"] = turns

    heuristic_pairs = list(updated.get("pair_candidates") or pair_question_answers(turns))
    has_panel = any(str(turn.get("role")) == "panel" for turn in turns)

    if not has_panel:
        if turns:
            updated["pair_candidates"] = []
            reason = "no_panel"
        else:
            reason = "no_turns"
        updated["structure"] = {
            "status": "skipped",
            "source": "heuristic",
            "reason": reason,
            "segments": heuristic_segments(turns, [] if turns else heuristic_pairs),
            "model": None,
        }
        return _refresh_counts(updated)

    structure = understand_conversation(
        turns,
        api_key=api_key,
        model=model,
        groq_call=groq_call,
        debug=debug,
    )
    if structure.get("source") == "llm" and structure.get("segments"):
        turns = apply_structure_to_turns(turns, structure["segments"])
        updated["turns"] = turns
        updated["pair_candidates"] = pairs_from_segments(structure["segments"], turns)
        updated["structure"] = structure
        return _refresh_counts(updated)

    fallback_segments = structure.get("segments") or heuristic_segments(turns, heuristic_pairs)
    updated["pair_candidates"] = heuristic_pairs
    updated["structure"] = {
        "status": "fallback",
        "source": "heuristic",
        "error": structure.get("error"),
        "segments": fallback_segments,
        "model": structure.get("model"),
    }
    return _refresh_counts(updated)
