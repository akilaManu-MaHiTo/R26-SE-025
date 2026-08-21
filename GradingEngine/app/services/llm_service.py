import json

from app.services.ai_model_route import evaluate_grading_async
from app.services.answer_splitter import (
    clean_ocr_transcript,
    normalize_question_no,
    resolve_answer_for_question,
    split_transcript_by_questions,
    transcript_has_markers,
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


def _empty_question_result(q_no: str, *, reason: str = "No answer detected for this question.") -> dict:
    return {
        "q_no": q_no,
        "score": 0.0,
        "criteria_breakdown": [],
        "justification": reason,
        "feedback": "Please review manually.",
        "grading_source": "empty",
        "slice_source": "empty",
        "answer_excerpt": "",
        "error": None,
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
                score = _coerce_float(item.get("score", item.get("marks")))
                if score == 0:
                    # Colab often puts the mark on the parent object as score/total_score.
                    score = _coerce_float(
                        evaluation.get("total_score", evaluation.get("score", evaluation.get("marks")))
                    )
                if score == 0 and isinstance(item.get("criteria_breakdown"), list):
                    score = round(
                        sum(
                            _coerce_float(p.get("awarded_marks", p.get("marks")))
                            for p in item["criteria_breakdown"]
                            if isinstance(p, dict)
                        ),
                        4,
                    )
                return {
                    "q_no": q_no,
                    "score": score,
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
        "score": _coerce_float(
            (evaluation or {}).get(
                "total_score",
                (evaluation or {}).get("score", (evaluation or {}).get("marks")),
            )
        ),
        "criteria_breakdown": [],
        "justification": str((evaluation or {}).get("justification") or "").strip(),
        "feedback": str((evaluation or {}).get("feedback") or "").strip(),
    }


def _attach_diagnostics(
    row: dict,
    *,
    q_no: str,
    slice_source: str,
    answer_slice: str,
    grading_source: str,
    error: str | None = None,
) -> dict:
    enriched = dict(row)
    enriched["q_no"] = q_no
    enriched["slice_source"] = slice_source
    enriched["grading_source"] = grading_source
    enriched["answer_excerpt"] = (answer_slice or "")[:1200]
    enriched["error"] = error
    return enriched


async def generate_grading_report(all_text, rubric_data, on_progress=None):
    """
    OCR stays as one full transcript. Grading is one Colab/Groq call per rubric question.
    Local regex split is used when question markers exist.

    If markers exist but a rubric question has no bucket, that question scores 0
    (no full-paper fallback). Full transcript is only used when no markers are found.
    """
    questions_list = [
        q for q in (rubric_data.get("questions") or []) if isinstance(q, dict)
    ]
    subject_code = " ".join(str(rubric_data.get("subject_code") or "").strip().upper().split())
    session_name = str(rubric_data.get("session_name") or "").strip()
    topic_base = subject_code or session_name or "Exam"
    full_text = clean_ocr_transcript(all_text or "")
    questions_total = len(questions_list)

    async def _emit(done: int, current_q: str | None = None):
        if not on_progress:
            return
        maybe = on_progress(done, questions_total, current_q)
        if hasattr(maybe, "__await__"):
            await maybe

    if not questions_list:
        await _emit(0, None)
        payload = {
            "topic": topic_base,
            "rubric": "[]",
            "snippet": session_name,
            "answer": full_text,
            "course_name": subject_code,
        }
        return await evaluate_grading_async(payload)

    buckets = split_transcript_by_questions(full_text, questions_list)
    markers_found = transcript_has_markers(full_text)
    if buckets:
        print(f"Answer splitter found {len(buckets)} question bucket(s): {sorted(buckets.keys())}")
    elif markers_found:
        print("Answer splitter found markers but no usable buckets after cleanup.")
    else:
        print("Answer splitter found no markers; using full transcript only when needed.")

    results: list[dict] = []
    engine_sources: list[str] = []
    slice_sources: dict[str, str] = {}
    rag_chunks_total = 0
    rag_used_any = False
    rag_per_question: dict[str, dict] = {}
    rag_course = subject_code or None

    await _emit(0, None)

    for idx, question in enumerate(questions_list, start=1):
        q_no = normalize_question_no(question.get("question_no"), idx)
        await _emit(len(results), q_no)
        answer_slice, slice_source = resolve_answer_for_question(
            full_text,
            question,
            buckets,
            idx,
            markers_found=markers_found,
        )
        slice_sources[q_no] = slice_source

        if slice_source == "empty":
            print(f"Q{q_no}: no answer text — scoring 0.")
            reason = (
                "No answer detected for this question (marker missing or empty after OCR cleanup)."
                if markers_found
                else "No answer detected for this question."
            )
            results.append(
                _attach_diagnostics(
                    _empty_question_result(q_no, reason=reason),
                    q_no=q_no,
                    slice_source="empty",
                    answer_slice="",
                    grading_source="empty",
                )
            )
            engine_sources.append("empty")
            rag_per_question[q_no] = {
                "rag_chunks": 0,
                "rag_context_used": False,
                "rag_snippet": "",
            }
            await _emit(len(results), q_no)
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
            evaluation = await evaluate_grading_async(payload)
            row = _row_from_evaluation(evaluation, q_no)
            q_engine = str(evaluation.get("grading_source") or "unknown")
            results.append(
                _attach_diagnostics(
                    row,
                    q_no=q_no,
                    slice_source=slice_source,
                    answer_slice=answer_slice,
                    grading_source=q_engine,
                )
            )
            engine_sources.append(q_engine)
            q_chunks = int(evaluation.get("rag_chunks") or 0)
            q_used = bool(evaluation.get("rag_context_used"))
            q_snippet = str(evaluation.get("rag_snippet") or "").strip()
            rag_chunks_total += q_chunks
            rag_used_any = rag_used_any or q_used
            if evaluation.get("rag_course"):
                rag_course = evaluation["rag_course"]
            rag_per_question[q_no] = {
                "rag_chunks": q_chunks,
                "rag_context_used": q_used,
                "rag_snippet": q_snippet,
            }
        except Exception as err:
            print(f"Q{q_no}: grading failed ({err}) — scoring 0.")
            err_text = str(err)
            results.append(
                _attach_diagnostics(
                    {
                        "q_no": q_no,
                        "score": 0.0,
                        "criteria_breakdown": [],
                        "justification": f"Grading engine failed for this question: {err_text}",
                        "feedback": "Please review manually.",
                    },
                    q_no=q_no,
                    slice_source=slice_source,
                    answer_slice=answer_slice,
                    grading_source="error",
                    error=err_text,
                )
            )
            engine_sources.append("error")
            rag_per_question[q_no] = {
                "rag_chunks": 0,
                "rag_context_used": False,
                "rag_snippet": "",
            }

        await _emit(len(results), q_no)

    return _finalize_evaluation(
        results=results,
        questions_list=questions_list,
        buckets=buckets,
        slice_sources=slice_sources,
        markers_found=markers_found,
        rag_per_question=rag_per_question,
        rag_course=rag_course,
        subject_code=subject_code,
    )


def _finalize_evaluation(
    *,
    results: list[dict],
    questions_list: list[dict],
    buckets: dict[str, str],
    slice_sources: dict[str, str],
    markers_found: bool,
    rag_per_question: dict[str, dict],
    rag_course: str | None,
    subject_code: str,
) -> dict:
    engine_sources = [str(r.get("grading_source") or "unknown") for r in results]
    total_score = round(sum(_coerce_float(r.get("score")) for r in results), 4)
    max_score = _paper_max_score(questions_list)
    rag_chunks_total = sum(int((rag_per_question.get(r.get("q_no")) or {}).get("rag_chunks") or 0) for r in results)
    rag_used_any = any(
        bool((rag_per_question.get(r.get("q_no")) or {}).get("rag_context_used")) for r in results
    )

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
        "rag_course": rag_course or subject_code or None,
        "rag_per_question": rag_per_question,
        "answer_split": {
            "buckets_found": sorted(buckets.keys()),
            "per_question_source": slice_sources,
            "markers_found": markers_found,
            "cleaned_transcript": True,
        },
    }


async def _grade_one_question_row(
    *,
    question: dict,
    q_no: str,
    question_idx: int,
    full_text: str,
    buckets: dict[str, str],
    markers_found: bool,
    topic_base: str,
    session_name: str,
    subject_code: str,
) -> tuple[dict, dict]:
    """
    Grade a single rubric question. Returns (result_row, rag_meta_for_q).
    """
    answer_slice, slice_source = resolve_answer_for_question(
        full_text,
        question,
        buckets,
        question_idx,
        markers_found=markers_found,
    )

    if slice_source == "empty":
        reason = (
            "No answer detected for this question (marker missing or empty after OCR cleanup)."
            if markers_found
            else "No answer detected for this question."
        )
        row = _attach_diagnostics(
            _empty_question_result(q_no, reason=reason),
            q_no=q_no,
            slice_source="empty",
            answer_slice="",
            grading_source="empty",
        )
        return row, {"rag_chunks": 0, "rag_context_used": False, "rag_snippet": ""}

    payload = {
        "topic": f"{topic_base} — Q{q_no}",
        "rubric": json.dumps([question], ensure_ascii=False),
        "snippet": session_name,
        "answer": answer_slice,
        "course_name": subject_code,
    }
    try:
        evaluation = await evaluate_grading_async(payload)
        row = _row_from_evaluation(evaluation, q_no)
        q_engine = str(evaluation.get("grading_source") or "unknown")
        row = _attach_diagnostics(
            row,
            q_no=q_no,
            slice_source=slice_source,
            answer_slice=answer_slice,
            grading_source=q_engine,
        )
        rag_meta = {
            "rag_chunks": int(evaluation.get("rag_chunks") or 0),
            "rag_context_used": bool(evaluation.get("rag_context_used")),
            "rag_snippet": str(evaluation.get("rag_snippet") or "").strip(),
        }
        if evaluation.get("rag_course"):
            rag_meta["rag_course"] = evaluation["rag_course"]
        return row, rag_meta
    except Exception as err:
        err_text = str(err)
        row = _attach_diagnostics(
            {
                "q_no": q_no,
                "score": 0.0,
                "criteria_breakdown": [],
                "justification": f"Grading engine failed for this question: {err_text}",
                "feedback": "Please review manually.",
            },
            q_no=q_no,
            slice_source=slice_source,
            answer_slice=answer_slice,
            grading_source="error",
            error=err_text,
        )
        return row, {"rag_chunks": 0, "rag_context_used": False, "rag_snippet": ""}


async def regrade_single_question(
    all_text: str,
    rubric_data: dict,
    existing_evaluation: dict | None,
    question_no: str,
) -> dict:
    """
    Re-grade one question and merge into the existing evaluation document.
    """
    questions_list = [
        q for q in (rubric_data.get("questions") or []) if isinstance(q, dict)
    ]
    if not questions_list:
        raise ValueError("Rubric has no questions.")

    target = normalize_question_no(question_no, 1)
    question = None
    question_idx = 1
    for idx, q in enumerate(questions_list, start=1):
        if normalize_question_no(q.get("question_no"), idx) == target:
            question = q
            question_idx = idx
            break
    if question is None:
        raise ValueError(f"Question {target} not found on rubric.")

    subject_code = " ".join(str(rubric_data.get("subject_code") or "").strip().upper().split())
    session_name = str(rubric_data.get("session_name") or "").strip()
    topic_base = subject_code or session_name or "Exam"
    full_text = clean_ocr_transcript(all_text or "")
    buckets = split_transcript_by_questions(full_text, questions_list)
    markers_found = transcript_has_markers(full_text)

    row, rag_meta = await _grade_one_question_row(
        question=question,
        q_no=target,
        question_idx=question_idx,
        full_text=full_text,
        buckets=buckets,
        markers_found=markers_found,
        topic_base=topic_base,
        session_name=session_name,
        subject_code=subject_code,
    )

    existing = dict(existing_evaluation or {})
    old_results = [
        r for r in (existing.get("results") or []) if isinstance(r, dict)
    ]
    # Preserve order of rubric questions
    by_no = {
        normalize_question_no(r.get("q_no") or r.get("question_no"), i): r
        for i, r in enumerate(old_results, start=1)
    }
    by_no[target] = row
    results = []
    for idx, q in enumerate(questions_list, start=1):
        q_no = normalize_question_no(q.get("question_no"), idx)
        if q_no in by_no:
            results.append(by_no[q_no])
        else:
            results.append(_empty_question_result(q_no))

    rag_per_question = dict(existing.get("rag_per_question") or {})
    rag_per_question[target] = {
        "rag_chunks": int(rag_meta.get("rag_chunks") or 0),
        "rag_context_used": bool(rag_meta.get("rag_context_used")),
        "rag_snippet": str(rag_meta.get("rag_snippet") or ""),
    }
    slice_sources = dict((existing.get("answer_split") or {}).get("per_question_source") or {})
    slice_sources[target] = str(row.get("slice_source") or "empty")
    rag_course = rag_meta.get("rag_course") or existing.get("rag_course") or subject_code

    return _finalize_evaluation(
        results=results,
        questions_list=questions_list,
        buckets=buckets,
        slice_sources=slice_sources,
        markers_found=markers_found,
        rag_per_question=rag_per_question,
        rag_course=rag_course,
        subject_code=subject_code,
    )

