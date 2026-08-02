import json
import os
import re

import requests
from fastapi import APIRouter, HTTPException
from groq import Groq
from pydantic import BaseModel

from app.services.rag_service import build_grading_query, retrieve_relevant_context

router = APIRouter()

COLAB_URL = os.getenv("COLAB_EVALUATE_URL", "").strip()
# Per-question Colab calls need more headroom than the old whole-paper default.
COLAB_TIMEOUT_SECONDS = int(os.getenv("COLAB_TIMEOUT_SECONDS", "25"))
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("BACKUP_API_KEY") or os.getenv("AI_API_KEY")


class GradingPayload(BaseModel):
    topic: str
    rubric: str
    snippet: str
    answer: str
    course_name: str | None = None


def _extract_json_string_field(text: str, field: str) -> str | None:
    pattern = rf'"{re.escape(field)}"\s*:\s*"'
    match = re.search(pattern, text)
    if not match:
        return None

    start = match.end()
    chars: list[str] = []
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            chars.append(text[i : i + 2])
            i += 2
            continue
        if ch == '"':
            rest = text[i + 1 :].lstrip()
            if not rest or rest[0] in ",}":
                return "".join(chars)
        chars.append(ch)
        i += 1

    return "".join(chars)


def _strip_markdown_json_fence(text: str) -> str:
    text = (text or "").strip()
    if not text.startswith("```"):
        return text
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _sanitize_colab_grading_payload(data: dict) -> dict:
    """Normalize a parsed Colab dict so feedback/justification stay plain strings."""
    clean = dict(data)
    for field in ("feedback", "justification"):
        value = clean.get(field, "")
        if isinstance(value, (dict, list)):
            clean[field] = json.dumps(value, ensure_ascii=False)
        else:
            clean[field] = str(value or "").strip()

    if clean.get("max_score") is not None:
        clean["max_score"] = _coerce_float(clean.get("max_score"))
    if clean.get("total_score") is not None:
        clean["total_score"] = _coerce_float(clean.get("total_score"))

    results = clean.get("results")
    if isinstance(results, list) and results:
        total = 0.0
        for item in results:
            if isinstance(item, dict):
                total += _coerce_float(item.get("score", item.get("marks")))
        if total > 0:
            clean["total_score"] = round(total, 4)

    return clean


def parse_colab_response_body(text: str) -> dict:
    raw = _strip_markdown_json_fence(text)
    if not raw:
        raise ValueError("Colab returned an empty body.")

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            if parsed.get("error"):
                raise ValueError(str(parsed["error"]))
            return _sanitize_colab_grading_payload(parsed)
        if isinstance(parsed, str):
            return parse_colab_response_body(parsed)
    except json.JSONDecodeError:
        pass

    max_score_match = re.search(r'"max_score"\s*:\s*([0-9.]+)', raw)
    total_score_match = re.search(r'"total_score"\s*:\s*([0-9.]+)', raw)
    if not total_score_match:
        raise ValueError(f"Colab response is not valid JSON: {raw[:300]}")

    return {
        "max_score": float(max_score_match.group(1)) if max_score_match else 0.0,
        "total_score": float(total_score_match.group(1)),
        "justification": _extract_json_string_field(raw, "justification") or "",
        "feedback": _extract_json_string_field(raw, "feedback") or "",
        "parse_warning": "Colab returned malformed JSON; core fields were recovered from raw text.",
    }


def _coerce_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_rubric_questions(rubric_raw) -> list[dict]:
    if isinstance(rubric_raw, list):
        return [q for q in rubric_raw if isinstance(q, dict)]
    if isinstance(rubric_raw, str) and rubric_raw.strip():
        try:
            parsed = json.loads(rubric_raw)
            if isinstance(parsed, list):
                return [q for q in parsed if isinstance(q, dict)]
        except json.JSONDecodeError:
            pass
    return []


def _paper_max_score(questions_list: list[dict], fallback: float = 0.0) -> float:
    total = 0.0
    for q in questions_list:
        total += _coerce_float(q.get("max_marks", q.get("marks")))
    return total if total > 0 else fallback


def _normalize_criteria_breakdown(raw_criteria) -> list[dict]:
    if not isinstance(raw_criteria, list):
        return []
    normalized = []
    for item in raw_criteria:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "point": str(
                    item.get("point")
                    or item.get("criterion")
                    or item.get("description")
                    or ""
                ).strip(),
                "awarded_marks": _coerce_float(
                    item.get("awarded_marks", item.get("marks"))
                ),
                "reason": str(item.get("reason") or item.get("feedback") or "").strip(),
            }
        )
    return normalized


