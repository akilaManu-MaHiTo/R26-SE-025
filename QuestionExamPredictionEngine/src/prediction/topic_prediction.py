"""Topic prediction helpers for future grading workflow work.

This module provides a lightweight, rule-based `predict_topics` function
that matches a student's answer against exam topics and question text.
It is intentionally dependency-free and designed as a sensible fallback
before more advanced ML models are added.
"""
from collections import Counter
import json
import re
from typing import List, Dict, Any, Union


_WORD_RE = re.compile(r"\w+")


def _tokens(text: str):
    return [t.lower() for t in _WORD_RE.findall(text or "")]


def _load_exam_data(exam_data: Union[None, str, Dict[str, Any]]):
    if exam_data is None:
        return None
    if isinstance(exam_data, str):
        try:
            with open(exam_data, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return exam_data


def predict_topics(answer: str, exam_data: Union[None, str, Dict[str, Any]] = None, top_n: int = 3) -> List[Dict[str, Any]]:
    """Predict likely topics for a free-text `answer` using `exam_data`.

    Parameters
    - answer: student's answer text
    - exam_data: exam JSON (or path) containing `questions` with `topic` and `parts`/`question` text
    - top_n: maximum number of topic candidates to return

    Returns: list of dicts: {"topic": str, "score": float, "matched_terms": [str,..]}

    The implementation uses simple token overlap between the answer and the
    concatenated topic/question text. Scores are normalized to [0,1].
    """
    exam = _load_exam_data(exam_data)
    answer_tokens = Counter(_tokens(answer))

    # Fallback: if no exam data provided, return empty list
    if not exam or "questions" not in exam:
        return []

    topic_texts = {}
    for q in exam.get("questions", []):
        topic = q.get("topic") or f"Q{q.get('question_number')}"
        parts = q.get("parts", [])
        combined = topic + " " + " ".join(str(p.get("question", "")) for p in parts)
        # accumulate text per topic (multiple questions may share topics)
        if topic in topic_texts:
            topic_texts[topic] += " " + combined
        else:
            topic_texts[topic] = combined

    candidates = []
    answer_unique_count = max(1, sum(answer_tokens.values()))

    for topic, text in topic_texts.items():
        t_tokens = Counter(_tokens(text))
        # compute overlap as intersection of token multiset
        matched = []
        overlap = 0
        for tok, cnt in answer_tokens.items():
            if tok in t_tokens:
                matched.append(tok)
                overlap += min(cnt, t_tokens[tok])

        score = overlap / answer_unique_count
        candidates.append({
            "topic": topic,
            "score": round(float(score), 4),
            "matched_terms": matched,
        })

    # sort by score desc
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_n]


__all__ = ["predict_topics"]