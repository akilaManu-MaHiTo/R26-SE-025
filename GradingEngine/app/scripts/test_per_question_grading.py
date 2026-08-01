"""
Test per-question grading locally without depending on live Colab.

Usage (from GradingEngine directory):
    python -m app.scripts.test_per_question_grading
    python -m app.scripts.test_per_question_grading --with-colab
    python -m app.scripts.test_per_question_grading --with-local-colab
    python -m app.scripts.test_per_question_grading --splitter-only

Default: skip Colab (force Groq / emergency fallback) so the run is fast.
--with-local-colab: starts a mock Flask /evaluate server (COLAB_USE_MOCK=1).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


SAMPLE_TRANSCRIPT = """
Question 1
Two-phase locking has a growing phase where locks are acquired and a shrinking
phase where locks are released. The lock point is when the last lock is taken.

Q2
During the shrinking phase a transaction may only release locks and cannot
request new ones. This helps guarantee serializability.
""".strip()

SAMPLE_RUBRIC = {
    "session_name": "Per-question grading test",
    "subject_code": "SE3040",
    "questions": [
        {
            "question_no": "01",
            "question_text": "Explain the two phases of 2PL and the lock point.",
            "max_marks": 5,
            "criteria": [
                {"point": "Mentions growing phase", "marks": 2},
                {"point": "Mentions shrinking phase", "marks": 2},
                {"point": "Defines lock point", "marks": 1},
            ],
        },
        {
            "question_no": "02",
            "question_text": "What happens during the shrinking phase of 2PL?",
            "max_marks": 5,
            "criteria": [
                {"point": "Locks may be released", "marks": 3},
                {"point": "No new locks may be acquired", "marks": 2},
            ],
        },
    ],
}

LOCAL_COLAB_URL = "http://127.0.0.1:5000/evaluate"
LOCAL_COLAB_HEALTH = "http://127.0.0.1:5000/health"


def test_rag_course_filter() -> None:
    from app.services.rag_service import list_indexed_lectures, retrieve_relevant_context

    print("\n=== RAG COURSE FILTER ===")
    items = list_indexed_lectures()
    print(f"Indexed lecture files: {len(items)}")
    for item in items[:5]:
        print(
            f"  - {item.get('course_name')} | {item.get('filename')} | "
            f"{item.get('indexed_items')} chunks"
        )

    if not items:
        print("No indexed materials yet — upload on Page 8 to verify course filtering.")
        return

    course = str(items[0].get("course_name") or "").strip()
    other = "___NO_SUCH_COURSE___"
    hit = retrieve_relevant_context("locking shrinking phase", course_name=course)
    miss = retrieve_relevant_context("locking shrinking phase", course_name=other)
    print(
        f"Filter course={course!r} used={hit['rag_context_used']} "
        f"chunks={hit['rag_chunks']} preview: "
        f"{str(hit['snippet'])[:120].replace(chr(10), ' ')}..."
    )
    print(
        f"Filter course={other!r} used={miss['rag_context_used']} "
        f"chunks={miss['rag_chunks']}: {miss['snippet']}"
    )


def test_splitter() -> dict:
    from app.services.answer_splitter import (
        resolve_answer_for_question,
        split_transcript_by_questions,
    )

    buckets = split_transcript_by_questions(SAMPLE_TRANSCRIPT, SAMPLE_RUBRIC["questions"])
    print("\n=== ANSWER SPLITTER ===")
    print(f"Buckets found: {sorted(buckets.keys()) or '(none)'}")
    for q_no, text in sorted(buckets.items()):
        preview = text.replace("\n", " ")[:100]
        print(f"  Q{q_no}: {preview}...")

    sources = {}
    for idx, question in enumerate(SAMPLE_RUBRIC["questions"], start=1):
        _, source = resolve_answer_for_question(
            SAMPLE_TRANSCRIPT, question, buckets, idx
        )
        sources[question["question_no"]] = source
    print(f"Per-question sources: {sources}")
    return {"buckets": buckets, "sources": sources}


def _point_module_at_local_colab() -> None:
    os.environ["COLAB_EVALUATE_URL"] = LOCAL_COLAB_URL
    import app.services.ai_model_route as route

    route.COLAB_URL = LOCAL_COLAB_URL


def start_local_mock_colab() -> subprocess.Popen | None:
    """Start Flask mock server if nothing is already listening on :5000."""
    try:
        health = requests.get(LOCAL_COLAB_HEALTH, timeout=1)
        if health.ok:
            print(f"Local Colab already running at {LOCAL_COLAB_HEALTH} ({health.json()})")
            _point_module_at_local_colab()
            return None
    except requests.RequestException:
        pass

    env = os.environ.copy()
    env["COLAB_USE_MOCK"] = "1"
    # Avoid ngrok attempts when running the local mock.
    env["COLAB_SKIP_NGROK"] = "1"
    server_path = ROOT / "colab" / "colab_evaluate_server.py"
    print(f"Starting local mock Colab: {server_path}")
    log_path = ROOT / "colab_mock_server.log"
    log_file = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(server_path)],
        cwd=str(ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    for _ in range(40):
        time.sleep(0.25)
        try:
            health = requests.get(LOCAL_COLAB_HEALTH, timeout=1)
            if health.ok:
                print(f"Local mock Colab ready: {health.json()}")
                _point_module_at_local_colab()
                log_file.close()
                return proc
        except requests.RequestException:
            if proc.poll() is not None:
                break

    proc.terminate()
    log_file.close()
    details = ""
    if log_path.exists():
        details = log_path.read_text(encoding="utf-8", errors="replace")[-800:]
    raise RuntimeError(
        "Local mock Colab failed to start on port 5000. "
        f"Install flask (`pip install flask`) if missing.\n{details}"
    )


async def test_grading(skip_colab: bool) -> dict:
    if skip_colab:
        # Fail Colab instantly so we exercise Groq / emergency path.
        import app.services.ai_model_route as route

        route.try_forward_to_colab = lambda payload: None  # type: ignore[assignment]
        print("\n=== GRADING (Colab skipped -> Groq/emergency) ===")
    else:
        print("\n=== GRADING (Colab first, then Groq fallback) ===")
        print(f"COLAB_EVALUATE_URL: {os.getenv('COLAB_EVALUATE_URL')}")

    from app.services.llm_service import generate_grading_report

    evaluation = await generate_grading_report(SAMPLE_TRANSCRIPT, SAMPLE_RUBRIC)
    return evaluation


def print_evaluation(evaluation: dict) -> None:
    print("\n=== RESULT SUMMARY ===")
    print(f"grading_source : {evaluation.get('grading_source')}")
    print(f"total_score    : {evaluation.get('total_score')}")
    print(f"max_score      : {evaluation.get('max_score')}")
    print(f"rag_context_used: {evaluation.get('rag_context_used')}")
    print(f"rag_chunks     : {evaluation.get('rag_chunks')}")
    print(f"rag_course     : {evaluation.get('rag_course')}")

    split_meta = evaluation.get("answer_split") or {}
    print(f"buckets_found  : {split_meta.get('buckets_found')}")
    print(f"slice_sources  : {split_meta.get('per_question_source')}")

    print("\n=== PER-QUESTION RESULTS ===")
    for row in evaluation.get("results") or []:
        print("-" * 40)
        print(f"q_no           : {row.get('q_no')}")
        print(f"score          : {row.get('score')}")
        justification = str(row.get("justification") or "")[:200]
        feedback = str(row.get("feedback") or "")[:200]
        print(f"justification  : {justification}")
        print(f"feedback       : {feedback}")

    out_path = ROOT / "test_per_question_grading_output.json"
    out_path.write_text(json.dumps(evaluation, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFull JSON written to: {out_path}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test per-question grading locally.")
    parser.add_argument(
        "--splitter-only",
        action="store_true",
        help="Only test local regex splitting (no LLM calls).",
    )
    parser.add_argument(
        "--with-colab",
        action="store_true",
        help="Try whatever COLAB_EVALUATE_URL points at (live ngrok or local).",
    )
    parser.add_argument(
        "--with-local-colab",
        action="store_true",
        help="Start mock Flask Colab on :5000 and grade through it (no live Colab needed).",
    )
    args = parser.parse_args()

    print("GradingEngine per-question grading smoke test")
    print(f"Working dir: {ROOT}")
    print(f"AI_API_KEY set: {bool(os.getenv('AI_API_KEY') or os.getenv('BACKUP_API_KEY'))}")

    splitter_info = test_splitter()
    if not splitter_info["buckets"]:
        print("WARNING: expected split buckets for the sample transcript.")

    test_rag_course_filter()

    if args.splitter_only:
        print("\nSplitter-only mode done.")
        return

    mock_proc: subprocess.Popen | None = None
    try:
        if args.with_local_colab:
            mock_proc = start_local_mock_colab()
            skip_colab = False
        else:
            skip_colab = not args.with_colab

        evaluation = await test_grading(skip_colab=skip_colab)
        print_evaluation(evaluation)

        results = evaluation.get("results") or []
        if len(results) != len(SAMPLE_RUBRIC["questions"]):
            print(
                f"\nWARNING: expected {len(SAMPLE_RUBRIC['questions'])} result rows, "
                f"got {len(results)}."
            )
        else:
            print(f"\nOK: got {len(results)} per-question result row(s).")

        if args.with_local_colab and evaluation.get("grading_source") != "colab":
            print(
                f"WARNING: expected grading_source=colab with --with-local-colab, "
                f"got {evaluation.get('grading_source')!r}."
            )
        elif args.with_local_colab:
            print("OK: local mock Colab path returned grading_source=colab.")
    finally:
        if mock_proc is not None:
            mock_proc.terminate()
            try:
                mock_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                mock_proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
