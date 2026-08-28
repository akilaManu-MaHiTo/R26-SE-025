"""Canonicalize fragmented topic labels into unified canonical topics."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from app.analytics.student_document import performance_status

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

def _load_taxonomy() -> dict[str, dict]:
    # canonical source is config/topic_taxonomy.json, enriched via app.taxonomy.normalizer
    from app.taxonomy.normalizer import load_taxonomy as _load_norm_taxonomy

    return _load_norm_taxonomy()


def _load_thresholds() -> list[dict]:
    with open(_CONFIG_DIR / "thresholds.json", encoding="utf-8") as f:
        return json.load(f)["status_thresholds"]

def _build_alias_map(taxonomy: dict[str, dict]) -> dict[str, str]:
    from app.taxonomy.normalizer import normalize_topic  # noqa: F401 - ensure cache built

    # case-insensitive map: alias.casefold -> canonical_id + canonical_topic.casefold
    alias_map: dict[str, str] = {}
    for canonical_id, entry in taxonomy.items():
        canon = entry.get("canonical_topic", "")
        if canon:
            alias_map[canon.casefold().strip()] = canonical_id
        for alias in entry.get("aliases", []):
            alias_map[alias.casefold().strip()] = canonical_id
        alias_map[canonical_id.casefold()] = canonical_id
    return alias_map

def _resolve_priority(status: str, thresholds: list[dict]) -> str:
    for t in thresholds:
        if t["status"] == status:
            return t["priority"]
    return "Medium"

async def canonicalize_topics(
    db, document: dict[str, Any], course_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
) -> dict[str, Any]:
    taxonomy = _load_taxonomy()
    thresholds = _load_thresholds()
    alias_map = _build_alias_map(taxonomy)
    raw_topics = document.get("topic_performance", [])
    question_perf = document.get("question_performance", [])

    # Build canonical_id -> list of raw topic strings
    canonical_fragments: dict[str, list[str]] = {cid: [] for cid in taxonomy}

    # Map each raw topic to its canonical ID (case-insensitive)
    topic_to_canonical: dict[str, str] = {}
    unmapped: list[str] = []
    for t in raw_topics:
        raw_name = t["topic"]
        key = raw_name.casefold().strip()
        cid = alias_map.get(key)
        # fallback substring for noisy OCR merges
        if not cid:
            for alias_key, alias_cid in alias_map.items():
                if len(alias_key) > 5 and (alias_key in key or key in alias_key):
                    cid = alias_cid
                    break
        if cid:
            topic_to_canonical[raw_name] = cid
            canonical_fragments.setdefault(cid, []).append(raw_name)
        else:
            unmapped.append(raw_name)

    # Fetch raw submissions for recomputation
    submissions_query: dict = {"subject_code": course_code, "session_name": session_name, "status": "graded"}
    if year is not None:
        submissions_query["year"] = year
    if month is not None:
        submissions_query["month"] = month
    if semester is not None:
        submissions_query["semester"] = semester
    submissions = await db["submissions"].find(
        submissions_query,
        {"_id": 0, "student_id": 1, "evaluation.results": 1}
    ).to_list(length=500)

    # Build question -> canonical_topic mapping (case-insensitive)
    question_canonical: dict[str, str] = {}
    for qp in question_perf:
        raw_topic = qp.get("topic", "")
        cid = topic_to_canonical.get(raw_topic)
        if not cid:
            # try alias map directly for question topics not in topic_performance
            key = raw_topic.casefold().strip()
            cid = alias_map.get(key)
        if cid:
            question_canonical[qp["question_id"]] = cid
        elif raw_topic:
            # still unmapped, try substring
            for alias_key, alias_cid in alias_map.items():
                if len(alias_key) > 5 and alias_key in raw_topic.casefold():
                    question_canonical[qp["question_id"]] = alias_cid
                    break

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

    # Fetch rubric to build question_max_map {qid: max_marks}
    # Wire criterion evidence: use authoritative rubric max not reverse pct estimation
    question_max_map: dict[str, float] = {}
    rubric_available = False
    rubric_doc = None
    # Try find_rubric_for_submission via repository helper for first submission
    if submissions:
        try:
            from app.db.repository import find_rubric_for_submission as _find_rubric
            rubric_doc = await _find_rubric(db, submissions[0])
        except Exception:
            rubric_doc = None
    if rubric_doc is None:
        # Fallback direct query on rubricCollection
        try:
            query: dict = {"subject_code": course_code, "session_name": session_name}
            if year is not None:
                query["year"] = year
            if month is not None:
                query["month"] = month
            if semester is not None:
                query["semester"] = semester
            rubric_doc = await db["rubricCollection"].find_one(query)
            if rubric_doc is None and (year is not None or month is not None or semester is not None):
                rubric_doc = await db["rubricCollection"].find_one(
                    {"subject_code": course_code, "session_name": session_name}
                )
        except Exception:
            rubric_doc = None
    if rubric_doc is not None:
        for rq in rubric_doc.get("questions") or []:
            raw_qno = rq.get("question_no") or rq.get("q_no") or ""
            norm = str(raw_qno).strip()
            norm = norm.zfill(2) if norm.isdigit() else norm
            qid = f"Q{norm}"
            # max_marks from rubric, fallback sum of criteria marks
            max_marks_val: float | None = None
            if rq.get("max_marks") is not None:
                try:
                    max_marks_val = float(rq.get("max_marks"))
                except Exception:
                    max_marks_val = None
            if max_marks_val is None or max_marks_val <= 0:
                criteria = rq.get("criteria") or []
                try:
                    summed = sum(float(c.get("marks", 0)) for c in criteria)
                except Exception:
                    summed = 0.0
                if summed > 0:
                    max_marks_val = float(summed)
            if max_marks_val is not None and max_marks_val > 0:
                question_max_map[qid] = float(max_marks_val)
                # also store without zero-pad variant for robustness
                alt = f"Q{str(raw_qno).strip()}"
                if alt != qid:
                    question_max_map[alt] = float(max_marks_val)
        rubric_available = bool(question_max_map)

    # Build canonical_topic_performance
    canonical_topic_perf = []
    for cid, entry in taxonomy.items():
        frags = canonical_fragments.get(cid, [])
        if not frags:
            continue
        total_score = canonical_score.get(cid, 0.0)
        is_estimated = True
        est_max = 0.0
        qids = canonical_qids.get(cid, set())
        s_count_for_cid = len(student_set.get(cid, set()))
        # Prefer rubric-based max: est_max = sum(question_max_map[qid] * num_students)
        if rubric_available and qids and s_count_for_cid > 0:
            sum_per_student = sum(question_max_map.get(qid, 0) for qid in qids)
            if sum_per_student > 0:
                est_max = sum_per_student * s_count_for_cid
                is_estimated = False
        if is_estimated:
            # Fallback reverse pct math (old method)
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
            "topic": entry["canonical_topic"],
            "average_percentage": avg_pct,
            "status": status,
            "priority": priority,
            "question_count": q_count,
            "student_count": s_count,
            "contributing_fragments": frags,
            "is_estimated": is_estimated,
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