def _normalize_result_row(item: dict, fallback_idx: int, rubric_q: dict | None = None) -> dict:
    q_no = str(
        item.get("q_no")
        or item.get("question_no")
        or (rubric_q or {}).get("question_no")
        or fallback_idx
    ).strip()
    if q_no.isdigit():
        q_no = str(int(q_no)).zfill(2)

    return {
        "q_no": q_no,
        "score": _coerce_float(item.get("score", item.get("marks"))),
        "criteria_breakdown": _normalize_criteria_breakdown(item.get("criteria_breakdown")),
        "justification": str(item.get("justification") or "").strip(),
        "feedback": str(item.get("feedback") or "").strip(),
    }


def _sum_per_question_scores(results: list[dict]) -> float:
    return round(sum(_coerce_float(item.get("score")) for item in results), 4)


def normalize_evaluation(raw: dict, questions_list: list[dict] | None = None) -> dict:
    """Unify Colab flat JSON and Groq structured JSON into one stored/API shape."""
    questions_list = questions_list or []
    max_score = _paper_max_score(questions_list, _coerce_float(raw.get("max_score")))

    results_raw = raw.get("results")
    if isinstance(results_raw, list) and results_raw:
        by_qno: dict[str, dict] = {}
        for idx, item in enumerate(results_raw, start=1):
            if isinstance(item, dict):
                row = _normalize_result_row(item, idx)
                by_qno[row["q_no"]] = row

        results: list[dict] = []
        if questions_list:
            for idx, q in enumerate(questions_list, start=1):
                q_no = str(q.get("question_no") or idx).strip()
                if q_no.isdigit():
                    q_no = str(int(q_no)).zfill(2)
                results.append(by_qno.get(q_no, _normalize_result_row({}, idx, q)))
        else:
            results = list(by_qno.values()) or [
                _normalize_result_row(item, idx) for idx, item in enumerate(results_raw, start=1) if isinstance(item, dict)
            ]
    else:
        total = _coerce_float(raw.get("total_score"))
        justification = str(raw.get("justification") or "").strip()
        feedback = str(raw.get("feedback") or "").strip()
        if questions_list:
            results = []
            for idx, q in enumerate(questions_list, start=1):
                q_no = str(q.get("question_no") or idx).strip()
                if q_no.isdigit():
                    q_no = str(int(q_no)).zfill(2)
                row_score = total if len(questions_list) == 1 else 0.0
                results.append(
                    {
                        "q_no": q_no,
                        "score": row_score,
                        "criteria_breakdown": [],
                        "justification": justification,
                        "feedback": feedback,
                    }
                )
            if len(questions_list) > 1 and total > 0 and all(r["score"] == 0 for r in results):
                results[0]["score"] = total
        else:
            results = [
                {
                    "q_no": "01",
                    "score": total,
                    "criteria_breakdown": [],
                    "justification": justification,
                    "feedback": feedback,
                }
            ]

    total_score = _sum_per_question_scores(results)
    summary_justification = str(raw.get("justification") or "").strip() or " ".join(
        r["justification"] for r in results if r["justification"]
    )[:2000]
    summary_feedback = str(raw.get("feedback") or "").strip() or " ".join(
        r["feedback"] for r in results if r["feedback"]
    )[:2000]

    normalized = {
        "total_score": total_score,
        "max_score": max_score,
        "justification": summary_justification,
        "feedback": summary_feedback,
        "results": results,
    }
    if raw.get("parse_warning"):
        normalized["parse_warning"] = raw["parse_warning"]
    if raw.get("grading_source"):
        normalized["grading_source"] = raw["grading_source"]
    return normalized


def _emergency_fallback_response() -> dict:
    return {
        "max_score": 10.0,
        "total_score": 0.0,
        "justification": "Primary AI engine timed out. Running basic fallback mode.",
        "feedback": "System operating on emergency backup parameters.",
        "grading_source": "emergency",
    }


def try_forward_to_colab(payload: dict) -> dict | None:
    if not COLAB_URL:
        print("COLAB_EVALUATE_URL not set — skipping Colab, using fallback.")
        return None

    try:
        print("Attempting primary cloud AI engine (Colab)...")
        colab_body = {
            "topic": payload.get("topic", ""),
            "rubric": payload.get("rubric", ""),
            "snippet": payload.get("snippet", ""),
            "answer": payload.get("answer", ""),
        }
        response = requests.post(
            COLAB_URL,
            json=colab_body,
            timeout=COLAB_TIMEOUT_SECONDS,
            headers={"ngrok-skip-browser-warning": "true"},
        )
        if response.status_code != 200:
            print(f"Colab returned HTTP {response.status_code}.")
            return None

        result = parse_colab_response_body(response.text)
        result["grading_source"] = "colab"
        print("Primary engine responded successfully.")
        return result
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as err:
        print(f"Primary engine unreachable ({type(err).__name__}).")
        return None
    except (ValueError, requests.exceptions.RequestException) as err:
        print(f"Primary engine failed ({type(err).__name__}): {err}")
        return None


