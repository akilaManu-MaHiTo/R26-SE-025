import json

from app.services.ai_model_route import evaluate_grading
from app.services.answer_splitter import (
    normalize_question_no,
    resolve_answer_for_question,
    split_transcript_by_questions,
)


def _coerce_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _paper_max_score(questions_list: list[dict]) -> float:
    total = 0.0
    for q in questions_list:
        total += _coerce_float(q.get("max_marks", q.get("marks")))
    return total


def _empty_question_result(q_no: str) -> dict:
    return {
        "q_no": q_no,
        "score": 0.0,
        "criteria_breakdown": [],
        "justification": "No answer detected for this question.",
        "feedback": "Please review manually.",
    }


def _row_from_evaluation(evaluation: dict, q_no: str) -> dict:
    """Map a single-question evaluate_grading response into one results row."""
    results = evaluation.get("results") if isinstance(evaluation, dict) else None
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                continue
            item_no = normalize_question_no(item.get("q_no") or item.get("question_no"), 1)
            if item_no == q_no or len(results) == 1:
                return {
                    "q_no": q_no,
                    "score": _coerce_float(item.get("score", item.get("marks"))),
                    "criteria_breakdown": item.get("criteria_breakdown")
                    if isinstance(item.get("criteria_breakdown"), list)
                    else [],
                    "justification": str(
                        item.get("justification") or evaluation.get("justification") or ""
                    ).strip(),
                    "feedback": str(
                        item.get("feedback") or evaluation.get("feedback") or ""
                    ).strip(),
                }

    return {
        "q_no": q_no,
        "score": _coerce_float(evaluation.get("total_score") if isinstance(evaluation, dict) else 0),
        "criteria_breakdown": [],
        "justification": str((evaluation or {}).get("justification") or "").strip(),
        "feedback": str((evaluation or {}).get("feedback") or "").strip(),
    }


async def generate_grading_report(all_text, rubric_data):
    """
    OCR stays as one full transcript. Grading is one Colab/Groq call per rubric question.
    Local regex split is used when question markers exist; otherwise full text is sent.
    """
    questions_list = [
        q for q in (rubric_data.get("questions") or []) if isinstance(q, dict)
    ]
    subject_code = " ".join(str(rubric_data.get("subject_code") or "").strip().upper().split())
    session_name = str(rubric_data.get("session_name") or "").strip()
    topic_base = subject_code or session_name or "Exam"
    full_text = (all_text or "").strip()

    if not questions_list:
        payload = {
            "topic": topic_base,
            "rubric": "[]",
            "snippet": session_name,
            "answer": full_text,
            "course_name": subject_code,
        }
        return evaluate_grading(payload)

    buckets = split_transcript_by_questions(full_text, questions_list)
    if buckets:
        print(f"Answer splitter found {len(buckets)} question bucket(s): {sorted(buckets.keys())}")
    else:
        print("Answer splitter found no markers; using full transcript per question.")

    results: list[dict] = []
    engine_sources: list[str] = []
    slice_sources: dict[str, str] = {}
    rag_chunks_total = 0
    rag_used_any = False
    rag_per_question: dict[str, dict] = {}
    rag_course = subject_code or None

    for idx, question in enumerate(questions_list, start=1):
        q_no = normalize_question_no(question.get("question_no"), idx)
        answer_slice, slice_source = resolve_answer_for_question(
            full_text, question, buckets, idx
        )
        slice_sources[q_no] = slice_source

        if slice_source == "empty":
            print(f"Q{q_no}: no answer text — scoring 0.")
            results.append(_empty_question_result(q_no))
            engine_sources.append("empty")
            continue

        print(f"Q{q_no}: grading with answer source={slice_source} ({len(answer_slice)} chars).")
        payload = {
            "topic": f"{topic_base} — Q{q_no}",
            "rubric": json.dumps([question], ensure_ascii=False),
            "snippet": session_name,
            "answer": answer_slice,
            "course_name": subject_code,
        }

        try:
            evaluation = evaluate_grading(payload)
            row = _row_from_evaluation(evaluation, q_no)
            results.append(row)
            engine_sources.append(str(evaluation.get("grading_source") or "unknown"))
            q_chunks = int(evaluation.get("rag_chunks") or 0)
            q_used = bool(evaluation.get("rag_context_used"))
            rag_chunks_total += q_chunks
            rag_used_any = rag_used_any or q_used
            if evaluation.get("rag_course"):
                rag_course = evaluation["rag_course"]
            rag_per_question[q_no] = {
                "rag_chunks": q_chunks,
                "rag_context_used": q_used,
            }
        except Exception as err:
            print(f"Q{q_no}: grading failed ({err}) — scoring 0.")
            results.append(
                {
                    "q_no": q_no,
                    "score": 0.0,
                    "criteria_breakdown": [],
                    "justification": f"Grading engine failed for this question: {err}",
                    "feedback": "Please review manually.",
                }
            )
            engine_sources.append("error")

    total_score = round(sum(_coerce_float(r.get("score")) for r in results), 4)
    max_score = _paper_max_score(questions_list)

    unique_engines = sorted(
        {s for s in engine_sources if s not in {"empty", "error", "unknown"}}
    )
    if len(unique_engines) == 1:
        grading_source = unique_engines[0]
    elif unique_engines:
        grading_source = "mixed"
    elif "error" in engine_sources:
        grading_source = "error"
    else:
        grading_source = "empty"

    summary_justification = " ".join(
        f"Q{r['q_no']}: {r['justification']}" for r in results if r.get("justification")
    )[:2000]
    summary_feedback = " ".join(
        f"Q{r['q_no']}: {r['feedback']}" for r in results if r.get("feedback")
    )[:2000]

    return {
        "total_score": total_score,
        "max_score": max_score,
        "justification": summary_justification,
        "feedback": summary_feedback,
        "results": results,
        "grading_source": grading_source,
        "rag_context_used": rag_used_any,
        "rag_chunks": rag_chunks_total,
        "rag_course": rag_course,
        "rag_per_question": rag_per_question,
        "answer_split": {
            "buckets_found": sorted(buckets.keys()),
            "per_question_source": slice_sources,
        },
    }
