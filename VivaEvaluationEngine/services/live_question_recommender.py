"""Live Viva Question Recommender Service.

Analyzes live student transcript turns and viva context to recommend
probing questions for the viva examiner/teacher to ask next.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence


BLOOM_LEVELS = frozenset({"Understand", "Apply", "Analyze", "Evaluate", "Remember", "Create"})
DIFFICULTIES = frozenset({"basic", "intermediate", "advanced"})
PRIORITIES = frozenset({"high", "medium", "low"})
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

_ENV_LOADED = False


def _load_env_files() -> None:
    """Load local .env files if not already populated."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    engine_root = Path(__file__).resolve().parents[1]
    candidates = [
        engine_root / ".env",
        engine_root.parent / "Gradex_AI_Server" / "app" / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except OSError:
            continue


def get_api_key() -> Optional[str]:
    _load_env_files()
    for name in ("VIVA_LLM_API_KEY", "VIVA_COPILOT_API_KEY", "GROQ_API_KEY", "AI_API_KEY", "BACKUP_API_KEY"):
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def get_model_name() -> str:
    _load_env_files()
    return os.getenv("VIVA_COPILOT_LLM_MODEL") or os.getenv("VIVA_LLM_MODEL") or os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b"


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


def _extract_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    if not raw_text:
        return None
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


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


def get_llm_base_url() -> str:
    _load_env_files()
    base = (os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL") or os.getenv("VIVA_LLM_BASE_URL") or "https://api.groq.com/openai/v1").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _default_chat_call(system_prompt: str, payload: Dict[str, Any]) -> str:
    """Execute standard HTTPS POST to Groq / OpenAI compatible endpoint without extra third-party SDK."""
    import urllib.error
    import urllib.request

    key = get_api_key()
    if not key:
        raise RuntimeError("No LLM API key configured (set AI_API_KEY or GROQ_API_KEY)")

    model = get_model_name()
    body = {
        "model": model,
        "temperature": 0.2,
        "stream": False,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    req = urllib.request.Request(
        get_llm_base_url(),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "VivaEvaluationEngine/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=12) as response:
        data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]



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


def get_model_name() -> str:
    _load_env_files()
    return os.getenv("VIVA_COPILOT_LLM_MODEL") or os.getenv("VIVA_LLM_MODEL") or os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b"
