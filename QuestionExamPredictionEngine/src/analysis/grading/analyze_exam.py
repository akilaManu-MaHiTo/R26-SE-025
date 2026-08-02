"""Command-line adapter for the shared exam-analysis service."""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.exam_analysis import analyze_exam_records
from src.analysis.reporting import create_analysis_output_dir, write_analysis_outputs


def _load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze one historical exam year")
    parser.add_argument("--year", type=int, default=2021)
    args = parser.parse_args()

    exam_path = PROJECT_ROOT / "data" / "exams" / f"exam{args.year}.json"
    answers_path = (
        PROJECT_ROOT
        / "data"
        / "answers"
        / f"student_answers{args.year}.json"
    )
    model_answer_path = (
        PROJECT_ROOT
        / "data"
        / "model_answer"
        / f"model_answer_{args.year}.json"
    )

    exam_data = _load_json(exam_path)
    student_data = _load_json(answers_path)
    model_answers = (
        _load_json(model_answer_path)
        if model_answer_path.exists()
        else {}
    )

    results = analyze_exam_records(exam_data, student_data, model_answers)
    output_dir = create_analysis_output_dir(
        PROJECT_ROOT / "output",
        exam_data,
        year=args.year,
    )
    write_analysis_outputs(results, output_dir)

    print("Analytics completed")
    print(f"Student reports: {len(results['student_reports'])}")
    print(f"Weak topics: {len(results['weak_topics'])}")
    print(f"Misunderstood questions: {len(results['misunderstood_questions'])}")
    print(f"Cognitive gaps: {len(results['cognitive_gaps'])}")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