def grade_with_groq(payload: dict) -> dict:
    print("Executing Groq fallback model...")

    if not GROQ_API_KEY:
        print("No Groq API key configured; using emergency fallback response.")
        return _emergency_fallback_response()

    questions_list = _parse_rubric_questions(payload.get("rubric", ""))
    question_ids = [
        str(q.get("question_no") or idx).zfill(2) if str(q.get("question_no") or idx).isdigit()
        else str(q.get("question_no") or idx)
        for idx, q in enumerate(questions_list, start=1)
    ] or ["01"]

    prompt = f"""
    SYSTEM: Expert University Grader.
    TOPIC: {payload.get("topic", "")}
    CONTEXT: {payload.get("snippet", "")}
    RUBRIC: {json.dumps(questions_list, ensure_ascii=False)}
    STUDENT TEXT: "{payload.get("answer", "")}"

    TASK: Grade each rubric question separately and return JSON ONLY.
    RULES:
    - Return exactly one entry in "results" for each rubric question.
    - Use these question numbers in order: {json.dumps(question_ids)}
    - "total_score" MUST equal the sum of all "score" values in "results".
    - Each result must include criteria_breakdown aligned to that question's rubric criteria.

    FORMAT:
    {{
        "total_score": 0.0,
        "results": [
            {{
              "q_no": "01",
              "score": 0.0,
              "criteria_breakdown": [{{"point": "...", "awarded_marks": 0.0, "reason": "..."}}],
              "justification": "...",
              "feedback": "..."
            }}
        ]
    }}
    """.strip()

    client = Groq(api_key=GROQ_API_KEY)
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    raw = (completion.choices[0].message.content or "").strip()
    evaluation_data = json.loads(raw) if raw else {}

    if not isinstance(evaluation_data, dict):
        evaluation_data = {"results": [], "raw_model_output": evaluation_data}

    evaluation_data["grading_source"] = "groq"
    print("Groq fallback completed successfully.")
    return normalize_evaluation(evaluation_data, questions_list)


def _enrich_payload_with_rag(payload: dict) -> dict:
    enriched = dict(payload)
    questions_list = _parse_rubric_questions(payload.get("rubric", ""))
    course_name = str(
        payload.get("course_name") or payload.get("subject_code") or ""
    ).strip()
    query = build_grading_query(
        str(payload.get("topic") or ""),
        questions_list,
        str(payload.get("answer") or ""),
    )
    rag = retrieve_relevant_context(query, course_name=course_name or None)
    rag_snippet = str(rag.get("snippet") or "")
    explicit_snippet = str(payload.get("snippet") or "").strip()
    # Don't prepend session name alone when RAG found nothing useful for the course.
    if explicit_snippet and explicit_snippet != rag_snippet:
        enriched["snippet"] = f"{explicit_snippet}\n\n{rag_snippet}".strip()
    else:
        enriched["snippet"] = rag_snippet
    if course_name:
        enriched["course_name"] = course_name
    enriched["_rag_meta"] = {
        "rag_chunks": int(rag.get("rag_chunks") or 0),
        "rag_context_used": bool(rag.get("rag_context_used")),
        "course_name": rag.get("course_name") or course_name or None,
    }
    return enriched


def _attach_rag_meta(result: dict, enriched: dict) -> dict:
    meta = enriched.get("_rag_meta") if isinstance(enriched, dict) else None
    if isinstance(meta, dict):
        result["rag_chunks"] = int(meta.get("rag_chunks") or 0)
        result["rag_context_used"] = bool(meta.get("rag_context_used"))
        if meta.get("course_name"):
            result["rag_course"] = meta["course_name"]
    return result


def evaluate_grading(payload: dict) -> dict:
    questions_list = _parse_rubric_questions(payload.get("rubric", ""))
    enriched = _enrich_payload_with_rag(payload)
    colab_result = try_forward_to_colab(enriched)
    if colab_result is not None:
        return _attach_rag_meta(
            normalize_evaluation(colab_result, questions_list), enriched
        )

    print("Switching to fallback system...")
    try:
        return _attach_rag_meta(grade_with_groq(enriched), enriched)
    except Exception as err:
        print(f"Fallback model failed: {err}")
        if GROQ_API_KEY:
            raise
        return _attach_rag_meta(
            normalize_evaluation(_emergency_fallback_response(), questions_list),
            enriched,
        )


@router.post("/api/grade")
async def handle_grading(payload: GradingPayload):
    try:
        return evaluate_grading(payload.model_dump())
    except Exception as err:
        print(f"All evaluation engines failed: {err}")
        raise HTTPException(
            status_code=500,
            detail="All evaluation engines are currently offline.",
        ) from err
