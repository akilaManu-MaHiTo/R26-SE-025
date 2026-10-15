"""Paper checks, blueprint-aware selection, and grounded lecturer drafts."""
from collections import Counter
from difflib import SequenceMatcher
from math import isclose
from uuid import uuid4

from app.analytics.recommendation_score import priority_from_score
from app.analytics.taxonomy import BLOOM_LEVELS
from app.schemas.exam_creator import CreatorRequest, GenerateRequest, GroundedCandidate
from app.services import llm_service, recommendation


def course_bank(course_code: str, bank: list[dict] | None = None) -> list[dict]:
    bank = recommendation._load_question_bank() if bank is None else bank
    # Legacy bank rows encode the course in question_id. Never share an unknown row across courses.
    return [r for r in bank if str(r.get("course_code") or r.get("subject_code") or
            str(r.get("question_id", "")).split("_")[0]).upper() == course_code.upper()]


def normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def review_paper(request: CreatorRequest, analytics: dict, bank: list[dict]) -> dict:
    paper, blueprint = request.paper, request.paper.blueprint
    topics, blooms = Counter(), Counter()
    parts, seen, issues = [], {}, []
    estimated_minutes = 0.0
    estimated_parts = 0

    def issue(code, message):
        issues.append({"code": code, "message": message})

    for q in paper.questions:
        for p in q.get("parts", []):
            label = f"Q{q.get('question_number', '?')}{p.get('part', '')}"
            marks = p.get("max_marks", 0)
            topic = q.get("topic", "")
            if not topic.strip():
                issue("topic_missing", f"{label}: enter the assessed topic.")
            topics[topic] += marks
            blooms[p.get("bloom_level", "Unclassified")] += marks
            parts.append(p)
            text = normalized(p.get("question", ""))
            if not text or marks <= 0:
                issue("incomplete", f"{label}: enter question text and positive marks.")
            if text and text in seen:
                issue("duplicate", f"{label} repeats {seen[text]}.")
            seen[text] = label
            if p.get("bloom_level") not in BLOOM_LEVELS:
                issue("bloom_missing", f"{label}: assign a Bloom level.")
            if not p.get("model_answer", "").strip():
                issue("answer_missing", f"{label}: add a model answer.")
            scheme = p.get("marking_scheme") or []
            try:
                rubric_marks = sum(float(c["marks"]) for c in scheme)
                valid_rubric = bool(scheme) and all(float(c["marks"]) > 0 and str(c.get("criterion", "")).strip() for c in scheme)
            except (KeyError, TypeError, ValueError):
                valid_rubric, rubric_marks = False, 0
            if not valid_rubric or not isclose(rubric_marks, marks, abs_tol=0.01):
                issue("rubric", f"{label}: marking scheme must total {marks:g} marks.")
            if p.get("review_status") != "approved":
                issue("review_required", f"{label}: lecturer review is pending.")
            minutes = p.get("estimated_minutes")
            if isinstance(minutes, (int, float)) and 0 < minutes <= 1440:
                estimated_minutes += minutes
                estimated_parts += 1
            # Only flag explicit external dependencies; this is not semantic verification.
            if any(term in text for term in ("diagram below", "figure below", "schema below", "table below", "given diagram")):
                issue("supporting_material", f"{label}: verify the referenced diagram, table or schema is included.")

    total = sum(topics.values())
    remaining = blueprint.total_marks - total
    if not isclose(total, blueprint.total_marks, abs_tol=0.01):
        issue("total_marks", f"Paper has {total:g} of {blueprint.total_marks:g} required marks.")
    topic_coverage = {topic: {"target": target, "actual": topics[topic], "remaining": max(0, target - topics[topic])}
                      for topic, target in blueprint.topic_marks.items()}
    bloom_coverage = {level: {"target": blueprint.total_marks * blueprint.bloom_percentages.get(level, 0) / 100,
                              "actual": blooms[level]} for level in BLOOM_LEVELS}
    for topic, coverage in topic_coverage.items():
        if not isclose(coverage["target"], coverage["actual"], abs_tol=0.01):
            issue("topic_coverage", f"{topic}: {coverage['actual']:g}/{coverage['target']:g} marks.")
    for level, coverage in bloom_coverage.items():
        if not isclose(coverage["target"], coverage["actual"], abs_tol=0.01):
            issue("bloom_coverage", f"{level}: {coverage['actual']:g}/{coverage['target']:g} marks.")
    if estimated_parts < len(parts):
        issue("time_missing", "Some parts have no time estimate; the time total is incomplete.")
    if estimated_minutes > blueprint.duration_minutes:
        issue("duration", f"Estimated {estimated_minutes:g} minutes exceeds the {blueprint.duration_minutes}-minute duration.")
    if not blueprint.learning_outcomes.strip():
        issue("outcomes_missing", "Enter the learning outcomes to guide generation and lecturer review.")

    ranked = recommendation.recommend_questions(analytics, question_bank=bank,
        limit=len(bank), reference_year=paper.year, require_evidence=False)
    excluded = {p.get("question_id") for p in parts} | {r.question_id for r in paper.rejected_questions}
    selected_texts = {normalized(p.get("question", "")) for p in parts}
    candidates = []
    for candidate in ranked:
        topic, level = candidate["canonical_topic"], candidate.get("bloom_level")
        marks = candidate.get("marks", 0)
        if candidate["question_id"] in excluded or normalized(candidate["text"]) in selected_texts:
            continue
        if remaining <= 0 or marks > remaining:
            continue
        target = blueprint.topic_marks.get(topic)
        if target is not None and (topics[topic] >= target or topics[topic] + marks > target):
            continue
        # A complete topic allocation is a closed blueprint; partial allocation leaves room for other topics.
        if target is None and isclose(sum(blueprint.topic_marks.values()), blueprint.total_marks, abs_tol=0.01):
            continue
        bloom_target = bloom_coverage.get(level, {}).get("target", 0)
        bloom_gap = max(0, bloom_target - blooms[level]) / max(bloom_target, 1)
        topic_gap = max(0, target - topics[topic]) / max(target, 1) if target is not None else 0
        if blueprint.purpose == "final":
            score = 0.45 * topic_gap + 0.35 * bloom_gap + 0.10 * candidate["lecture_coverage"] + 0.10 * candidate["exam_relevance"]
        else:
            score = 0.5 * candidate["recommendation_score"] + 0.25 * topic_gap + 0.25 * bloom_gap
        candidate.update(recommendation_score=round(score, 4), priority=priority_from_score(score))
        candidate["requires_marks"] = marks <= 0
        candidate["max_available_marks"] = min(remaining, target - topics[topic]) if target is not None else remaining
        candidate["blueprint_reason"] = (f"{topic}: {topics[topic]:g}/{target:g} marks. " if target is not None else "Unallocated topic marks. ") + f"{level}: {blooms[level]:g}/{bloom_target:g} marks."
        candidates.append(candidate)
    candidates.sort(key=lambda c: c["recommendation_score"], reverse=True)
    return {"topics": sorted({r["canonical_topic"] for r in bank}),
            "recommendations": candidates[:30],
            "review": {"total_marks": total, "remaining_marks": remaining,
                       "topic_coverage": topic_coverage, "bloom_coverage": bloom_coverage,
                       "estimated_minutes": estimated_minutes, "estimated_parts": estimated_parts,
                       "part_count": len(parts), "issues": issues},
            "analytics_available": bool(analytics),
            "ranked_weak_topics": recommendation.weakness_for_document(analytics)["ranked_weak_topics"]}


