import os
import json
import asyncio
import re
import fitz
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
AI_API_KEY = os.getenv("AI_API_KEY")
MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
client = Groq(api_key=AI_API_KEY) if AI_API_KEY else None


class AIServiceUnavailableError(Exception):
    pass


def _is_network_error(err: Exception) -> bool:
    text = str(err).lower()
    network_markers = [
        "dns",
        "timed out",
        "timeout",
        "connection reset",
        "connection aborted",
        "connection refused",
        "name resolution",
        "temporary failure in name resolution",
        "max retries exceeded",
        "unavailable",
    ]
    return any(marker in text for marker in network_markers)


async def _with_retries(callable_fn, retries: int = 3, delay_seconds: float = 1.5):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            return callable_fn()
        except Exception as err:
            last_error = err
            if not _is_network_error(err) or attempt == retries:
                break
            await asyncio.sleep(delay_seconds * attempt)
    raise last_error


def extract_text_from_pdf(pdf_path: str) -> str:
    with fitz.open(pdf_path) as doc:
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts).strip()


def _parse_questions_payload(content: str):
    _BULLET = r"[\s\u2022\u00b7\u25aa\u25cf\u2023\-\*\.\:]"
    # Line-start bullet + label (handles "• Question:", " - Question:", tabs)
    _LINE_START = rf"(?:^|\n){_BULLET}*"

    def _split_by_question_number_headers(blob: str):
        """Split marking scheme text on standalone lines like 'Question 01' (no colon)."""
        blob = (blob or "").replace("\r\n", "\n").strip()
        if not blob:
            return []
        rx = re.compile(r"(?mi)^\s*Question\s*(0*\d+)\s*$", re.MULTILINE)
        matches = list(rx.finditer(blob))
        if not matches:
            return [(None, blob)]
        blocks = []
        first_start = matches[0].start()
        if first_start > 0:
            pre = blob[:first_start].strip()
            if pre:
                blocks.append((None, pre))
        for i, m in enumerate(matches):
            qn = m.group(1)
            end = matches[i + 1].start() if i + 1 < len(matches) else len(blob)
            body = blob[m.end() : end].strip()
            blocks.append((qn, body))
        return blocks

    def _extract_from_freeform_blob(blob: str, question_no_from_header=None):
        if not blob:
            return {}

        blob = blob.replace("\r\n", "\n").strip()

        def _capture(label_patterns):
            for pattern in label_patterns:
                match = re.search(pattern, blob, flags=re.IGNORECASE | re.DOTALL)
                if match:
                    return match.group(1).strip()
            return ""

        question_text = _capture(
            [
                rf"{_LINE_START}question(?:\s+\d+)?\s*:\s*(.+?)(?={_LINE_START}(?:criteria|model\s*answer|max\s*marks)\s*:|$)",
            ]
        )
        criteria_text = _capture(
            [
                rf"{_LINE_START}criteria\s*:\s*(.+?)(?={_LINE_START}(?:model\s*answer|max\s*marks|question)\s*:|$)",
            ]
        )
        model_answer_text = _capture(
            [
                rf"{_LINE_START}model\s*answer\s*:\s*(.+?)(?={_LINE_START}(?:max\s*marks|criteria|question)\s*:|$)",
            ]
        )
        max_marks_text = _capture(
            [
                rf"{_LINE_START}max\s*marks\s*:\s*([0-9]+(?:\.[0-9]+)?)",
            ]
        )
        # "Question: ..." line only (not "Question 01" header) — needs a colon after Question
        question_no_inline = _capture(
            [
                rf"{_LINE_START}question\s*([0-9]+)\s*:",
            ]
        )

        extracted = {}
        if question_text:
            extracted["question"] = question_text
        if criteria_text:
            extracted["criteria"] = criteria_text
        if model_answer_text:
            extracted["model_answer"] = model_answer_text
        if max_marks_text:
            extracted["max_marks"] = (
                float(max_marks_text) if "." in max_marks_text else int(max_marks_text)
            )
        if question_no_from_header:
            extracted["question_no"] = str(question_no_from_header).strip()
        elif question_no_inline:
            extracted["question_no"] = str(question_no_inline).strip()
        return extracted

    def _extract_from_freeform_text(raw_question: dict):
        if not raw_question:
            return {}

        text_candidates = []
        for key, value in raw_question.items():
            if isinstance(value, str):
                # Keep the original key label in the blob to preserve semantics
                # for formats like {"Question 01": "...", "Criteria": "..."}.
                text_candidates.append(f"{key}: {value}".replace("\\n", "\n"))
        blob = "\n".join(text_candidates).strip()
        if not blob:
            return {}

        return _extract_from_freeform_blob(blob, question_no_from_header=None)

    def _expand_question_segments(raw_questions):
        """Turn Groq 'questions' array into (optional_header_qn, segment_blob) pairs."""
        segments = []
        for raw in raw_questions:
            if isinstance(raw, str):
                blob = raw.replace("\\n", "\n").strip()
                if not blob:
                    continue
                hdrs = len(re.findall(r"(?mi)^\s*Question\s*0*\d+\s*$", blob, flags=re.MULTILINE))
                if hdrs >= 2:
                    for qn, body in _split_by_question_number_headers(blob):
                        if body:
                            segments.append((qn, body))
                else:
                    segments.append((None, blob))
                continue
            if not isinstance(raw, dict):
                continue
            has_structured_keys = any(
                isinstance(k, str)
                and k.strip().lower().replace("_", " ").startswith(
                    ("question", "criteria", "model answer", "model_answer", "max marks", "max_marks")
                )
                for k in raw.keys()
            )
            if has_structured_keys:
                segments.append((None, raw))
                continue
            blob = "\n".join(
                str(v).replace("\\n", "\n")
                for v in raw.values()
                if isinstance(v, str)
            ).strip()
            if not blob:
                segments.append((None, raw))
                continue
            hdrs = len(re.findall(r"(?mi)^\s*Question\s*0*\d+\s*$", blob, flags=re.MULTILINE))
            if hdrs >= 2:
                for qn, body in _split_by_question_number_headers(blob):
                    if body:
                        segments.append((qn, body))
            else:
                segments.append((None, blob))
        return segments

    def _pick_value_case_insensitive(source: dict, aliases, default=""):
        def _norm_key(value):
            return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())

        normalized = {_norm_key(k): v for k, v in source.items()}
        for alias in aliases:
            key = _norm_key(alias)
            if key in normalized:
                return normalized[key]
        return default

    parsed = json.loads(content)
    if isinstance(parsed, list):
        questions = parsed
    elif isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
        questions = parsed["questions"]
    elif isinstance(parsed, dict) and isinstance(parsed.get("questions"), str):
        questions = [parsed["questions"]]
    else:
        raise RuntimeError("Groq JSON response does not contain a valid questions array.")

    segments = _expand_question_segments(questions)

    normalized_questions = []
    seg_idx = 0
    for qn_header, segment in segments:
        seg_idx += 1
        if isinstance(segment, dict):
            raw_question = segment
            freeform_fields = _extract_from_freeform_text(raw_question)
            merged_question = {**raw_question, **freeform_fields}
        else:
            freeform_fields = _extract_from_freeform_blob(segment, question_no_from_header=qn_header)
            merged_question = {**freeform_fields}

        question_no = _pick_value_case_insensitive(
            merged_question, ["question_no", "question no", "q_no", "qno"], qn_header or seg_idx
        )
        question_text = _pick_value_case_insensitive(
            merged_question, ["question", "question_text", "question text", "prompt"], ""
        )
        model_answer = _pick_value_case_insensitive(
            merged_question, ["model_answer", "model answer", "answer", "sample_answer"], ""
        )
        max_marks = _pick_value_case_insensitive(
            merged_question, ["max_marks", "max marks", "marks", "total_marks"], 0
        )
        criteria = _pick_value_case_insensitive(
            merged_question, ["criteria", "criterion", "rubric", "marking_criteria"], ""
        )

        if isinstance(criteria, list):
            criteria_descriptions = []
            criteria_marks_total = 0
            for criterion in criteria:
                if not isinstance(criterion, dict):
                    continue
                description = str(criterion.get("description", "")).strip()
                if description:
                    criteria_descriptions.append(description)
                marks = criterion.get("marks")
                if isinstance(marks, (int, float)):
                    criteria_marks_total += marks
            criteria = "; ".join(criteria_descriptions).strip()
            if (not max_marks or max_marks == 0) and criteria_marks_total > 0:
                max_marks = criteria_marks_total

        normalized_questions.append(
            {
                "question_no": str(question_no).strip(),
                "question": str(question_text).strip(),
                "criteria": str(criteria).strip(),
                "model_answer": str(model_answer).strip(),
                "max_marks": max_marks,
            }
        )

    if not normalized_questions:
        raise RuntimeError("Groq JSON response did not contain usable question objects.")

    return normalized_questions


