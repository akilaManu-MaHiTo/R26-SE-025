"""
Google Colab grading server — copy this cell into Colab (or run locally for testing).

Install in Colab:
    pip install flask pyngrok

Set your ngrok token once:
    from pyngrok import ngrok
    ngrok.set_auth_token("YOUR_NGROK_TOKEN")

Then run this file and point GradingEngine COLAB_EVALUATE_URL to the printed /evaluate URL.

Local mock (no real model, Colab offline):
    set COLAB_USE_MOCK=1
    python colab/colab_evaluate_server.py
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from flask import Flask, jsonify, request

app = Flask(__name__)

COLAB_USE_MOCK = os.getenv("COLAB_USE_MOCK", "").strip().lower() in {"1", "true", "yes"}


def strip_markdown_json_fence(text: str) -> str:
    text = (text or "").strip()
    if not text.startswith("```"):
        return text
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def sanitize_grading_response(data: dict) -> dict:
    """
    Build a clean JSON-serializable grading payload.
    Keeps feedback as plain text (never nested JSON objects).
    """
    feedback = data.get("feedback", "")
    if isinstance(feedback, (dict, list)):
        feedback = json.dumps(feedback, ensure_ascii=False)
    else:
        feedback = str(feedback or "")

    justification = data.get("justification", "")
    if isinstance(justification, (dict, list)):
        justification = json.dumps(justification, ensure_ascii=False)
    else:
        justification = str(justification or "")

    max_score = _coerce_float(data.get("max_score"))
    total_score = _coerce_float(data.get("total_score"))

    results = data.get("results")
    if isinstance(results, list) and results:
        recomputed = 0.0
        for item in results:
            if isinstance(item, dict):
                recomputed += _coerce_float(item.get("score", item.get("marks")))
        if recomputed > 0:
            total_score = round(recomputed, 4)

    return {
        "max_score": max_score,
        "total_score": total_score,
        "justification": justification.strip(),
        "feedback": feedback.strip(),
        **({"results": results} if isinstance(results, list) else {}),
    }


def parse_model_json(raw_output: str) -> dict:
    """Parse LLM output into a dict, then sanitize for jsonify."""
    text = strip_markdown_json_fence(raw_output)
    if not text:
        raise ValueError("Model returned empty output.")

    parsed = json.loads(text)
    if isinstance(parsed, str):
        parsed = json.loads(strip_markdown_json_fence(parsed))
    if not isinstance(parsed, dict):
        raise ValueError("Model JSON must be an object.")

    return sanitize_grading_response(parsed)


def _parse_rubric_questions(rubric: Any) -> list[dict]:
    if isinstance(rubric, list):
        return [q for q in rubric if isinstance(q, dict)]
    if isinstance(rubric, str) and rubric.strip():
        try:
            parsed = json.loads(rubric)
            if isinstance(parsed, list):
                return [q for q in parsed if isinstance(q, dict)]
            if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
                return [q for q in parsed["questions"] if isinstance(q, dict)]
        except json.JSONDecodeError:
            return []
    return []


def mock_grade_with_model(payload: dict) -> str:
    """
    Deterministic stand-in when COLAB_USE_MOCK=1 (local E2E without a real model).
    Awards ~60% of each question's max_marks so parse/normalize paths stay realistic.
    """
    questions = _parse_rubric_questions(payload.get("rubric"))
    answer = str(payload.get("answer") or "")
    snippet = str(payload.get("snippet") or "")
    has_context = bool(snippet.strip()) and "No lecture materials found" not in snippet

    results: list[dict] = []
    if questions:
        for idx, q in enumerate(questions, start=1):
            q_no = str(q.get("question_no") or idx).strip()
            if q_no.isdigit():
                q_no = str(int(q_no)).zfill(2)
            max_marks = _coerce_float(q.get("max_marks", q.get("marks")), 5.0)
            score = round(max_marks * 0.6, 2) if answer.strip() else 0.0
            results.append(
                {
                    "q_no": q_no,
                    "score": score,
                    "criteria_breakdown": [],
                    "justification": (
                        f"Mock Colab graded Q{q_no} "
                        f"({'with RAG context' if has_context else 'without RAG hits'})."
                    ),
                    "feedback": "Local mock response — replace with your Colab model.",
                }
            )
        total = round(sum(_coerce_float(r["score"]) for r in results), 4)
        max_score = round(sum(_coerce_float(q.get("max_marks", q.get("marks")), 5.0) for q in questions), 4)
    else:
        total = 3.0 if answer.strip() else 0.0
        max_score = 5.0
        results = [
            {
                "q_no": "01",
                "score": total,
                "criteria_breakdown": [],
                "justification": "Mock Colab single-question grade.",
                "feedback": "Local mock response — replace with your Colab model.",
            }
        ]

    return json.dumps(
        {
            "max_score": max_score,
            "total_score": total,
            "justification": "Mock Colab evaluation.",
            "feedback": "Deterministic local mock (COLAB_USE_MOCK=1).",
            "results": results,
        },
        ensure_ascii=False,
    )


def grade_with_model(payload: dict) -> str:
    """
    Replace this with your fine-tuned model / RAG pipeline in Colab.
    Must return a JSON string (or text containing a JSON object).

    Expected request keys: topic, rubric, snippet, answer
    """
    if COLAB_USE_MOCK:
        return mock_grade_with_model(payload)

    raise NotImplementedError(
        "Plug in your Colab model here and return a JSON string with "
        "max_score, total_score, justification, feedback (and optional results). "
        "For local E2E without a model, set COLAB_USE_MOCK=1."
    )


@app.route("/evaluate", methods=["POST"])
def evaluate():
    try:
        payload = request.get_json(silent=True) or {}
        for key in ("topic", "rubric", "snippet", "answer"):
            payload.setdefault(key, "")

        raw_model_output = grade_with_model(payload)
        clean = parse_model_json(raw_model_output)
        return jsonify(clean), 200
    except json.JSONDecodeError as err:
        return jsonify({"error": f"Model returned invalid JSON: {err}"}), 500
    except NotImplementedError as err:
        return jsonify({"error": str(err)}), 501
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "mock": COLAB_USE_MOCK}), 200


if __name__ == "__main__":
    # Optional: expose via ngrok when running inside Colab
    skip_ngrok = os.getenv("COLAB_SKIP_NGROK", "").strip().lower() in {"1", "true", "yes"}
    if not skip_ngrok:
        try:
            from pyngrok import ngrok

            public_url = ngrok.connect(5000)
            print(f"Public evaluate URL: {public_url}/evaluate")
        except Exception as err:
            print(f"ngrok not started ({err}). Use local http://127.0.0.1:5000/evaluate")
    else:
        print("ngrok skipped (COLAB_SKIP_NGROK=1). Use http://127.0.0.1:5000/evaluate")

    print(f"COLAB_USE_MOCK={COLAB_USE_MOCK}")
    app.run(host="0.0.0.0", port=5000)