async def generate_for_paper(request: GenerateRequest, bank: list[dict]) -> dict:
    blueprint = request.paper.blueprint
    sources = [{"source_id": r["question_id"], "kind": "lecture_objective", "text": r["text"][:3000]}
               for r in bank if r.get("source_type") == "lecture" and r.get("canonical_topic") == request.topic][:8]
    if blueprint.lecture_notes.strip():
        sources.insert(0, {"source_id": "lecturer-notes", "kind": "lecture_notes", "text": blueprint.lecture_notes})
    if not sources:
        raise ValueError("Add lecture notes or select a topic with course lecture sources before generating.")
    current_parts = [p for q in request.paper.questions for p in q.get("parts", [])]
    remaining = blueprint.total_marks - sum(p.get("max_marks", 0) for p in current_parts)
    if request.marks > remaining:
        raise ValueError("Question marks exceed the remaining paper marks.")
    topic_marks = sum(p.get("max_marks", 0) for q in request.paper.questions if q.get("topic") == request.topic for p in q.get("parts", []))
    if request.topic in blueprint.topic_marks and topic_marks + request.marks > blueprint.topic_marks[request.topic]:
        raise ValueError("Question marks exceed the remaining topic allocation.")
    if request.topic not in blueprint.topic_marks and isclose(sum(blueprint.topic_marks.values()), blueprint.total_marks, abs_tol=0.01):
        raise ValueError("Topic is outside the fully allocated blueprint.")
    historical = [{"question_id": r["question_id"], "question_text": r["text"]}
                  for r in bank if r.get("canonical_topic") == request.topic and r.get("source_type") != "lecture"]
    historical.extend({"question_id": p.get("question_id", "draft"), "question_text": p.get("question", "")} for p in current_parts)
    result = await llm_service.generate_candidates({
        "course_code": request.course_code, "topic": request.topic, "bloom_level": request.bloom_level,
        "mark_range": [request.marks, request.marks], "sources": sources,
        "learning_outcomes": blueprint.learning_outcomes,
        "historical_questions": [{**h, "question_text": h["question_text"][:1500]} for h in historical[:20]],
    }, count=request.count)
    if result["status"] != "ok":
        return {"status": "degraded", "reason": result.get("reason", "generation_failed"),
                "detail": result.get("detail"), "candidates": []}
    allowed = {s["source_id"]: s for s in sources}
    candidates = []
    for raw in result["candidates"]:
        try:
            c = GroundedCandidate.model_validate(raw)
        except ValueError:
            continue
        if c.topic != request.topic or c.bloom_level != request.bloom_level or not isclose(c.marks, request.marks, abs_tol=0.01) or any(s not in allowed for s in c.source_ids):
            continue
        comparison_texts = [h["question_text"] for h in historical] + [p["text"] for p in candidates]
        lexical_duplicate = any(SequenceMatcher(None, normalized(c.text), normalized(text)).ratio() >= 0.9 for text in comparison_texts)
        if lexical_duplicate:
            continue
        candidates.append({**c.model_dump(), "question_id": f"generated_{uuid4().hex[:12]}",
                           "sources": [allowed[s] for s in c.source_ids], "review_status": "needs_review"})
    checks = result.get("similarity_checks", [])
    if len(candidates) != request.count:
        return {"status": "degraded", "reason": "Generated output did not meet the topic, marks, source or originality requirements. Try again.", "candidates": []}
    return {"status": "ok", "candidates": candidates, "similarity_checks": checks,
            "similarity_available": len(checks) == request.count,
            "model": llm_service.settings.llm_model}
