"""Follow-up question generation + ranking. Isolated Groq client."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from Gradex_AI_Server.app.viva_copilot.answer_detector import normalize_answer
from Gradex_AI_Server.app.viva_copilot.groq_client import (
    api_key,
    chat_model,
    extract_json_object,
    groq_chat,
)

DIFFICULTIES = frozenset({"basic", "intermediate", "advanced"})
PRIORITIES = frozenset({"high", "medium", "low"})
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

SYSTEM_PROMPT = """You are an AI Interviewer Copilot.

Your role is to assist the interviewer during a live
technical interview or viva.

Analyze the candidate's latest answer (or presentation) and identify
important technical areas, claims, assumptions, knowledge
gaps, or unexplored concepts that can be evaluated through
follow-up questions.

Generate relevant follow-up questions that the interviewer
can ask next.

Rules:

1. Do NOT answer the candidate's question.
2. Do NOT generate questions unrelated to the candidate's answer or presentation.
3. Questions must be directly derived from the candidate's response.
4. Prioritize questions that test understanding rather than memorization.
5. Identify unsupported claims or areas requiring clarification.
6. Generate questions at different difficulty levels when appropriate.
7. Avoid repeating questions already asked.
8. Consider the previous interview conversation.
9. Questions must sound natural for a human interviewer.
10. Do not assume facts that are not present in the context.
11. Keep questions concise enough for a live interview.
12. If the candidate gives a weak or incomplete answer, generate
    clarification questions.
13. If the candidate gives a strong answer, generate deeper
    technical questions.
14. Prefer questions that allow the interviewer to evaluate the
    candidate's actual understanding.
15. Do not generate more than 3 follow-up questions.
16. Rank the questions by usefulness to the interviewer.

Return ONLY valid JSON using this structure:

{
  "analysis": {
    "topics": [],
    "concepts": [],
    "technologies": [],
    "claims": [],
    "gaps": []
  },
  "main_points": [],
  "suggestions": [
    {
      "question": "string",
      "reason": "string",
      "difficulty": "basic | intermediate | advanced",
      "priority": "high | medium | low"
    }
  ]
}
"""

ChatFn = Callable[[str, Dict[str, Any]], str]


def _default_chat(system_prompt: str, payload: Dict[str, Any]) -> str:
    key = api_key()
    if not key:
        raise RuntimeError("No LLM API key configured (set AI_API_KEY or GROQ_API_KEY)")
    return groq_chat(system_prompt, payload, api_key_value=key, model=chat_model())


def _as_str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    items: List[str] = []
    for item in value:
        text = str(item).strip() if item is not None else ""
        if text:
            items.append(text[:240])
    return items[:12]


def validate_analysis(payload: Any) -> Dict[str, List[str]]:
    raw = payload if isinstance(payload, dict) else {}
    return {
        "topics": _as_str_list(raw.get("topics")),
        "concepts": _as_str_list(raw.get("concepts")),
        "technologies": _as_str_list(raw.get("technologies")),
        "claims": _as_str_list(raw.get("claims")),
        "gaps": _as_str_list(raw.get("gaps")),
    }


def _similar(a: str, b: str) -> bool:
    na = normalize_answer(a)
    nb = normalize_answer(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    wa = set(na.split())
    wb = set(nb.split())
    if not wa or not wb:
        return False
    overlap = len(wa & wb) / max(len(wa), len(wb))
    return overlap >= 0.85


def validate_suggestions(payload: Any, asked: Optional[List[str]] = None) -> List[Dict[str, str]]:
    if not isinstance(payload, list):
        return []
    asked = asked or []
    seen: List[str] = []
    out: List[Dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        reason = str(item.get("reason") or "").strip()
        difficulty = str(item.get("difficulty") or "").strip().lower()
        priority = str(item.get("priority") or "").strip().lower()
        if not question or not reason:
            continue
        if difficulty not in DIFFICULTIES or priority not in PRIORITIES:
            continue
        if any(_similar(question, prev) for prev in asked + seen):
            continue
        seen.append(question)
        out.append(
            {
                "question": question[:320],
                "reason": reason[:400],
                "difficulty": difficulty,
                "priority": priority,
            }
        )
    out.sort(key=lambda row: (PRIORITY_RANK.get(row["priority"], 9), row["difficulty"]))
    return out[:3]


def parse_followup_payload(raw_text: str, asked: Optional[List[str]] = None) -> Dict[str, Any]:
    parsed = extract_json_object(raw_text) or {}
    return {
        "analysis": validate_analysis(parsed.get("analysis")),
        "main_points": _as_str_list(parsed.get("main_points")),
        "suggestions": validate_suggestions(parsed.get("suggestions"), asked),
    }


def generate_followups(
    context: Dict[str, Any],
    asked: Optional[List[str]] = None,
    *,
    chat: ChatFn = _default_chat,
) -> Dict[str, Any]:
    content = chat(SYSTEM_PROMPT, context)
    return parse_followup_payload(content, asked)