async def parse_rubric_ai(file_path: str):
    if not AI_API_KEY or client is None:
        raise RuntimeError("AI_API_KEY is missing in environment.")

    if not os.path.exists(file_path):
        raise RuntimeError(f"PDF file not found: {file_path}")
    if os.path.getsize(file_path) == 0:
        raise RuntimeError("Uploaded PDF is empty (0 bytes).")

    pdf_text = extract_text_from_pdf(file_path)
    if not pdf_text:
        raise RuntimeError("Could not extract text from PDF.")

    prompt = f"""
Analyze the following marking scheme text and convert it into JSON.
Return a JSON object with one key: "questions".
"questions" must be an array of objects. Each object MUST use these exact keys:
"question_no", "question", "criteria", "model_answer", "max_marks".

Rules:
- "question_no" is the question number only (e.g. "01", "2").
- "question" is the full question wording (not the rubric criteria).
- If the source uses lines like "Question 01" as a header, still fill "question_no" and put the actual question text in "question".

Return only valid JSON.

TEXT:
{pdf_text[:120000]}
""".strip()

    def _groq_call():
        return client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )

    try:
        completion = await _with_retries(_groq_call, retries=3, delay_seconds=1.5)
    except Exception as err:
        if _is_network_error(err):
            raise AIServiceUnavailableError(
                "Groq service is unreachable (DNS/network timeout). Please retry."
            ) from err
        raise

    content = (completion.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("Groq returned an empty response.")

    return _parse_questions_payload(content)