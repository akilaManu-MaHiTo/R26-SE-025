"""Model providers for the v2 Question Knowledge Agent.

Providers wrap trained models and deterministic rules behind small typed
interfaces. Missing optional capabilities degrade to warnings and defined
fallbacks rather than failing the whole agent run.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.agents.contracts import AgentWarning, SourceCitation
from src.agents.v2.contracts import TopicMapping
from src.agents.v2.records import CourseRecord, QuestionRecord
from src.analysis.scoring.cognitive import detect_level

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_TOPICS_PATH = PROJECT_ROOT / "data" / "topics.json"

ModelProvider = Callable[[], tuple[Any | None, AgentWarning | None]]


def _load_canonical_topics(path: Path | None = None) -> list[str]:
    topics_path = path or CANONICAL_TOPICS_PATH
    try:
        with topics_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return [str(topic).strip() for topic in data if topic]
    except Exception:
        pass
    return []


_WORD_RE = re.compile(r"\w+", re.UNICODE)
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "how", "in", "into", "is", "it", "of", "on", "or", "that", "the",
    "their", "this", "to", "was", "what", "when", "which", "with", "why",
}


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in (value.lower() for value in _WORD_RE.findall(text or ""))
        if token not in _STOP_WORDS and len(token) > 1
    ]


@dataclass(frozen=True)
class BloomResult:
    level: str
    confidence: float
    used_model: bool


class RequiredBloomProvider:
    """Predicts the required Bloom level for a question.

    Uses the trained cognitive model when available and falls back to the
    deterministic keyword heuristic from ``detect_level`` otherwise.
    """

    def __init__(self, model_provider: ModelProvider | None = None):
        self._model_provider = model_provider

    def predict_question(self, text: str) -> tuple[BloomResult, list[AgentWarning]]:
        warnings: list[AgentWarning] = []
        if self._model_provider is not None:
            model, warning = self._model_provider()
            if warning:
                warnings.append(warning)
            if model is not None:
                level, confidence = model.predict_level(text)
                return BloomResult(str(level), float(confidence), True), warnings

        level, confidence = detect_level(text, "question")
        warnings.append(
            AgentWarning(
                code="bloom_fallback_used",
                message="Bloom model unavailable; keyword heuristic used",
                capability="required_bloom",
            )
        )
        return BloomResult(str(level), float(confidence), False), warnings


class RuleBasedTopicMapper:
    """Maps a question to canonical topics using declared/overlap evidence.

    Priority:
      1. Declared ``question.topic_id``.
      2. Token overlap between question text, rubric criteria, model answer,
         and each canonical topic.
      3. Token candidates when no canonical topics are configured or nothing
         matches. The caller treats the ``token`` mode as low confidence.
    """

    def __init__(
        self,
        canonical_topics: list[str] | None = None,
        min_score: float = 0.2,
    ):
        self.canonical_topics = list(
            canonical_topics
            if canonical_topics is not None
            else _load_canonical_topics()
        )
        self.min_score = min_score

    @staticmethod
    def _question_text(question: QuestionRecord) -> str:
        parts = [question.question_text]
        parts.extend(criterion.point for criterion in question.rubric_criteria)
        if question.model_answer:
            parts.append(question.model_answer)
        return " ".join(part for part in parts if part)

    def _token_candidates(self, tokens: list[str]) -> list[TopicMapping]:
        seen: list[str] = []
        for token in tokens:
            if token not in seen and len(token) > 3:
                seen.append(token)
            if len(seen) >= 3:
                break
        return [
            TopicMapping(topic_id=token, score=round(0.3 - 0.05 * index, 4))
            for index, token in enumerate(seen)
        ]

    def map_question(
        self,
        question: QuestionRecord,
        course: CourseRecord | None = None,
    ) -> tuple[list[TopicMapping], str]:
        """Return ``(mappings, mode)`` where mode is declared/canonical/token/empty."""
        if question.topic_id:
            return (
                [TopicMapping(topic_id=question.topic_id, score=1.0)],
                "declared",
            )

        tokens = _tokens(self._question_text(question))
        if not tokens:
            return [], "empty"

        if not self.canonical_topics:
            return self._token_candidates(tokens), "token"

        scored: list[TopicMapping] = []
        for topic in self.canonical_topics:
            topic_tokens = set(_tokens(topic))
            if not topic_tokens:
                continue
            overlap = sum(1 for token in tokens if token in topic_tokens)
            score = overlap / len(topic_tokens)
            if score >= self.min_score:
                scored.append(
                    TopicMapping(topic_id=topic, score=round(min(score, 1.0), 4))
                )

        if scored:
            scored.sort(key=lambda mapping: mapping.score, reverse=True)
            return scored[:5], "canonical"

        return self._token_candidates(tokens), "token"


QUESTION_TYPE_KEYWORDS: dict[str, list[str]] = {
    "definition": ["define", "what is", "state", "list", "identify", "name", "recall"],
    "explanation": ["explain", "describe", "summarize", "discuss", "interpret", "clarify", "outline"],
    "comparison": ["compare", "contrast", "differentiate", "distinguish", "difference"],
    "calculation": ["calculate", "compute", "solve", "determine the value"],
    "analysis": ["analyze", "examine", "investigate", "break down"],
    "evaluation": ["evaluate", "critique", "assess", "justify", "argue", "judge", "recommend"],
    "creation": ["design", "develop", "construct", "propose", "formulate", "synthesize", "create", "plan"],
    "application": ["apply", "implement", "demonstrate", "perform", "execute"],
}


class RuleBasedQuestionTypeClassifier:
    """Classifies the question structure (e.g. definition, explanation, comparison)."""

    def classify(self, text: str) -> tuple[str | None, float]:
        if not text or not text.strip():
            return None, 0.0
        lowered = text.lower()
        best_type: str | None = None
        best_matches = 0
        for question_type, keywords in QUESTION_TYPE_KEYWORDS.items():
            matches = sum(1 for keyword in keywords if keyword in lowered)
            if matches > best_matches:
                best_type = question_type
                best_matches = matches
        if best_type is None:
            return "general", 0.3
        confidence = min(0.5 + 0.1 * best_matches, 0.95)
        return best_type, round(confidence, 2)


class RuleBasedDifficultyEstimator:
    """Estimates question difficulty on a 1..5 scale.

    Combines the Bloom level, rubric criteria count, and maximum marks so the
    estimate is reproducible and independent of any model.
    """

    BLOOM_SCORES = {
        "remember": 1,
        "understand": 2,
        "apply": 3,
        "analyze": 4,
        "evaluate": 5,
        "create": 6,
    }

    def estimate(
        self,
        question: QuestionRecord,
        bloom_level: str | None = None,
        question_type: str | None = None,
    ) -> float:
        bloom_score = self.BLOOM_SCORES.get(bloom_level or "", 3) / 6.0
        criteria = min(len(question.rubric_criteria), 6) / 6.0
        marks = min(question.max_marks, 20) / 20.0
        raw = 0.5 * bloom_score + 0.3 * criteria + 0.2 * marks
        return round(1 + 4 * raw, 2)


class RubricEvidenceRetriever:
    """Baseline evidence retriever built from the rubric and model answer.

    This is the defined fallback when course-material retrieval is
    unavailable: citations come from the rubric document and model answer.
    """

    def retrieve(self, query: str, filters: dict[str, Any]) -> list[SourceCitation]:
        citations: list[SourceCitation] = []
        rubric_id = filters.get("rubric_id")
        filename = filters.get("rubric_filename")
        if rubric_id:
            citations.append(
                SourceCitation(
                    source_id=rubric_id,
                    source_path=filename or "rubric",
                    excerpt="",
                )
            )
        model_answer = filters.get("model_answer")
        if model_answer:
            citations.append(
                SourceCitation(
                    source_id=f"{rubric_id}:model-answer" if rubric_id else "model-answer",
                    source_path="model_answer",
                    excerpt=str(model_answer)[:200],
                )
            )
        return citations
