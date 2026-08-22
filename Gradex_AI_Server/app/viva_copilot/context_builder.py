"""Sliding interview context for follow-up generation. No RAG."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


MAX_QA_PAIRS = 5


def build_llm_context(
    *,
    session_id: str,
    project_context: Optional[Dict[str, Any]] = None,
    current_question: Optional[str] = None,
    candidate_answer: Optional[str] = None,
    recent_qa: Optional[List[Dict[str, str]]] = None,
    presentation_points: Optional[List[str]] = None,
    presentation_excerpt: Optional[str] = None,
) -> Dict[str, Any]:
    pairs = list(recent_qa or [])[-MAX_QA_PAIRS:]
    excerpt = (presentation_excerpt or "").strip()
    if len(excerpt) > 4000:
        excerpt = excerpt[-4000:]
    return {
        "sessionId": session_id,
        "projectContext": project_context or {},
        "presentationPoints": list(presentation_points or [])[:12],
        "presentationExcerpt": excerpt,
        "currentQuestion": {"text": (current_question or "").strip()} if current_question else None,
        "candidateAnswer": {"text": (candidate_answer or "").strip()} if candidate_answer else None,
        "recentConversation": [
            {"speaker": item.get("speaker", "candidate"), "text": item.get("text", "")}
            for item in _flatten_pairs(pairs)
        ],
    }


def _flatten_pairs(pairs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    turns: List[Dict[str, str]] = []
    for pair in pairs:
        question = (pair.get("question") or "").strip()
        answer = (pair.get("answer") or "").strip()
        if question:
            turns.append({"speaker": "interviewer", "text": question})
        if answer:
            turns.append({"speaker": "candidate", "text": answer})
    return turns[-10:]
