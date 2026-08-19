import asyncio
import json
import os
import re
import time

import requests
from fastapi import APIRouter, HTTPException
from groq import Groq
from pydantic import BaseModel

from app.services.rag_service import build_grading_query, retrieve_relevant_context

router = APIRouter()

COLAB_URL = os.getenv("COLAB_EVALUATE_URL", "").strip()
# Per-question Colab via ngrok often needs well over 25s (cold start + LLM).
COLAB_TIMEOUT_SECONDS = int(os.getenv("COLAB_TIMEOUT_SECONDS", "120"))
COLAB_CONNECT_TIMEOUT_SECONDS = int(os.getenv("COLAB_CONNECT_TIMEOUT_SECONDS", "20"))
COLAB_RETRIES = max(1, int(os.getenv("COLAB_RETRIES", "3")))
COLAB_RETRY_DELAY_SECONDS = float(os.getenv("COLAB_RETRY_DELAY_SECONDS", "2"))
# Appended to Colab snippet so fine-tuned models get a stricter marking policy.
COLAB_STRICT_GRADING = os.getenv("COLAB_STRICT_GRADING", "1").strip().lower() in {
    "1",
    "true",
    "yes",
}
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("BACKUP_API_KEY") or os.getenv("AI_API_KEY")

_COLAB_STRICT_POLICY = (
    "\n\nGRADING POLICY (mandatory): Be a strict university examiner. "
    "Award marks only for evidence that clearly meets each rubric criterion. "
    "Use partial credit for partial answers. Do not award full marks for vague, "
    "incomplete, generic, or barely-related answers. When uncertain, under-mark "
    "rather than over-mark. Never inflate scores for effort alone."
)


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


def _extract_balanced_json_object(text: str, start_idx: int) -> str | None:
    """Return the JSON object substring starting at text[start_idx] ('{')."""
    if start_idx < 0 or start_idx >= len(text) or text[start_idx] != "{":
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start_idx, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start_idx : i + 1]
    return None


def _grade_dict_from_model_markdown(text: str) -> dict | None:
    """
    Extract a grading object from model markdown like:
      ### Grade & Feedback: { "total_score": 10, "justification": "..." }
    or a fenced/raw JSON blob containing total_score/score.
    """
    raw = _strip_markdown_json_fence(text or "")
    if not raw.strip():
        return None

    # Prefer the explicit "Grade & Feedback" block from the fine-tuned Colab model.
    marker = re.search(
        r"(?:###\s*)?Grade\s*&\s*Feedback\s*:\s*",
        raw,
        flags=re.IGNORECASE,
    )
    if marker:
        brace = raw.find("{", marker.end())
        blob = _extract_balanced_json_object(raw, brace) if brace >= 0 else None
        if blob:
            try:
                parsed = json.loads(blob)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

    # Whole-string JSON
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and (
            "total_score" in parsed
            or "score" in parsed
            or "marks" in parsed
            or isinstance(parsed.get("results"), list)
        ):
            return parsed
        if isinstance(parsed, str):
            return _grade_dict_from_model_markdown(parsed)
    except json.JSONDecodeError:
        pass

    # First JSON object in the text that looks like a grade payload.
    for match in re.finditer(r"\{", raw):
        blob = _extract_balanced_json_object(raw, match.start())
        if not blob:
            continue
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and (
            "total_score" in parsed
            or "score" in parsed
            or "marks" in parsed
            or isinstance(parsed.get("results"), list)
        ):
            return parsed

    # Last resort: pull numeric total_score / score from text.
    total_score_match = re.search(r'"total_score"\s*:\s*([0-9.]+)', raw)
    score_match = re.search(r'"(?:score|marks)"\s*:\s*([0-9.]+)', raw)
    max_score_match = re.search(r'"max_score"\s*:\s*([0-9.]+)', raw)
    if total_score_match or score_match:
        return {
            "max_score": float(max_score_match.group(1)) if max_score_match else 0.0,
            "total_score": float((total_score_match or score_match).group(1)),
            "justification": _extract_json_string_field(raw, "justification") or "",
            "feedback": _extract_json_string_field(raw, "feedback") or "",
            "parse_warning": "Recovered score fields from model markdown text.",
        }
    return None


