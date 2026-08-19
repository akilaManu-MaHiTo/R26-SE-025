"""Build panel/student conversation turns and a labeled timed transcript.

Turn construction is deterministic (diarized word times). Conversation
structure (presentation vs Q&A vs instruction) is filled later by the
LLM analyzer, with heuristic pairing kept only as fallback.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from services.diarization import assign_words_to_speakers, speaker_at


TURN_GAP_S = 1.2
MAX_PAIRS = 40

QA_PHASES = frozenset(
    {
        "qa",
        "panel_question",
        "student_answer",
        "follow_up_question",
        "follow_up_answer",
    }
)
PRESENTATION_PHASES = frozenset({"presentation", "return_to_presentation"})

_INTERROGATIVE_START = frozenset(
    {
        "what",
        "why",
        "how",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "whose",
        "did",
        "do",
        "does",
        "can",
        "could",
        "would",
        "will",
        "is",
        "are",
        "was",
        "were",
        "have",
        "has",
        "explain",
        "describe",
        "tell",
    }
)


def _word_token(item: Dict[str, Any]) -> str:
    return str(item.get("word") or item.get("text") or "").strip()


def _timed_items(
    words: Sequence[Dict[str, Any]],
    whisper_segments: Sequence[Dict[str, Any]],
    diar_segments: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    source = list(words or [])
    if not source:
        source = [
            {
                "word": str(seg.get("text") or "").strip(),
                "start": seg.get("start"),
                "end": seg.get("end"),
            }
            for seg in (whisper_segments or [])
            if str(seg.get("text") or "").strip()
        ]
    labeled = assign_words_to_speakers(source, diar_segments)
    items: List[Dict[str, Any]] = []
    for item in labeled:
        text = _word_token(item)
        if not text:
            continue
        try:
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start))
        except (TypeError, ValueError):
            continue
        speaker = item.get("speaker") or speaker_at(0.5 * (start + end), diar_segments) or "SPEAKER_00"
        items.append(
            {
                "text": text,
                "start": start,
                "end": end,
                "speaker": str(speaker),
            }
        )
    items.sort(key=lambda row: (row["start"], row["end"]))
    return items


def format_clock(seconds: Any) -> str:
    """Format seconds as mm:ss.xx for labeled transcripts."""
    try:
        total = max(0.0, float(seconds))
    except (TypeError, ValueError):
        total = 0.0
    mins = int(total // 60)
    remainder = total - mins * 60
    return f"{mins:02d}:{remainder:05.2f}"


def turn_id_for(index: int) -> str:
    return f"T{int(index):02d}"


def assign_turn_ids(turns: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    labeled: List[Dict[str, Any]] = []
    for index, turn in enumerate(turns):
        row = dict(turn)
        row["turn_id"] = turn_id_for(index)
        labeled.append(row)
    return labeled


def _panel_display_names(speaker_ids: Sequence[str], student_speaker: str) -> Dict[str, str]:
    panel_ids: List[str] = []
    for sid in speaker_ids:
        if sid != student_speaker and sid not in panel_ids:
            panel_ids.append(sid)
    return {sid: f"PANEL_{index + 1:02d}" for index, sid in enumerate(panel_ids)}


def build_turns(
    words: Sequence[Dict[str, Any]],
    diar_segments: Sequence[Dict[str, Any]],
    student_speaker: Optional[str],
    whisper_segments: Optional[Sequence[Dict[str, Any]]] = None,
    gap_seconds: float = TURN_GAP_S,
) -> List[Dict[str, Any]]:
    student_id = str(student_speaker or "SPEAKER_00")
    items = _timed_items(words, whisper_segments or [], diar_segments)
    if not items:
        return []

    ordered_speakers: List[str] = []
    for item in items:
        sid = str(item["speaker"])
        if sid not in ordered_speakers:
            ordered_speakers.append(sid)
    display = _panel_display_names(ordered_speakers, student_id)

    turns: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    tokens: List[str] = []

    def flush() -> None:
        nonlocal current, tokens
        if current is None:
            return
        text = " ".join(tokens).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            current["text"] = text
            current["end"] = round(float(current["end"]), 3)
            current["start"] = round(float(current["start"]), 3)
            turns.append(current)
        current = None
        tokens = []

    for item in items:
        speaker = str(item["speaker"])
        start = float(item["start"])
        end = float(item["end"])
        if current is None:
            role = "student" if speaker == student_id else "panel"
            current = {
                "start": start,
                "end": end,
                "speaker_id": speaker,
                "role": role,
                "label": "STUDENT" if role == "student" else display.get(speaker, "PANEL_01"),
            }
            tokens = [item["text"]]
            continue
        gap = start - float(current["end"])
        if speaker != current["speaker_id"] or gap > gap_seconds:
            flush()
            role = "student" if speaker == student_id else "panel"
            current = {
                "start": start,
                "end": end,
                "speaker_id": speaker,
                "role": role,
                "label": "STUDENT" if role == "student" else display.get(speaker, "PANEL_01"),
            }
            tokens = [item["text"]]
            continue
        tokens.append(item["text"])
        current["end"] = end

    flush()
    return annotate_phases(assign_turn_ids(turns))


def annotate_phases(turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Heuristic fallback: student speech is presentation until an off-camera voice appears."""
    qa_start = None
    for turn in turns:
        if str(turn.get("role")) == "panel":
            qa_start = turn.get("start")
            break
    for turn in turns:
        start = turn.get("start")
        if qa_start is None or start is None or float(start) < float(qa_start):
            turn["phase"] = "presentation"
        else:
            turn["phase"] = "qa"
    return turns


