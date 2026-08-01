"""Filesystem adapter for serializing exam-analysis results."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


_OUTPUT_FILES = {
    "student_reports": "student_report.json",
    "question_summaries": "question_summary.json",
    "student_summaries": "student_summary.json",
    "misunderstood_questions": "misunderstood_questions.json",
    "cognitive_gaps": "cognitive_gap_analysis.json",
    "weak_topics": "weak_topics.json",
}


def _safe_path_component(value: object) -> str:
    text = re.sub(r'[<>:"/\\|?*]+', "_", str(value)).strip()
    return re.sub(r"\s+", "_", text) or "UNKNOWN"


def create_analysis_output_dir(
    output_base: Path,
    exam_data: dict,
    *,
    year: Optional[int] = None,
    timestamp: Optional[str] = None,
) -> Path:
    """Create and return a stable, timestamped analysis output directory."""
    output_year = year if year is not None else exam_data.get("year", "UNKNOWN")
    exam_name = _safe_path_component(exam_data.get("exam", "PAPERS"))
    run_timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = output_base / str(output_year) / exam_name / run_timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_analysis_outputs(results: dict, output_dir: Path) -> None:
    """Write all supported analytical result collections as JSON."""
    for result_key, filename in _OUTPUT_FILES.items():
        with (output_dir / filename).open("w", encoding="utf-8") as handle:
            json.dump(results.get(result_key, []), handle, indent=2)
