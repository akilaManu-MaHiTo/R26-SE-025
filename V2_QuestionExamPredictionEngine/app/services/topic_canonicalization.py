"""Canonicalize fragmented topic labels into unified canonical topics."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from app.analytics.student_document import performance_status

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

def _load_taxonomy() -> dict[str, dict]:
    with open(_CONFIG_DIR / "topic_taxonomy.json", encoding="utf-8") as f:
        return json.load(f)

def _load_thresholds() -> list[dict]:
    with open(_CONFIG_DIR / "thresholds.json", encoding="utf-8") as f:
        return json.load(f)["status_thresholds"]

def _build_alias_map(taxonomy: dict[str, dict]) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for canonical_id, entry in taxonomy.items():
        for alias in entry.get("aliases", []):
            alias_map[alias] = canonical_id
    return alias_map

def _resolve_priority(status: str, thresholds: list[dict]) -> str:
    for t in thresholds:
        if t["status"] == status:
            return t["priority"]
    return "Medium"

async def canonicalize_topics(
    db, document: dict[str, Any], course_code: str, session_name: str
) -> dict[str, Any]:
    taxonomy = _load_taxonomy()
    thresholds = _load_thresholds()
    alias_map = _build_alias_map(taxonomy)
    raw_topics = document.get("topic_performance", [])
    question_perf = document.get("question_performance", [])

    # Build canonical_id -> list of raw topic strings
    canonical_fragments: dict[str, list[str]] = {cid: [] for cid in taxonomy}

    # Map each raw topic to its canonical ID
    topic_to_canonical: dict[str, str] = {}
    unmapped: list[str] = []
    for t in raw_topics:
        raw_name = t["topic"]
        if raw_name in alias_map:
            cid = alias_map[raw_name]
            topic_to_canonical[raw_name] = cid
            canonical_fragments.setdefault(cid, []).append(raw_name)
        else:
            unmapped.append(raw_name)

    # Fetch raw submissions for recomputation
    submissions = await db["submissions"].find(
        {"subject_code": course_code, "session_name": session_name, "status": "graded"},
        {"_id": 0, "student_id": 1, "evaluation.results": 1}
    ).to_list(length=500)

    # Build question -> canonical_topic mapping
    question_canonical: dict[str, str] = {}
    for qp in question_perf:
        raw_topic = qp.get("topic", "")
        if raw_topic in topic_to_canonical:
            question_canonical[qp["question_id"]] = topic_to_canonical[raw_topic]

    # Recompute canonical topic averages from raw scores
    canonical_score: dict[str, float] = {}
    canonical_max: dict[str, float] = {}
    canonical_qids: dict[str, set[str]] = {}
    student_set: dict[str, set[str]] = {}

    for sub in submissions:
        sid = sub.get("student_id", "")
        results = (sub.get("evaluation") or {}).get("results") or []
        for r in results:
            q_id = f"Q{r.get('q_no', '')}"
            if q_id not in question_canonical:
                continue
            cid = question_canonical[q_id]
            score = float(r.get("score", 0))
            canonical_score[cid] = canonical_score.get(cid, 0.0) + score
            canonical_qids.setdefault(cid, set()).add(q_id)
            student_set.setdefault(cid, set()).add(sid)

    # Build canonical_topic_performance
    canonical_topic_perf = []
    for cid, entry in taxonomy.items():
        frags = canonical_fragments.get(cid, [])
        if not frags:
            continue
        total_score = canonical_score.get(cid, 0.0)
        # Estimate max: sum of (score / percentage * 100) for each question
        est_max = 0.0
        for qp in question_perf:
            if question_canonical.get(qp["question_id"]) == cid:
                pct = qp.get("average_percentage", 0)
                q_score = 0.0
                for sub in submissions:
                    results = (sub.get("evaluation") or {}).get("results") or []
                    for r in results:
                        if f"Q{r.get('q_no', '')}" == qp["question_id"]:
                            q_score += float(r.get("score", 0))
                if pct > 0 and q_score > 0:
                    est_max += q_score / (pct / 100.0)

        avg_pct = round(total_score / est_max * 100.0, 2) if est_max > 0 else 0.0
        status = performance_status(avg_pct)
        priority = _resolve_priority(status, thresholds)
        q_count = len(canonical_qids.get(cid, set()))
        s_count = len(student_set.get(cid, set()))

        canonical_topic_perf.append({
            "topic": entry["label"],
            "average_percentage": avg_pct,
            "status": status,
            "priority": priority,
            "question_count": q_count,
            "student_count": s_count,
            "contributing_fragments": frags,
            "is_estimated": False,
        })

    canonical_topic_perf.sort(key=lambda x: x["average_percentage"])

    # Build canonical_attention_areas
    attention_statuses = {"Critical", "Needs Improvement", "Developing"}
    canonical_attention = [
        {"type": "topic", "name": t["topic"], "average_percentage": t["average_percentage"],
         "priority": t["priority"], "question_count": t["question_count"],
         "student_count": t["student_count"]}
        for t in canonical_topic_perf if t["status"] in attention_statuses
    ]

    # Build canonical_insights
    canonical_insights = []
    if canonical_topic_perf:
        weakest = min(canonical_topic_perf, key=lambda x: x["average_percentage"])
        canonical_insights.append(
            f"{weakest['topic']} is the weakest topic at {weakest['average_percentage']}% "
            f"across {weakest['question_count']} questions and {weakest['student_count']} students."
        )
        strongest = max(canonical_topic_perf, key=lambda x: x["average_percentage"])
        canonical_insights.append(
            f"{strongest['topic']} is the strongest topic at {strongest['average_percentage']}%."
        )
    if question_perf:
        lowest_q = min(question_perf, key=lambda x: x["average_percentage"])
        canonical_insights.append(
            f"Question {lowest_q['question_id']} was the lowest-performing question "
            f"at {lowest_q['average_percentage']}%."
        )

    return {
        "canonical_topic_performance": canonical_topic_perf,
        "canonical_attention_areas": canonical_attention,
        "canonical_insights": canonical_insights,
        "unmapped_topics": unmapped,
    }