def full_transcript_text(
    turns: Sequence[Dict[str, Any]],
    *,
    include_turn_ids: bool = False,
) -> str:
    """Clean chronological transcript with role labels and start–end clocks."""
    blocks: List[str] = []
    for turn in turns:
        text = str(turn.get("text") or "").strip()
        if not text:
            continue
        label = str(turn.get("label") or ("STUDENT" if turn.get("role") == "student" else "PANEL_01"))
        start = format_clock(turn.get("start"))
        end = format_clock(turn.get("end") if turn.get("end") is not None else turn.get("start"))
        header = f"[{start} - {end}] {label}"
        if include_turn_ids:
            tid = str(turn.get("turn_id") or "").strip()
            if tid:
                header = f"{tid} {header}"
        blocks.append(f"{header}\n{text}")
    return "\n\n".join(blocks)


def _normalized_lead_tokens(text: str) -> List[str]:
    lowered = re.sub(r"[^\w\s']+", " ", text.lower())
    return [tok for tok in lowered.split() if tok]


def is_panel_question(turn: Dict[str, Any]) -> bool:
    if str(turn.get("role")) != "panel":
        return False
    text = str(turn.get("text") or "").strip()
    if not text:
        return False
    if "?" in text:
        return True
    tokens = _normalized_lead_tokens(text)
    if not tokens:
        return False
    if tokens[0] in _INTERROGATIVE_START:
        if tokens[0] == "tell":
            return len(tokens) > 1 and tokens[1] in {"me", "us"}
        return True
    return False


def pair_question_answers(
    turns: Sequence[Dict[str, Any]],
    max_pairs: int = MAX_PAIRS,
) -> List[Dict[str, Any]]:
    pairs: List[Dict[str, Any]] = []
    index = 0
    qa_started = False
    while index < len(turns) and len(pairs) < max_pairs:
        turn = turns[index]
        is_first_panel = (not qa_started) and str(turn.get("role")) == "panel"
        if is_first_panel:
            qa_started = True
        if not (is_first_panel or is_panel_question(turn)):
            index += 1
            continue
        qa_started = True
        answer_turns: List[Dict[str, Any]] = []
        cursor = index + 1
        while cursor < len(turns):
            nxt = turns[cursor]
            if is_panel_question(nxt):
                break
            if str(nxt.get("role")) == "student":
                answer_turns.append(nxt)
            cursor += 1
        answer_text = " ".join(str(item.get("text") or "").strip() for item in answer_turns).strip()
        answer_text = re.sub(r"\s+", " ", answer_text)
        pair: Dict[str, Any] = {
            "question": str(turn.get("text") or "").strip(),
            "answer": answer_text,
            "question_start": turn.get("start"),
            "question_end": turn.get("end"),
            "answer_start": answer_turns[0]["start"] if answer_turns else None,
            "answer_end": answer_turns[-1]["end"] if answer_turns else None,
            "panel_speaker": turn.get("speaker_id"),
            "panel_label": turn.get("label") or "PANEL_01",
        }
        pairs.append(pair)
        index = cursor if cursor > index else index + 1
    return pairs


def build_conversation(
    words: Sequence[Dict[str, Any]],
    diar_segments: Sequence[Dict[str, Any]],
    student_speaker: Optional[str],
    whisper_segments: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    turns = build_turns(
        words=words,
        diar_segments=diar_segments,
        student_speaker=student_speaker,
        whisper_segments=whisper_segments,
    )
    pairs = pair_question_answers(turns)
    labeled = full_transcript_text(turns)
    qa_start = next((turn.get("start") for turn in turns if turn.get("phase") in QA_PHASES), None)
    presentation_turns = [turn for turn in turns if turn.get("phase") in PRESENTATION_PHASES]
    qa_turns = [turn for turn in turns if turn.get("phase") in QA_PHASES]
    return {
        "turns": turns,
        "pair_candidates": pairs,
        "turn_count": len(turns),
        "pair_count": len(pairs),
        "qa_start": qa_start,
        "has_panel": any(turn.get("role") == "panel" for turn in turns),
        "full_transcript": labeled,
        "labeled_transcript": labeled,
        "presentation_turn_count": len(presentation_turns),
        "qa_turn_count": len(qa_turns),
        "structure": {
            "status": "pending",
            "source": "heuristic",
            "segments": [],
        },
    }
