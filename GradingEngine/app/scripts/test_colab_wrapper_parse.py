"""Regression: Colab {status, evaluation_output} markdown must yield non-zero scores."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ai_model_route import normalize_evaluation, parse_colab_response_body


SAMPLE = {
    "evaluation_output": (
        "### Topic: SE — Q01\n"
        "### Student Answer: A requirements specification describes what software should do.\n\n"
        '### Grade & Feedback: {\n  "total_score": 10,\n'
        '  "justification": "Excellent answer. The main rubric criteria are satisfied fully and clearly."\n}\n'
        "### Explanation: The answer fully satisfies the rubric.\n"
        "### Reference: N/A"
    ),
    "status": "success",
}

SAMPLE_ZERO_PLACEHOLDER = {
    "status": "success",
    "total_score": 0,
    "evaluation_output": (
        '### Grade & Feedback: {\n  "total_score": 7,\n'
        '  "justification": "Partial but relevant."\n}\n'
        "### Explanation: Missing one criterion.\n"
    ),
}


def main() -> None:
    parsed = parse_colab_response_body(json.dumps(SAMPLE))
    assert float(parsed.get("total_score") or 0) == 10.0, parsed
    assert "Excellent" in (parsed.get("justification") or ""), parsed

    norm = normalize_evaluation(
        parsed,
        [{"question_no": "01", "max_marks": 10, "question_text": "Explain requirements."}],
    )
    assert float(norm.get("total_score") or 0) == 10.0, norm
    assert float(norm["results"][0]["score"]) == 10.0, norm

    parsed_zero = parse_colab_response_body(json.dumps(SAMPLE_ZERO_PLACEHOLDER))
    assert float(parsed_zero.get("total_score") or 0) == 7.0, parsed_zero

    print("OK: wrapper unwrap -> total_score=10; zero-placeholder unwrap -> 7")


if __name__ == "__main__":
    main()
