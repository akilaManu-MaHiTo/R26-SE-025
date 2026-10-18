"""Live Viva Question Recommender Service.

Analyzes live student transcript turns and viva context to recommend
probing questions for the viva examiner/teacher to ask next.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional, Sequence

from services.llm_common import (
    COPILOT_API_KEY_ENV_VARS,
    COPILOT_MODEL_ENV_VARS,
    extract_json_object as _extract_json_object,
    post_chat_completion,
    resolve_api_key,
    resolve_model_name,
)


BLOOM_LEVELS = frozenset({"Understand", "Apply", "Analyze", "Evaluate", "Remember", "Create"})
DIFFICULTIES = frozenset({"basic", "intermediate", "advanced"})
PRIORITIES = frozenset({"high", "medium", "low"})
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

def get_api_key() -> Optional[str]:
    return resolve_api_key(COPILOT_API_KEY_ENV_VARS)


def get_model_name() -> str:
    return resolve_model_name(COPILOT_MODEL_ENV_VARS)


SYSTEM_PROMPT = """You are an expert academic viva examiner copilot assistant.

Your task is to listen to the student's live presentation or viva response, identify technical claims, design decisions, and potential gaps, and recommend concise, probing follow-up questions for the examiner to ask next.

Guidelines:
1. Ground every question strictly in what the student said or the project context provided.
2. Focus on checking deep understanding vs superficial memorization.
3. Categorize each question with a valid Bloom's Taxonomy cognitive level:
   - "Understand": Clarifying concepts or explanations
   - "Apply": Handling real-world constraints or edge-cases
   - "Analyze": Examining trade-offs, architecture decisions, failure modes
   - "Evaluate": Defending choices against alternative approaches
4. Suggest a difficulty level: "basic", "intermediate", or "advanced".
5. Set priority: "high", "medium", or "low".
6. Provide a 1-sentence rationale explaining WHY the examiner should ask this question.
7. Avoid repeating questions that have already been asked.
8. Maximum 3 suggested questions.