def _unwrap_colab_wrapper(data: dict) -> dict:
    """
    Live Colab often returns:
      {"status":"success","evaluation_output":"### Grade & Feedback: {...}"}
    Unwrap that into a real grading dict before sanitize/normalize.

    Also unwrap when the wrapper includes a placeholder total_score=0 alongside
    evaluation_output that contains the real mark.
    """
    if not isinstance(data, dict):
        return data

    nested_key = None
    nested_val = None
    for key in ("evaluation_output", "output", "result", "response", "raw_output", "text"):
        candidate = data.get(key)
        if isinstance(candidate, dict):
            return _unwrap_colab_wrapper(candidate)
        if isinstance(candidate, str) and candidate.strip():
            nested_key = key
            nested_val = candidate
            break

    direct = _top_level_score(data)
    results = data.get("results")
    has_positive_results = False
    if isinstance(results, list) and results:
        has_positive_results = any(
            isinstance(r, dict) and _row_score_from_item(r) > 0 for r in results
        )

    # Already a real grading payload.
    if (direct > 0 or has_positive_results) and nested_val is None:
        return data
    if (direct > 0 or has_positive_results) and nested_val is not None:
        # Keep direct scores unless nested text clearly has a better grade object.
        extracted = _grade_dict_from_model_markdown(nested_val)
        if extracted and _top_level_score(extracted) > direct:
            extracted.setdefault(
                "parse_warning",
                f"Unwrapped Colab grade from '{nested_key}' (higher than wrapper score).",
            )
            if not extracted.get("feedback"):
                expl = re.search(
                    r"###\s*Explanation\s*:\s*(.+?)(?:\n###|\Z)",
                    nested_val,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                if expl:
                    extracted["feedback"] = expl.group(1).strip()
            return extracted
        return data

    # Placeholder/zero wrapper — pull Grade & Feedback from markdown.
    if nested_val:
        extracted = _grade_dict_from_model_markdown(nested_val)
        if extracted:
            if not extracted.get("feedback"):
                expl = re.search(
                    r"###\s*Explanation\s*:\s*(.+?)(?:\n###|\Z)",
                    nested_val,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                if expl:
                    extracted["feedback"] = expl.group(1).strip()
            extracted.setdefault(
                "parse_warning",
                f"Unwrapped Colab grade from '{nested_key}' markdown/wrapper.",
            )
            return extracted

    return data


def _sanitize_colab_grading_payload(data: dict) -> dict:
    """Normalize a parsed Colab dict so feedback/justification stay plain strings."""
    clean = dict(_unwrap_colab_wrapper(data))
    # Drop wrapper-only keys that are not part of the grading schema.
    for noise in ("status", "evaluation_output", "ok", "success"):
        clean.pop(noise, None)

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
            clean = _sanitize_colab_grading_payload(parsed)
            # Normalize aliases so downstream always sees total_score.
            if clean.get("total_score") in (None, 0, 0.0) and (
                clean.get("score") is not None or clean.get("marks") is not None
            ):
                clean["total_score"] = _coerce_float(
                    clean.get("score", clean.get("marks"))
                )
            # If wrapper still had no score, try treating the whole body as model markdown.
            if clean.get("total_score") in (None, 0, 0.0) and not (
                isinstance(clean.get("results"), list) and clean.get("results")
            ):
                recovered = _grade_dict_from_model_markdown(raw)
                if recovered:
                    clean = _sanitize_colab_grading_payload(recovered)
                    if clean.get("total_score") in (None, 0, 0.0) and (
                        clean.get("score") is not None or clean.get("marks") is not None
                    ):
                        clean["total_score"] = _coerce_float(
                            clean.get("score", clean.get("marks"))
                        )
            return clean
        if isinstance(parsed, str):
            return parse_colab_response_body(parsed)
    except json.JSONDecodeError:
        pass

    recovered = _grade_dict_from_model_markdown(raw)
    if recovered:
        clean = _sanitize_colab_grading_payload(recovered)
        if clean.get("total_score") in (None, 0, 0.0) and (
            clean.get("score") is not None or clean.get("marks") is not None
        ):
            clean["total_score"] = _coerce_float(clean.get("score", clean.get("marks")))
        return clean

    max_score_match = re.search(r'"max_score"\s*:\s*([0-9.]+)', raw)
    total_score_match = re.search(r'"total_score"\s*:\s*([0-9.]+)', raw)
    score_match = re.search(r'"(?:score|marks)"\s*:\s*([0-9.]+)', raw)
    if not total_score_match and not score_match:
        raise ValueError(f"Colab response is not valid JSON: {raw[:300]}")

    return {
        "max_score": float(max_score_match.group(1)) if max_score_match else 0.0,
        "total_score": float(
            (total_score_match or score_match).group(1)
        ),
        "justification": _extract_json_string_field(raw, "justification") or "",
        "feedback": _extract_json_string_field(raw, "feedback") or "",
        "parse_warning": "Colab returned malformed JSON; core fields were recovered from raw text.",
    }


def _coerce_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        pass
    # Common LLM forms: "7/10", "score: 4.5", "awarded 3 marks"
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return default
    return default


def _top_level_score(raw: dict) -> float:
    """Colab models often return score/marks instead of total_score."""
    if not isinstance(raw, dict):
        return 0.0
    for key in ("total_score", "score", "marks", "awarded_marks", "total"):
        if key in raw and raw.get(key) is not None:
            val = _coerce_float(raw.get(key))
            # Ignore max_score-sized placeholders only when explicitly zero-ish elsewhere
            if key != "max_score":
                return val
    return 0.0


def _row_score_from_item(item: dict) -> float:
    if not isinstance(item, dict):
        return 0.0
    for key in ("score", "marks", "awarded_marks", "total_score"):
        if key in item and item.get(key) is not None:
            return _coerce_float(item.get(key))
    breakdown = item.get("criteria_breakdown")
    if isinstance(breakdown, list) and breakdown:
        total = 0.0
        any_marks = False
        for part in breakdown:
            if not isinstance(part, dict):
                continue
            if part.get("awarded_marks") is not None or part.get("marks") is not None:
                any_marks = True
                total += _coerce_float(part.get("awarded_marks", part.get("marks")))
        if any_marks:
            return round(total, 4)
    return 0.0


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
        "score": _row_score_from_item(item),
        "criteria_breakdown": _normalize_criteria_breakdown(item.get("criteria_breakdown")),
        "justification": str(item.get("justification") or "").strip(),
        "feedback": str(item.get("feedback") or "").strip(),
    }


def _sum_per_question_scores(results: list[dict]) -> float:
    return round(sum(_coerce_float(item.get("score")) for item in results), 4)


def _pick_result_for_question(
    *,
    q_no: str,
    idx: int,
    by_qno: dict[str, dict],
    results_raw: list,
    rubric_q: dict | None,
) -> dict:
    """Match Colab/Groq result rows even when q_no formatting differs."""
    if q_no in by_qno:
        row = dict(by_qno[q_no])
        row["q_no"] = q_no
        return row

    # Strip-leading-zero / alternate keys
    alt_keys = {q_no.lstrip("0") or "0", q_no.zfill(2), str(int(q_no)) if q_no.isdigit() else q_no}
    for key in alt_keys:
        if key in by_qno:
            row = dict(by_qno[key])
            row["q_no"] = q_no
            return row

    # Single-question Colab calls often return one result with a mismatched q_no.
    if len(by_qno) == 1:
        row = dict(next(iter(by_qno.values())))
        row["q_no"] = q_no
        return row
    if len(results_raw) == 1 and isinstance(results_raw[0], dict):
        row = _normalize_result_row(results_raw[0], idx, rubric_q)
        row["q_no"] = q_no
        return row

    return _normalize_result_row({}, idx, rubric_q)


def normalize_evaluation(raw: dict, questions_list: list[dict] | None = None) -> dict:
    """Unify Colab flat JSON and Groq structured JSON into one stored/API shape."""
    questions_list = questions_list or []
    max_score = _paper_max_score(
        questions_list, _coerce_float(raw.get("max_score"), _top_level_score(raw))
    )
    top_total = _top_level_score(raw)

    results_raw = raw.get("results")
    if isinstance(results_raw, list) and results_raw:
        by_qno: dict[str, dict] = {}
        for idx, item in enumerate(results_raw, start=1):
            if isinstance(item, dict):
                row = _normalize_result_row(item, idx)
                by_qno[row["q_no"]] = row
                # Also index bare / zero-padded variants for lookup.
                bare = row["q_no"].lstrip("0") or "0"
                by_qno.setdefault(bare, row)
                by_qno.setdefault(row["q_no"].zfill(2), row)

        results: list[dict] = []
        if questions_list:
            for idx, q in enumerate(questions_list, start=1):
                q_no = str(q.get("question_no") or idx).strip()
                if q_no.isdigit():
                    q_no = str(int(q_no)).zfill(2)
                results.append(
                    _pick_result_for_question(
                        q_no=q_no,
                        idx=idx,
                        by_qno=by_qno,
                        results_raw=results_raw,
                        rubric_q=q,
                    )
                )
        else:
            results = list({id(v): v for v in by_qno.values()}.values()) or [
                _normalize_result_row(item, idx)
                for idx, item in enumerate(results_raw, start=1)
                if isinstance(item, dict)
            ]
    else:
        total = top_total
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

    # If results parsed as zeros but Colab returned a positive top-level score, recover it.
    if top_total > 0 and results and all(_coerce_float(r.get("score")) == 0 for r in results):
        if len(results) == 1:
            results[0]["score"] = top_total
        else:
            results[0]["score"] = top_total
        print(
            f"Recovered Colab top-level score={top_total} into results "
            f"(q_no mismatch or score/marks alias)."
        )

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

    colab_body = {
        "topic": payload.get("topic", ""),
        "rubric": payload.get("rubric", ""),
        "snippet": payload.get("snippet", ""),
        "answer": payload.get("answer", ""),
    }
    if COLAB_STRICT_GRADING:
        snippet = str(colab_body.get("snippet") or "")
        if "GRADING POLICY (mandatory)" not in snippet:
            colab_body["snippet"] = (snippet + _COLAB_STRICT_POLICY).strip()
    timeout = (COLAB_CONNECT_TIMEOUT_SECONDS, COLAB_TIMEOUT_SECONDS)
    last_err: Exception | None = None

    for attempt in range(1, COLAB_RETRIES + 1):
        try:
            print(
                f"Attempting primary cloud AI engine (Colab) "
                f"attempt {attempt}/{COLAB_RETRIES} "
                f"(connect={COLAB_CONNECT_TIMEOUT_SECONDS}s, read={COLAB_TIMEOUT_SECONDS}s)..."
            )
            response = requests.post(
                COLAB_URL,
                json=colab_body,
                timeout=timeout,
                headers={"ngrok-skip-browser-warning": "true"},
            )
            if response.status_code != 200:
                print(f"Colab returned HTTP {response.status_code} on attempt {attempt}.")
                last_err = RuntimeError(f"HTTP {response.status_code}")
                # Retry transient 5xx / 429; fail fast on 4xx.
                if response.status_code < 500 and response.status_code != 429:
                    return None
            else:
                result = parse_colab_response_body(response.text)
                result["grading_source"] = "colab"
                # Raw Colab bodies often omit top-level score until normalize — keep this line light.
                print(
                    "Primary engine HTTP 200 "
                    f"(parsed total_score={result.get('total_score')}, "
                    f"score={result.get('score')}, "
                    f"results={len(result.get('results') or []) if isinstance(result.get('results'), list) else 0}"
                    f"{', ' + result['parse_warning'] if result.get('parse_warning') else ''})."
                )
                return result
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as err:
            last_err = err
            print(
                f"Primary engine unreachable on attempt {attempt}/{COLAB_RETRIES} "
                f"({type(err).__name__})."
            )
        except (ValueError, requests.exceptions.RequestException) as err:
            last_err = err
            print(f"Primary engine failed on attempt {attempt}/{COLAB_RETRIES} ({type(err).__name__}): {err}")
            # Malformed JSON / non-retryable request errors — don't hammer Colab.
            if isinstance(err, ValueError):
                return None

        if attempt < COLAB_RETRIES:
            delay = COLAB_RETRY_DELAY_SECONDS * attempt
            print(f"Retrying Colab in {delay:.1f}s...")
            time.sleep(delay)

    if last_err is not None:
        print(f"Primary engine exhausted retries ({type(last_err).__name__}).")
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
    rag_chunks = int(rag.get("rag_chunks") or 0)
    rag_used = bool(rag.get("rag_context_used")) and rag_chunks > 0
    rag_snippet = str(rag.get("snippet") or "").strip()

    if rag_used:
        # Real lecture chunks for the model.
        enriched["snippet"] = rag_snippet
    else:
        # Empty RAG is fine — Colab/Groq must still grade from rubric + answer.
        # Do NOT send "No lecture materials found…" prose; it can bias models toward 0.
        enriched["snippet"] = (
            "No lecture context available. Grade using only the rubric and the student's answer."
        )

    if course_name:
        enriched["course_name"] = course_name
    enriched["_rag_meta"] = {
        "rag_chunks": rag_chunks if rag_used else 0,
        "rag_context_used": rag_used,
        "course_name": rag.get("course_name") or course_name or None,
        # Store real lecture text only when used; empty when RAG missed.
        "rag_snippet": rag_snippet if rag_used else "",
    }
    return enriched


def _attach_rag_meta(result: dict, enriched: dict) -> dict:
    meta = enriched.get("_rag_meta") if isinstance(enriched, dict) else None
    if isinstance(meta, dict):
        result["rag_chunks"] = int(meta.get("rag_chunks") or 0)
        result["rag_context_used"] = bool(meta.get("rag_context_used"))
        if meta.get("course_name"):
            result["rag_course"] = meta["course_name"]
        snippet = str(meta.get("rag_snippet") or "").strip()
        if snippet:
            result["rag_snippet"] = snippet
    return result


def evaluate_grading(payload: dict) -> dict:
    questions_list = _parse_rubric_questions(payload.get("rubric", ""))
    enriched = _enrich_payload_with_rag(payload)
    colab_result = try_forward_to_colab(enriched)
    if colab_result is not None:
        normalized = normalize_evaluation(colab_result, questions_list)
        per_q = [
            f"Q{r.get('q_no')}={r.get('score')}"
            for r in (normalized.get("results") or [])
            if isinstance(r, dict)
        ]
        print(
            "Colab grade applied "
            f"(total_score={normalized.get('total_score')}, "
            f"max_score={normalized.get('max_score')}, "
            f"{', '.join(per_q) or 'no per-question rows'})."
        )
        return _attach_rag_meta(normalized, enriched)

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


async def evaluate_grading_async(payload: dict) -> dict:
    """Run Colab/Groq/RAG HTTP off the event loop so dashboard polls stay live."""
    return await asyncio.to_thread(evaluate_grading, payload)


@router.post("/api/grade")
async def handle_grading(payload: GradingPayload):
    try:
        return await evaluate_grading_async(payload.model_dump())
    except Exception as err:
        print(f"All evaluation engines failed: {err}")
        raise HTTPException(
            status_code=500,
            detail="All evaluation engines are currently offline.",
        ) from err
