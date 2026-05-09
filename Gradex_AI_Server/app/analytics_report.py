from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_ROOT = PROJECT_ROOT / "Question-ExamPredictionEngine"
ANALYZER_SCRIPT = ANALYTICS_ROOT / "src" / "analysis" / "grading" / "analyze_exam.py"
OUTPUT_DIR = ANALYTICS_ROOT / "output"

REPORT_FILES = {
    "student_report": OUTPUT_DIR / "student_report.json",
    "student_summary": OUTPUT_DIR / "student_summary.json",
    "misunderstood_questions": OUTPUT_DIR / "misunderstood_questions.json",
    "cognitive_gap_analysis": OUTPUT_DIR / "cognitive_gap_analysis.json",
    "weak_topics": OUTPUT_DIR / "weak_topics.json",
    "results": OUTPUT_DIR / "results.json",
    "final_report": OUTPUT_DIR / "final_report.json",
}


def _read_json(path: Path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _title_case(value: str | None) -> str:
    if not value:
        return ""
    return str(value).replace("_", " ").strip().title()


def _level_number(value: str | None) -> int:
    levels = {
        "remember": 1,
        "understand": 2,
        "apply": 3,
        "analyze": 4,
        "evaluate": 5,
        "create": 6,
    }
    return levels.get(str(value or "").strip().lower(), 3)


def _build_distribution(student_summary: list[dict]) -> list[dict]:
    buckets = [
        {"band": "0-39", "min": 0, "max": 39, "c": 0, "fill": "#ef4444"},
        {"band": "40-54", "min": 40, "max": 54, "c": 0, "fill": "#f59e0b"},
        {"band": "55-69", "min": 55, "max": 69, "c": 0, "fill": "#3b82f6"},
        {"band": "70-84", "min": 70, "max": 84, "c": 0, "fill": "#10b981"},
        {"band": "85-100", "min": 85, "max": 100, "c": 0, "fill": "#059669"},
    ]
    for entry in student_summary:
        avg = round(float(entry.get("average_learning_score", 0)) * 100)
        for bucket in buckets:
            if bucket["min"] <= avg <= bucket["max"]:
                bucket["c"] += 1
                break
    return [{"band": bucket["band"], "c": bucket["c"], "fill": bucket["fill"]} for bucket in buckets]


def _build_students(student_summary: list[dict]) -> list[dict]:
    band_map = {"high": "high", "medium": "mid", "low": "low"}
    students = []
    for entry in student_summary:
        avg = round(float(entry.get("average_learning_score", 0)) * 100, 1)
        students.append(
            {
                "id": entry.get("student_id", "UNKNOWN"),
                "avg": avg,
                "band": band_map.get(str(entry.get("performance_band", "")).strip().lower(), "mid"),
                "weak": entry.get("weak_questions", []) or [],
                "cog": _title_case(entry.get("dominant_cognitive_level")) or "Apply",
                "scoreMap": {},
            }
        )
    return students


def _build_heatmap(student_report: list[dict]) -> tuple[list[str], list[str], list[list[int]]]:
    student_ids: list[str] = []
    question_ids: list[str] = []
    by_student: dict[str, dict[str, int]] = {}

    for row in student_report:
        student_id = str(row.get("student_id", "UNKNOWN"))
        question_id = f"Q{row.get('question', '')}{row.get('part', '')}"
        value = max(0, min(10, round(float(row.get("learning_score", 0)) * 10)))

        if student_id not in by_student:
            by_student[student_id] = {}
            student_ids.append(student_id)
        if question_id not in question_ids:
            question_ids.append(question_id)
        by_student[student_id][question_id] = value

    heat_data = [
        [by_student.get(student_id, {}).get(question_id, 0) for question_id in question_ids]
        for student_id in student_ids
    ]
    return student_ids, question_ids, heat_data


def _build_cognitive_scatter(cognitive_gap_analysis: list[dict]) -> list[dict]:
    return [
        {
            "expected": _level_number(row.get("required")),
            "actual": _level_number(row.get("average_student_level")),
            "label": row.get("question", ""),
        }
        for row in cognitive_gap_analysis
    ]


def _build_bloom_ladder(student_report: list[dict]) -> list[dict]:
    grouped: dict[str, list[float]] = {}
    for row in student_report:
        grouped.setdefault(str(row.get("required_level", "")).strip().lower(), []).append(
            float(row.get("learning_score", 0)) * 100
        )

    colors = [
        "bg-emerald-300",
        "bg-emerald-400",
        "bg-emerald-500",
        "bg-blue-500",
        "bg-indigo-500",
        "bg-violet-500",
    ]
    ladder = []
    for level_name, level_number in sorted(
        [("remember", 1), ("understand", 2), ("apply", 3), ("analyze", 4), ("evaluate", 5), ("create", 6)],
        key=lambda item: item[1],
    ):
        values = grouped.get(level_name, [])
        if not values:
            continue
        ladder.append(
            {
                "l": _title_case(level_name),
                "v": round(sum(values) / len(values)),
                "c": colors[level_number - 1],
            }
        )
    return ladder


def _build_topic_mastery(student_report: list[dict]) -> tuple[list[str], list[list[int]]]:
    topics: list[str] = []
    per_student: dict[str, dict[str, list[float]]] = {}

    for row in student_report:
        student_id = str(row.get("student_id", "UNKNOWN"))
        topic = str(row.get("topic", "Unknown"))
        if topic not in topics:
            topics.append(topic)
        per_student.setdefault(student_id, {}).setdefault(topic, []).append(float(row.get("learning_score", 0)) * 100)

    student_ids = list(per_student.keys())
    matrix: list[list[int]] = []
    for student_id in student_ids:
        row: list[int] = []
        for topic in topics:
            values = per_student[student_id].get(topic, [])
            row.append(round(sum(values) / len(values)) if values else 0)
        matrix.append(row)
    return topics, matrix


def _build_problem_questions(misunderstood_questions: list[dict], student_report: list[dict]) -> list[dict]:
    by_question: dict[str, list[dict]] = {}
    for row in student_report:
        question_id = f"Q{row.get('question', '')}{row.get('part', '')}"
        by_question.setdefault(question_id, []).append(row)

    problems = []
    for row in misunderstood_questions:
        question_id = str(row.get("question", ""))
        rows = by_question.get(question_id, [])
        if not rows:
            continue
        below_pct = sum(1 for item in rows if float(item.get("learning_score", 0)) < 0.6) / len(rows)
        avg_score = sum(float(item.get("learning_score", 0)) for item in rows) / len(rows)
        problems.append(
            {
                "q": question_id,
                "below": f"{round(below_pct * 100)}%",
                "avg": round(avg_score * 10, 1),
                "req": _title_case(row.get("required")) or "Apply",
                "act": _title_case(row.get("average_student_level")) or "Apply",
                "belowPct": below_pct,
            }
        )
    return [problem for problem in problems if problem["belowPct"] >= 0.3][:5]


def build_exam_report() -> dict:
    files = {name: _read_json(path) for name, path in REPORT_FILES.items()}
    student_report = files.get("student_report") or []
    student_summary = files.get("student_summary") or []
    cognitive_gap_analysis = files.get("cognitive_gap_analysis") or []
    misunderstood_questions = files.get("misunderstood_questions") or []

    students = _build_students(student_summary)
    distribution = _build_distribution(student_summary)
    heat_students, heat_questions, heat_data = _build_heatmap(student_report)
    cognitive_scatter = _build_cognitive_scatter(cognitive_gap_analysis)
    bloom_ladder = _build_bloom_ladder(student_report)
    topics, topic_mastery = _build_topic_mastery(student_report)
    problem_questions = _build_problem_questions(misunderstood_questions, student_report)

    at_risk = sum(1 for entry in student_summary if str(entry.get("performance_band", "")).strip().lower() == "low")
    avg_score = 0.0
    if student_summary:
        avg_score = sum(float(entry.get("average_learning_score", 0)) * 100 for entry in student_summary) / len(student_summary)
    cog_gaps = sum(1 for entry in cognitive_gap_analysis if str(entry.get("gap", "")).strip().upper() != "LOW")

    summary = {
        "total": len(students),
        "atRisk": at_risk,
        "avgScore": round(avg_score, 1),
        "cogGaps": cog_gaps,
        "problemCount": len(problem_questions),
    }

    return {
        "source": "Question-ExamPredictionEngine",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "students": students,
        "distribution": distribution,
        "heatStudents": heat_students,
        "heatQs": heat_questions,
        "heatData": heat_data,
        "cognitiveScatter": cognitive_scatter,
        "bloomLadder": bloom_ladder,
        "topics": topics,
        "topicMastery": topic_mastery,
        "problemQs": problem_questions,
        "files": files,
    }


def run_exam_analysis() -> dict:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    process = subprocess.run(
        [sys.executable, str(ANALYZER_SCRIPT)],
        cwd=str(ANALYTICS_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip() or "Analytics pipeline failed."
        raise RuntimeError(message)
    return build_exam_report()