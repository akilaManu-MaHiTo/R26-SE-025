import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from app.classifier.rules import classify_by_rules
from app.config import settings
from app.analytics.taxonomy import TOPICS
from app.llm.ollama import OllamaUnavailable, validate_with_retry
from app.llm.roles.classify import ClassificationResponse
from app.llm.roles.misconceptions import MisconceptionSummary
from app.llm.roles.student_analysis import QuestionSemantics, StudentInsightResponse
from app.llm.roles.study_actions import StudyActions

logger = logging.getLogger(__name__)

_LOOP_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm-service")
_EMBEDDER = None


def _run_coroutine(coro_factory):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())
    return _LOOP_EXECUTOR.submit(asyncio.run, coro_factory()).result()


def _rules_dict(result) -> dict:
    return {
        "topic_assignments": [
            {"topic": a.topic, "weight": a.weight} for a in result.topic_assignments
        ],
        "bloom_level": result.bloom_level,
        "question_type": result.question_type,
        "key_concepts": result.key_concepts,
        "confidence": result.confidence,
    }


def _try_bloom_model(question_text: str) -> dict:
    """Bloom ModernBERT ONLY: mandatory ModernBERT prediction, no threshold/fallback."""
    from app.classifier.bloom_classifier import is_bloom_model_available, predict_bloom

    if not is_bloom_model_available():
        raise RuntimeError(
            f"Bloom ModernBERT not available at {settings.bloom_model_dir} — "
            "ensure models/bloom_modernbert/bloom.safetensors + tokenizer exist"
        )
    bloom = predict_bloom(question_text)
    # No confidence threshold — always trust ModernBERT top-1 prediction
    logger.info(
        "Bloom ModernBERT prediction: %s (%.3f) for %r",
        bloom["level"],
        bloom["confidence"],
        question_text[:80],
    )
    return bloom


def classify_question(question_text: str) -> dict:
    """Classify question: topic from rules, Bloom level ONLY from bloom_modernbert."""
    rules_result = classify_by_rules(question_text)
    rules = _rules_dict(rules_result)
    try:
        bloom = _try_bloom_model(question_text)
    except Exception as exc:
        logger.warning("Bloom ModernBERT inference failed: %s", exc)
        # No fallback to rules/Qwen for Bloom — surface error explicitly
        return {"status": "bloom_error", "rules": rules, "reason": str(exc), "bloom": None}
    # Overwrite Bloom level with ModernBERT prediction regardless of rules confidence
    rules_with_bloom = {**rules, "bloom_level": bloom["level"]}
    return {"status": "bloom_model", "rules": rules_with_bloom, "bloom": bloom}


async def misconception_summary(topic: str, criteria: list[dict], answers: list[str]) -> dict:
    prompt = (
        f"Summarize likely misconceptions for topic '{topic}' in a DBMS course.\n"
        f"Rubric criteria: {criteria}\nAnonymized answer excerpts: {answers}\n"
        "Respond ONLY with JSON matching: "
        '{"topic": str, "misconceptions": [{"statement": str, "evidence": str, '
        '"confidence": "confirmed"|"inferred_low_confidence"}], "source_summary": str}'
    )
    try:
        parsed, raw, review = await validate_with_retry(
            MisconceptionSummary, prompt, temperature=settings.ollama_classify_temperature
        )
    except OllamaUnavailable:
        return {"status": "degraded", "reason": "ollama_unavailable"}
    if parsed is None:
        return {"status": "degraded", "reason": "schema_failure", "review_flag": True, "raw": raw}
    return {"status": "ok", **parsed.model_dump()}


async def study_actions(student_key: str, weak_topics: list[str], evidence: dict) -> dict:
    prompt = (
        f"Student {student_key} showed weakness in: {weak_topics}.\n"
        f"Evidence: {evidence}\n"
        "Respond ONLY with JSON matching: "
        '{"student_key": str, "actions": [{"action": str, "topic": str, "rationale": str, '
        '"practice_topics": [str]}]}'
    )
    try:
        parsed, raw, review = await validate_with_retry(
            StudyActions, prompt, temperature=settings.ollama_classify_temperature
        )
    except OllamaUnavailable:
        return {"status": "degraded", "reason": "ollama_unavailable"}
    if parsed is None:
        return {"status": "degraded", "reason": "schema_failure", "review_flag": True, "raw": raw}
    return {"status": "ok", **parsed.model_dump()}


async def classify_question_semantics(
    course: dict, question: str, criteria: list[str]
) -> dict:
    prompt = (
        "Classify the semantics of the supplied examination question. "
        "The supplied course, question, and rubric criteria are authoritative backend evidence. "
        "Do not alter or invent that evidence. The response schema contains no score, percentage, "
        "marks, average, or other numeric performance calculations; do not perform any.\n"
        "Respond ONLY with JSON matching this schema:\n"
        '{"level": "Remember|Understand|Apply|Analyze|Evaluate|Create", "topic": str, '
        '"subtopic": str, "confidence": float, "reason": str}\n'
        f"COURSE: {json.dumps(course, ensure_ascii=False)}\n"
        f"QUESTION: {json.dumps(question, ensure_ascii=False)}\n"
        f"RUBRIC_CRITERIA: {json.dumps(criteria, ensure_ascii=False)}"
    )
    try:
        parsed, _raw, _review = await validate_with_retry(
            QuestionSemantics,
            prompt,
            temperature=settings.ollama_classify_temperature,
        )
    except OllamaUnavailable:
        return {"status": "degraded", "reason": "ollama_unavailable"}
    if parsed is None:
        return {"status": "degraded", "reason": "schema_failure"}
    return {"status": "ok", "semantics": parsed.model_dump()}


