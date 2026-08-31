"""Compute class-level diagram analysis from diagram_evaluation + diagram_marking.

Merges into the exam analytics document so lecturers see diagram performance
alongside text-based question performance in a single view.
"""

import statistics as _stats


def compute_diagram_analysis(
    diagram_evaluations: list[dict],
    diagram_markings: list[dict],
) -> dict | None:
    """Return a diagram_analysis dict, or None if no diagram data exists.

    Produces:
      - statistics: class-wide scores, pass rate, distribution
      - criterion_performance: per-criterion pass/fail/missed rates
      - student_summaries: per-student diagram score + criteria breakdown
      - detection_summary: avg entity/relationship/label counts from marking data
    """
    if not diagram_evaluations:
        return None

    # ── Per-student scores ────────────────────────────────────────────────
    scores: list[float] = []
    max_scores: list[float] = []
    per_student: list[dict] = []
    # criterion_id -> {criterion, total_marks, awarded, pass_count, partial_count, fail_count, student_count}
    criterion_agg: dict[int, dict] = {}

    for ev in diagram_evaluations:
        student_id = ev.get("student_id", "unknown")
        result = ev.get("evaluation_result") or {}
        total = float(result.get("total_score", 0))
        maximum = float(result.get("max_score", 20))
        percentage = (total / maximum * 100.0) if maximum > 0 else 0.0
        scores.append(total)
        max_scores.append(maximum)

        criteria_results = result.get("criteria_results", [])
        criteria_detail: list[dict] = []
        for cr in criteria_results:
            cid = cr.get("criterion_id", 0)
            status = cr.get("status", "unknown")
            awarded = float(cr.get("awarded_marks", 0))
            max_marks = float(0)
            # Try to find max_marks from matching criterion in rubric
            # For now, infer from awarded if status is 'pass' and it equals the max
            # We'll compute max_marks from the rubric guideLines separately

            if cid not in criterion_agg:
                criterion_agg[cid] = {
                    "criterion_id": cid,
                    "criterion": cr.get("criterion", f"Criterion {cid}"),
                    "pass_count": 0,
                    "partial_count": 0,
                    "fail_count": 0,
                    "total_awarded": 0.0,
                    "student_count": 0,
                }
            agg = criterion_agg[cid]
            agg["student_count"] += 1
            agg["total_awarded"] += awarded
            if status == "pass":
                agg["pass_count"] += 1
            elif status == "partial":
                agg["partial_count"] += 1
            elif status == "fail":
                agg["fail_count"] += 1

            criteria_detail.append({
                "criterion_id": cid,
                "criterion": cr.get("criterion", f"Criterion {cid}"),
                "awarded_marks": awarded,
                "status": status,
                "remarks": cr.get("remarks", ""),
            })

        per_student.append({
            "student_id": student_id,
            "score": total,
            "max_score": maximum,
            "percentage": round(percentage, 2),
            "status": _performance_status(percentage),
            "criteria": criteria_detail,
            "feedback": result.get("overall_feedback", ""),
        })

    # ── Class statistics ──────────────────────────────────────────────────
    avg_score = sum(scores) / len(scores) if scores else 0.0
    avg_max = sum(max_scores) / len(max_scores) if max_scores else 20.0
    avg_percentage = (avg_score / avg_max * 100.0) if avg_max > 0 else 0.0
    pass_rate = (sum(1 for s in scores if s / avg_max * 100 >= 50) / len(scores) * 100.0) if scores else 0.0
    try:
        med_pct = _stats.median([(s / m * 100) if m > 0 else 0 for s, m in zip(scores, max_scores)])
        std_pct = round(_stats.pstdev([(s / m * 100) if m > 0 else 0 for s, m in zip(scores, max_scores)]), 2) if len(scores) > 1 else 0.0
    except Exception:
        med_pct = avg_percentage
        std_pct = 0.0

    statistics = {
        "total_students": len(scores),
        "average_score": round(avg_score, 2),
        "max_score": round(avg_max, 2),
        "average_percentage": round(avg_percentage, 2),
        "pass_rate": round(pass_rate, 2),
        "highest_score": round(max(scores), 2) if scores else 0.0,
        "lowest_score": round(min(scores), 2) if scores else 0.0,
        "median_percentage": float(med_pct),
        "std_percentage": float(std_pct),
    }

    # ── Criterion performance ─────────────────────────────────────────────
    # Sort by criterion_id
    criterion_performance = []
    for cid in sorted(criterion_agg.keys()):
        agg = criterion_agg[cid]
        n = agg["student_count"]
        # Find max_marks for this criterion from the evaluation data
        # (look for a student who got full marks to infer max)
        max_marks_for_criterion = 0.0
        for ev in diagram_evaluations:
            for cr in (ev.get("evaluation_result") or {}).get("criteria_results", []):
                if cr.get("criterion_id") == cid:
                    # If any student passed with this criterion, the awarded_marks is likely the max
                    # We need the rubric to get the actual max. For now, use the max awarded as proxy.
                    awarded = float(cr.get("awarded_marks", 0))
                    if awarded > max_marks_for_criterion:
                        max_marks_for_criterion = awarded
                    # If status is pass and awarded > 0, this is likely the full marks
                    if cr.get("status") == "pass" and awarded > 0:
                        max_marks_for_criterion = max(max_marks_for_criterion, awarded)

        avg_awarded = agg["total_awarded"] / n if n > 0 else 0.0
        avg_pct = (avg_awarded / max_marks_for_criterion * 100.0) if max_marks_for_criterion > 0 else 0.0
        fail_rate = agg["fail_count"] / n if n > 0 else 0.0
        criterion_performance.append({
            "criterion_id": cid,
            "criterion": agg["criterion"],
            "max_marks": max_marks_for_criterion,
            "average_awarded_marks": round(avg_awarded, 2),
            "average_percentage": round(avg_pct, 2),
            "pass_count": agg["pass_count"],
            "partial_count": agg["partial_count"],
            "fail_count": agg["fail_count"],
            "student_count": n,
            "fail_rate": round(fail_rate, 4),
        })

    # ── Detection summary from diagram_marking ────────────────────────────
    detection_summary = None
    if diagram_markings:
        entity_counts = [m.get("diagram_details", {}).get("entity_count", 0) for m in diagram_markings]
        rel_counts = [m.get("diagram_details", {}).get("relationship_count", 0) for m in diagram_markings]
        label_counts = [m.get("diagram_details", {}).get("label_count", 0) for m in diagram_markings]
        marking_scores = [float(m.get("diagram_marks", 0)) for m in diagram_markings]

        detection_summary = {
            "avg_entity_count": round(sum(entity_counts) / len(entity_counts), 1) if entity_counts else 0,
            "avg_relationship_count": round(sum(rel_counts) / len(rel_counts), 1) if rel_counts else 0,
            "avg_label_count": round(sum(label_counts) / len(label_counts), 1) if label_counts else 0,
            "total_detections": sum(len(m.get("diagram_details", {}).get("detections", [])) for m in diagram_markings),
            "avg_marking_score": round(sum(marking_scores) / len(marking_scores), 2) if marking_scores else 0,
        }

    # ── Weakest criteria (most failed) ───────────────────────────────────
    weakest_criteria = [
        {
            "criterion_id": c["criterion_id"],
            "criterion": c["criterion"],
            "fail_rate": c["fail_rate"],
            "fail_count": c["fail_count"],
            "student_count": c["student_count"],
        }
        for c in sorted(criterion_performance, key=lambda x: x["fail_rate"], reverse=True)
        if c["fail_rate"] > 0
    ][:5]

    # ── Insights ──────────────────────────────────────────────────────────
    insights: list[str] = []
    if scores:
        insights.append(
            f"Class average diagram score: {avg_percentage:.1f}% ({len(scores)} students, "
            f"pass rate {pass_rate:.0f}%)."
        )
    if weakest_criteria:
        wc = weakest_criteria[0]
        insights.append(
            f"Weakest criterion: \"{wc['criterion']}\" — {wc['fail_count']}/{wc['student_count']} "
            f"students failed ({wc['fail_rate']*100:.0f}% fail rate)."
        )
    if len(weakest_criteria) > 1:
        names = [f'"{c["criterion"]}"' for c in weakest_criteria[1:3]]
        insights.append(
            f"Other common failures: {', '.join(names)}."
        )
    if detection_summary:
        insights.append(
            f"Avg detected elements: {detection_summary['avg_entity_count']} entities, "
            f"{detection_summary['avg_relationship_count']} relationships, "
            f"{detection_summary['avg_label_count']} labels."
        )

    return {
        "statistics": statistics,
        "criterion_performance": criterion_performance,
        "student_summaries": sorted(per_student, key=lambda x: x["percentage"]),
        "detection_summary": detection_summary,
        "weakest_criteria": weakest_criteria,
        "insights": insights,
    }


def _performance_status(percentage: float) -> str:
    if percentage >= 80:
        return "Strong"
    if percentage >= 65:
        return "Developing"
    if percentage >= 50:
        return "Needs Improvement"
    return "Critical"