Return STRICT JSON only matching this schema:
{
  "analysis": {
    "topics": ["Topic1", "Topic2"],
    "claims": ["Claim made by student"],
    "gaps": ["Unaddressed edge case or lack of justification"]
  },
  "recommendations": [
    {
      "question": "Clear, direct question for the examiner to ask?",
      "reason": "1-sentence reason why this tests depth of understanding.",
      "bloom_level": "Understand | Apply | Analyze | Evaluate",
      "difficulty": "basic | intermediate | advanced",
      "priority": "high | medium | low",
      "category": "Architecture | Concurrency | Security | Testing | Scalability | General"
    }
  ]
}
"""

ChatFn = Callable[[str, Dict[str, Any]], str]


def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", str(text or "").lower())
    return " ".join(cleaned.split())


def _is_similar(q1: str, q2: str) -> bool:
    n1, n2 = _normalize_text(q1), _normalize_text(q2)
    if not n1 or not n2:
        return False
    if n1 == n2 or n1 in n2 or n2 in n1:
        return True
    w1, w2 = set(n1.split()), set(n2.split())
    if not w1 or not w2:
        return False
    overlap = len(w1 & w2) / max(len(w1), len(w2))
    return overlap >= 0.80


def _default_chat_call(system_prompt: str, payload: Dict[str, Any]) -> str:
    """One chat-completion call to the configured OpenAI-compatible (Groq by default) endpoint."""
    key = get_api_key()
    if not key:
        raise RuntimeError("No LLM API key configured (set AI_API_KEY or GROQ_API_KEY)")

    body = {
        "model": get_model_name(),
        "temperature": 0.2,
        "stream": False,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    return post_chat_completion(body, key, timeout=12)


class LiveQuestionRecommender:
    """Engine service to generate live follow-up questions from student speech."""

    def __init__(self, chat_fn: Optional[ChatFn] = None) -> None:
        self._chat_fn = chat_fn or _default_chat_call

    def build_context(
        self,
        *,
        candidate_transcript: str,
        project_context: Optional[Dict[str, Any]] = None,
        recent_qa: Optional[Sequence[Dict[str, str]]] = None,
        asked_questions: Optional[Sequence[str]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Construct the bounded context window for recommendation generation."""
        qa_history = []
        for pair in (recent_qa or [])[-5:]:
            q = str(pair.get("question") or "").strip()
            a = str(pair.get("answer") or "").strip()
            if q or a:
                qa_history.append({"question": q, "answer": a})

        return {
            "sessionId": session_id or "live-viva",
            "projectContext": project_context or {},
            "candidateTranscript": str(candidate_transcript or "").strip()[-4000:],
            "recentQA": qa_history,
            "alreadyAsked": list(asked_questions or [])[-15:],
        }

    def parse_and_validate(
        self,
        raw_output: str,
        asked_questions: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Validate LLM output schema, normalize Bloom levels, and deduplicate."""
        parsed = _extract_json_object(raw_output) or {}
        analysis_raw = parsed.get("analysis") if isinstance(parsed.get("analysis"), dict) else {}
        
        analysis = {
            "topics": [str(t).strip()[:100] for t in (analysis_raw.get("topics") or []) if str(t).strip()][:8],
            "claims": [str(c).strip()[:200] for c in (analysis_raw.get("claims") or []) if str(c).strip()][:8],
            "gaps": [str(g).strip()[:200] for g in (analysis_raw.get("gaps") or []) if str(g).strip()][:8],
        }

        asked = list(asked_questions or [])
        recs_raw = parsed.get("recommendations") or parsed.get("suggestions") or []
        if not isinstance(recs_raw, list):
            recs_raw = []

        validated_recs: List[Dict[str, Any]] = []
        seen_questions: List[str] = []

        for item in recs_raw:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if not question:
                continue

            if any(_is_similar(question, prior) for prior in asked + seen_questions):
                continue

            bloom = str(item.get("bloom_level") or item.get("bloom") or "Analyze").strip().capitalize()
            if bloom not in BLOOM_LEVELS:
                bloom = "Analyze"

            difficulty = str(item.get("difficulty") or "intermediate").strip().lower()
            if difficulty not in DIFFICULTIES:
                difficulty = "intermediate"

            priority = str(item.get("priority") or "medium").strip().lower()
            if priority not in PRIORITIES:
                priority = "medium"

            category = str(item.get("category") or "Technical Depth").strip()[:50]

            seen_questions.append(question)
            validated_recs.append({
                "question": question[:350],
                "reason": (reason or "Evaluates student's technical depth on this topic.")[:350],
                "bloom_level": bloom,
                "difficulty": difficulty,
                "priority": priority,
                "category": category,
            })

        validated_recs.sort(key=lambda r: (PRIORITY_RANK.get(r["priority"], 9), r["difficulty"]))

        return {
            "status": "success",
            "analysis": analysis,
            "recommendations": validated_recs[:3],
        }

    def generate_fallback_recommendations(
        self,
        candidate_transcript: str,
        project_context: Optional[Dict[str, Any]] = None,
        asked_questions: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Generate structured heuristic questions when LLM is unavailable."""
        asked = list(asked_questions or [])
        proj = project_context or {}
        title = proj.get("project", "your project")

        candidates = [
            {
                "question": f"Can you walk us through the main architectural trade-offs you encountered while implementing {title}?",
                "reason": "Evaluates the candidate's understanding of higher-level system architecture.",
                "bloom_level": "Analyze",
                "difficulty": "intermediate",
                "priority": "high",
                "category": "Architecture",
            },
            {
                "question": "What is the single most critical failure point in this design, and how does the system recover?",
                "reason": "Tests edge-case handling, fault tolerance, and system resilience.",
                "bloom_level": "Evaluate",
                "difficulty": "advanced",
                "priority": "high",
                "category": "Resilience",
            },
            {
                "question": "How did you validate and test the core functionalities under concurrent or heavy loads?",
                "reason": "Tests verification rigor and scalability considerations.",
                "bloom_level": "Apply",
                "difficulty": "intermediate",
                "priority": "medium",
                "category": "Testing & QA",
            },
        ]

        filtered = [c for c in candidates if not any(_is_similar(c["question"], a) for a in asked)]

        return {
            "status": "fallback",
            "source": "heuristic",
            "analysis": {
                "topics": [title] if title != "your project" else ["System Architecture"],
                "claims": ["Heuristic fallback generated due to LLM offline status"],
                "gaps": ["Requires verification of core design assumptions"],
            },
            "recommendations": filtered[:3],
        }

    def recommend_questions(
        self,
        candidate_transcript: str,
        project_context: Optional[Dict[str, Any]] = None,
        recent_qa: Optional[Sequence[Dict[str, str]]] = None,
        asked_questions: Optional[Sequence[str]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Main entry point: generates live recommendations with automatic fallback."""
        text = (candidate_transcript or "").strip()
        if not text and not project_context:
            return {
                "status": "empty",
                "analysis": {"topics": [], "claims": [], "gaps": []},
                "recommendations": [],
            }

        context = self.build_context(
            candidate_transcript=text,
            project_context=project_context,
            recent_qa=recent_qa,
            asked_questions=asked_questions,
            session_id=session_id,
        )

        try:
            raw_response = self._chat_fn(SYSTEM_PROMPT, context)
            result = self.parse_and_validate(raw_response, asked_questions)
            if result.get("recommendations"):
                return result
        except Exception:
            pass

        return self.generate_fallback_recommendations(
            candidate_transcript=text,
            project_context=project_context,
            asked_questions=asked_questions,
        )