async def generate_student_insights(student_id: str, evidence: dict) -> dict:
    prompt = (
        "Generate qualitative student learning insights from the supplied backend evidence. "
        "The student identifier and backend evidence are authoritative; do not recalculate, alter, "
        "or invent evidence. The response schema contains no score, percentage, marks, average, or "
        "other numeric performance calculations; perform no numeric performance calculations.\n"
        "Respond ONLY with JSON matching this schema:\n"
        '{"learning_gaps": [str], "recommendations": [{"priority": "High|Medium|Low", '
        '"topic": str, "bloom_level": "Remember|Understand|Apply|Analyze|Evaluate|Create", '
        '"action": str}], "generation_target": {"recommended_bloom_level": '
        '"Remember|Understand|Apply|Analyze|Evaluate|Create", "recommended_difficulty": '
        '"Easy|Medium|Hard", "recommended_topics": [str]}}\n'
        "Example output:\n"
        '{"learning_gaps": ["Review Describes Type-4 (Thin Driver) in Java Database Connectivity (JDBC)."], '
        '"recommendations": [{"priority": "High", "topic": "SQL", "bloom_level": "Understand", '
        '"action": "Review SQL and practice Understand questions."}], "generation_target": '
        '{"recommended_bloom_level": "Understand", "recommended_difficulty": "Medium", '
        '"recommended_topics": ["SQL", "Java Database Connectivity (JDBC)"]}}\n'
        f"STUDENT_ID: {json.dumps(student_id, ensure_ascii=False)}\n"
        f"BACKEND_EVIDENCE: {json.dumps(evidence, ensure_ascii=False)}"
    )
    try:
        parsed, _raw, _review = await validate_with_retry(
            StudentInsightResponse,
            prompt,
            temperature=settings.ollama_generate_temperature,
        )
    except OllamaUnavailable:
        return {"status": "degraded", "reason": "ollama_unavailable"}
    if parsed is None:
        return {"status": "degraded", "reason": "schema_failure"}
    return {"status": "ok", **parsed.model_dump()}


def is_embedding_available() -> bool:
    if not settings.embedding_available:
        return False
    return _get_embedder().is_available()


async def generate_practice_questions(target: dict) -> dict:
    from app.llm.roles.generate_practice import PracticeQuestions

    prompt = (
        "Generate practice DBMS questions for a student using only the supplied targeting. "
        "The target is authoritative; do not perform any numeric calculations.\n"
        "Respond ONLY with JSON matching this schema:\n"
        '{"requested_count": int, "questions": [{"prompt": str, "bloom_level": '
        '"Remember|Understand|Apply|Analyze|Evaluate|Create", "topic": str, '
        '"difficulty": "Easy|Medium|Hard", "hints": [str]}]}\n'
        f"TARGET: {json.dumps(target, ensure_ascii=False)}"
    )
    try:
        parsed, _raw, _review = await validate_with_retry(
            PracticeQuestions, prompt, temperature=settings.ollama_generate_temperature, timeout=30
        )
    except OllamaUnavailable:
        return {"status": "degraded", "reason": "ollama_unavailable"}
    if parsed is None:
        return {"status": "degraded", "reason": "schema_failure"}
    return {"status": "ok", "questions": [q.model_dump() for q in parsed.questions]}


async def generate_candidates(recommendation: dict, count: int = 3) -> dict:
    from app.llm.roles.generate import CandidateQuestions

    prompt = (
        f"Generate {count} new DBMS examination questions for topic "
        f"'{recommendation['topic']}' at Bloom level '{recommendation['bloom_level']}' "
        f"with marks in range {recommendation.get('mark_range')}.\n"
        "They must be original and not copy the following historical questions:\n"
        f"{recommendation.get('historical_questions', [])}\n"
        "Respond ONLY with JSON matching: "
        '{"target_topic": str, "target_bloom": str, "requested_count": int, '
        '"candidates": [{"text": str, "topic": str, "bloom_level": str, "marks": float, '
        '"rationale": str, "model_answer": str, "rubric_criteria": [str]}]}'
    )
    try:
        parsed, raw, review = await validate_with_retry(
            CandidateQuestions, prompt, temperature=settings.ollama_generate_temperature, timeout=90
        )
    except OllamaUnavailable:
        return {"status": "degraded", "reason": "ollama_unavailable"}
    if parsed is None:
        return {"status": "degraded", "reason": "schema_failure", "review_flag": True, "raw": raw}
    checks = _similarity_checks(parsed, recommendation)
    return {"status": "ok", "candidates": [c.model_dump() for c in parsed.candidates], "similarity_checks": checks}


def _get_embedder():
    global _EMBEDDER
    if _EMBEDDER is None:
        from app.embeddings.embedder import Embedder

        _EMBEDDER = Embedder()
    return _EMBEDDER


def _similarity_checks(parsed, recommendation: dict) -> list[dict]:
    if not is_embedding_available():
        return []
    embedder = _get_embedder()
    historical = recommendation.get("historical_questions", [])
    checks = []
    try:
        for candidate in parsed.candidates:
            cand_vec = embedder.embed(candidate.text)
            best = 0.0
            best_ref = None
            for hist in historical:
                sim = embedder.similarity(cand_vec, embedder.embed(hist.get("question_text", "")))
                if sim > best:
                    best = sim
                    best_ref = hist.get("question_id")
            flag = best > settings.candidate_similarity_threshold
            checks.append(
                {
                    "candidate_text": candidate.text[:50],
                    "max_similarity": round(best, 4),
                    "source_question_id": best_ref,
                    "flagged": flag,
                }
            )
    except Exception:
        return []
    return checks