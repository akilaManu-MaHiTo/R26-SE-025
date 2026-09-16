"""Generator that computes and persists lecturer-facing exam analytics."""

from datetime import datetime, timezone

from collections.abc import Callable

from app.analytics.diagram_analysis import compute_diagram_analysis
from app.analytics.exam_analytics import compute_exam_analytics_stats
from app.analytics.student_document import build_numeric_analysis, performance_status
from app.analytics.weakness import compute_weakness_scores
from app.db.repository import (
    find_course_for_submission,
    find_diagram_evaluations_for_exam,
    find_diagram_markings_for_exam,
    find_graded_submissions_for_exam,
    find_rubric_for_submission,
    upsert_exam_analytics,
    upsert_exam_analysis_status,
)
from app.ingestion.student_data import normalize_student_submission
from app.services import student_pipeline as _student_pipeline


class ExamNotFound(Exception):
    """Raised when no graded submissions exist for the requested exam."""


async def compute_exam_analytics(
    db, course_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict:
    def _progress(msg: str):
        # Real-time server terminal log for exam analyze (Bloom)
        print(f"[ExamAnalyze] {msg}", flush=True)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass
    submissions = await find_graded_submissions_for_exam(db, course_code, session_name, year, month, semester)
    if not submissions:
        raise ExamNotFound(f"no graded submissions for {course_code} {session_name}")

    _progress(f"PULSE·AI — Ingesting {len(submissions)} submissions for {course_code} {session_name}...")
    _progress(f"PULSE·AI — Resolving course/rubric once for {course_code} {session_name}...")
    # A: reuse course/rubric — N+1 query fan-out → 1 query (same exam identity)
    first_ref = submissions[0] if submissions else {}
    course = await find_course_for_submission(db, first_ref)
    rubric = await find_rubric_for_submission(db, first_ref)
    students: list[dict] = []
    classification_cache: dict = {}
    total_q = 0
    for idx, submission in enumerate(submissions):
        _progress(f"Analyzing student {submission.get('student_id', 'unknown')} ({idx+1}/{len(submissions)}) — normalizing...")
        normalized = normalize_student_submission(course or {}, rubric or {}, submission)
        total_q = len(normalized.questions)

        def _q_progress(msg: str):
            # msg is like "classify q01" or "classify q01 (cached)"
            # enrich to Bloom/topic after classification
            _progress(f"PULSE·AI — {msg} — checking Bloom level...")

        semantics = await _student_pipeline._classify_questions(normalized, classification_cache, progress=_q_progress, db=db)
        # After classify, emit per-question Bloom/topic details
        for q_no in sorted(semantics.keys()):
            sem = semantics[q_no]
            _progress(f"PULSE·AI — Q{q_no} Bloom: {sem.level} · Topic: {sem.topic} · Confidence: {sem.confidence:.2f}")
        numeric = build_numeric_analysis(normalized, semantics)
        # Determine low-confidence threshold for review flag
        from app.config import settings as _settings
        low_conf_threshold = float(getattr(_settings, "bloom_model_threshold", 0.6))
        students.append(
            {
                "overall": numeric.overall_performance.model_dump(),
                "topic_performance": [topic.model_dump() for topic in numeric.topic_performance],
                "bloom_performance": [bloom.model_dump() for bloom in numeric.bloom_performance],
                "question_performance": [
                    {
                        "question_no": q.question_no,
                        "topic": q.topic,
                        "bloom_level": q.bloom_analysis.level,
                        "score": q.performance.score,
                        "max_score": q.performance.max_score,
                        "criteria_performance": [c.model_dump() for c in q.criteria_performance],
                        # Preserve classification traceability
                        "bloom_confidence": float(semantics.get(q.question_no).confidence) if semantics.get(q.question_no) else None,
                        "bloom_model_version": "modernbert-bloom-v1",
                        "topic_source": str(semantics.get(q.question_no).reason) if semantics.get(q.question_no) else "unknown",
                        "needs_review": bool(semantics.get(q.question_no) and float(semantics.get(q.question_no).confidence) < low_conf_threshold) or q.topic == "Unclassified",
                    }
                    for q in numeric.question_performance
                ],
            }
        )

    _progress(f"PULSE·AI — Computing class statistics for {len(students)} students (avg, pass rate, Bloom)...")
    stats = compute_exam_analytics_stats(students, pass_threshold=0.5)
    _progress("PULSE·AI — Canonicalizing topics from same evidence set...")
    # Build canonical aggregates from the same normalized evidence used for class stats
    # (avoids second DB query, 500 cap, and rubric re-estimation mismatch)
    from pathlib import Path as _Path
    import json as _json
    taxonomy = {}
    try:
        from app.taxonomy.normalizer import load_taxonomy as _load_tax, load_taxonomy_sync
        try:
            taxonomy = await _load_tax(db, course_code)
        except TypeError:
            taxonomy = load_taxonomy_sync(course_code)
    except Exception:
        try:
            from app.taxonomy.normalizer import load_taxonomy_sync as _sync2
            taxonomy = _sync2(course_code)
        except Exception:
            taxonomy = {}
    # thresholds for priority
    thresholds_cfg = []
    try:
        cfg_path = _Path(__file__).resolve().parents[2] / "config" / "thresholds.json"
        thresholds_cfg = _json.loads(cfg_path.read_text(encoding="utf-8")).get("status_thresholds", [])
    except Exception:
        thresholds_cfg = []
    def _resolve_priority(status: str) -> str:
        for t in thresholds_cfg:
            if t.get("status") == status:
                return t.get("priority", "Medium")
        return "Medium"
    # alias_map
    alias_map: dict[str, str] = {}
    for cid, entry in taxonomy.items():
        canon = entry.get("canonical_topic", "")
        if canon:
            alias_map[canon.casefold().strip()] = cid
        for alias in entry.get("aliases", []):
            k = alias.casefold().strip()
            if k:
                alias_map[k] = cid
        alias_map[cid.casefold()] = cid
    # Map raw topic -> canonical_id (case-insensitive, keep Unclassified separate)
    canonical_score: dict[str, float] = {}
    canonical_max: dict[str, float] = {}
    canonical_qids: dict[str, set[str]] = {}
    canonical_students: dict[str, set[int]] = {}
    canonical_fragments: dict[str, set[str]] = {}
    unmapped_topics: list[str] = []
    unclassified_score = 0.0
    unclassified_max = 0.0
    unclassified_count = 0
    # Build per-question canonical mapping from stats question_performance topics already aggregated?
    # Better: iterate students' question_performance directly for marks-weighted correctness
    for idx, st in enumerate(students):
        for q in st.get("question_performance", []):
            raw_topic = q.get("topic", "")
            if raw_topic == "Unclassified" or not raw_topic:
                # keep marks in overall/Bloom but exclude from named canonical conclusions
                unclassified_score += float(q.get("score", 0))
                unclassified_max += float(q.get("max_score", 0))
                unclassified_count += 1
                if raw_topic and raw_topic not in unmapped_topics:
                    # track for display but not as canonical fragment
                    pass
                continue
            key = raw_topic.casefold().strip()
            cid = alias_map.get(key)
            if not cid:
                # substring fallback for noisy labels
                for ak, av in alias_map.items():
                    if len(ak) > 5 and (ak in key or key in ak):
                        cid = av
                        break
            if not cid:
                if raw_topic not in unmapped_topics:
                    unmapped_topics.append(raw_topic)
                continue
            # found canonical
            canonical_fragments.setdefault(cid, set()).add(raw_topic)
            qid = f"Q{q.get('question_no','')}"
            canonical_score[cid] = canonical_score.get(cid, 0.0) + float(q.get("score", 0))
            canonical_max[cid] = canonical_max.get(cid, 0.0) + float(q.get("max_score", 0))
            canonical_qids.setdefault(cid, set()).add(qid)
            canonical_students.setdefault(cid, set()).add(idx)
    # Build canonical_topic_performance list
    canonical_topic_perf = []
    for cid, entry in taxonomy.items():
        score = canonical_score.get(cid, 0.0)
        max_s = canonical_max.get(cid, 0.0)
        if max_s <= 0 and cid not in canonical_fragments:
            continue
        # only emit if at least one fragment contributed
        frags = sorted(list(canonical_fragments.get(cid, set())))
        if not frags:
            continue
        avg_pct = round(score / max_s * 100.0, 2) if max_s > 0 else 0.0
        status = performance_status(avg_pct)
        priority = _resolve_priority(status)
        q_count = len(canonical_qids.get(cid, set()))
        s_count = len(canonical_students.get(cid, set()))
        canonical_topic_perf.append({
            "topic": entry.get("canonical_topic", cid),
            "average_percentage": avg_pct,
            "status": status,
            "priority": priority,
            "question_count": q_count,
            "student_count": s_count,
            "contributing_fragments": frags,
            "is_estimated": False,
        })
    canonical_topic_perf.sort(key=lambda x: x["average_percentage"])
    # Canonical attention areas (Critical/Needs Improvement/Developing)
    attention_statuses = {"Critical", "Needs Improvement", "Developing"}
    canonical_attention = [
        {"type": "topic", "name": t["topic"], "average_percentage": t["average_percentage"],
         "priority": t["priority"], "question_count": t["question_count"], "student_count": t["student_count"]}
        for t in canonical_topic_perf if t["status"] in attention_statuses
    ]
    # Canonical insights with supportable wording
    canonical_insights = []
    if canonical_topic_perf:
        weakest = min(canonical_topic_perf, key=lambda x: x["average_percentage"])
        canonical_insights.append(
            f"{weakest['topic']} is the weakest topic at {weakest['average_percentage']}% "
            f"across {weakest['question_count']} questions and {weakest['student_count']} students."
        )
        strongest = max(canonical_topic_perf, key=lambda x: x["average_percentage"])
        canonical_insights.append(f"{strongest['topic']} is the strongest topic at {strongest['average_percentage']}%.")
    # Add unclassified coverage note if present
    if unclassified_count > 0:
        pct_un = round(unclassified_score / unclassified_max * 100.0, 2) if unclassified_max > 0 else 0.0
        canonical_insights.append(
            f"Unclassified questions cover {unclassified_count} attempts at {pct_un}% — review topic assignment for these questions."
        )
    # Inject canonical fields into stats so they are persisted together
    stats["canonical_topic_performance"] = canonical_topic_perf
    stats["canonical_attention_areas"] = canonical_attention
    stats["canonical_insights"] = canonical_insights
    stats["unmapped_topics"] = unmapped_topics
    # Also expose unclassified coverage for frontend
    stats["unclassified_coverage"] = {
        "attempt_count": unclassified_count,
        "average_percentage": round(unclassified_score / unclassified_max * 100.0, 2) if unclassified_max > 0 else 0.0,
        "total_max": round(unclassified_max, 2),
    } if unclassified_count > 0 else None
    # Enrich question_performance with classification traceability (confidence, needs_review)
    try:
        # Build per-question aggregate from students' evidence
        q_conf: dict[str, list[float]] = {}
        q_review: dict[str, bool] = {}
        for st in students:
            for q in st.get("question_performance", []):
                qno = q.get("question_no")
                if not qno:
                    continue
                conf = q.get("bloom_confidence")
                if conf is not None:
                    q_conf.setdefault(qno, []).append(float(conf))
                if q.get("needs_review"):
                    q_review[qno] = True
        for qp in stats.get("question_performance", []):
            qno = qp.get("question_no")
            confs = q_conf.get(qno, [])
            qp["bloom_confidence"] = round(sum(confs)/len(confs), 4) if confs else None
            qp["needs_review"] = bool(q_review.get(qno, False))
            # Use supportable wording for low evidence: keep distinct counts already present
            if qp.get("attempt_count", 0) < 2 or qp.get("student_count", 0) < 10:
                qp["coverage_warning"] = "insufficient_evidence"
    except Exception:
        pass
    _progress("PULSE·AI — Detecting weak topics and attention areas...")
    try:
        stats["weakness_scores"] = compute_weakness_scores(
            canonical_topic_performance=stats.get("canonical_topic_performance"),
            topic_performance=stats.get("topic_performance"),
        )
        stats["weakest_topics"] = [
            t for t, _ in sorted(
                ((k, v["weakness"]) for k, v in stats["weakness_scores"].items()),
                key=lambda kv: kv[1],
                reverse=True,
            )
        ]
        if stats.get("weakest_topics"):
            _progress(f"PULSE·AI — Weakest topics: {', '.join(stats['weakest_topics'][:3])}")
    except Exception:
        pass
    _progress("PULSE·AI — Finalizing analytics document...")
    # Fetch max_marks from rubricCollection with criterion fallback (wire criterion evidence)
    def _question_max(q: dict) -> float:
        if q.get("max_marks") is not None:
            try:
                return float(q["max_marks"])
            except Exception:
                pass
        criteria = q.get("criteria") or []
        try:
            return float(sum(float(c.get("marks", 0)) for c in criteria))
        except Exception:
            return 0.0
    total_marks = sum(_question_max(q) for q in (rubric or {}).get("questions", []))
    question_count = len((rubric or {}).get("questions", []))
    course_name = str((course or {}).get("name") or (course or {}).get("course_name") or "").strip()
    if not course_name:
        course_name = "Database Management Systems" if course_code == "IT2040" else course_code
    subject_name = str((rubric or {}).get("subject_name") or course_name or "").strip() or course_code
    try:
        if year is None:
            year = int((rubric or {}).get("year") or 0)
        if month is None:
            month = int((rubric or {}).get("month") or 0)
        if semester is None:
            semester = int((rubric or {}).get("semester") or 0)
    except (TypeError, ValueError) as exc:
        raise ExamNotFound(f"invalid rubric session identity for {course_code} {session_name}") from exc
    # Merge diagram analysis if diagram_evaluation data exists for this exam
    diagram_analysis = None
    try:
        diagram_evals = await find_diagram_evaluations_for_exam(db, course_code, session_name, year, month, semester)
        diagram_marks = await find_diagram_markings_for_exam(db, course_code, session_name, year, month, semester)
        if diagram_evals:
            diagram_analysis = compute_diagram_analysis(diagram_evals, diagram_marks)
            if diagram_analysis:
                _progress(f"PULSE·AI — Diagram analysis: {diagram_analysis['statistics']['total_students']} students, avg {diagram_analysis['statistics']['average_percentage']:.1f}%")
    except Exception:
        pass

    document = {
        "subject_code": course_code,
        "subject_name": subject_name,
        "year": year,
        "month": month,
        "semester": semester,
        "session_name": session_name,
        "exam": {"session_name": session_name, "total_marks": total_marks, "question_count": question_count},
        **stats,
        "diagram_analysis": diagram_analysis,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analytics_version": "1.0",
    }
    _progress("PULSE·AI — Saving analytics to database...")
    await upsert_exam_analytics(db, document)
    await upsert_exam_analysis_status(
        db,
        {
            "subject_code": course_code,
            "subject_name": subject_name,
            "year": year,
            "month": month,
            "semester": semester,
            "session_name": session_name,
            "analyzed": "done",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return document
