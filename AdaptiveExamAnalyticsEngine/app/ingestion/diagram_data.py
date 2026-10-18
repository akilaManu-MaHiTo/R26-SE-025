"""Adapt saved diagram-agent grades to the existing analytics response schema."""

from copy import deepcopy
import math


def _marks(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def normalize_diagram_evaluation(record: dict, guideline: dict | None) -> dict:
    document = deepcopy(record)
    result = document.get("evaluation_result")
    if not isinstance(result, dict):
        raise ValueError("Missing diagram evaluation result")
    if "agent_grading" not in result:
        if not _marks(result.get("total_score")) or not _marks(result.get("max_score")) or not 0 <= result["total_score"] <= result["max_score"]:
            raise ValueError("Missing or invalid diagram marks")
        return document
    if guideline is None or str(guideline.get("_id")) != str(record.get("guideline_object_id")):
        raise ValueError("Missing or conflicting diagram guideline reference")
    if result.get("status") != "ok":
        raise ValueError("Diagram evaluation is not successful")
    grade = result["agent_grading"]
    if not isinstance(grade, dict):
        raise ValueError("Missing diagram agent grade")
    criteria = guideline.get("guideLines")
    if not isinstance(criteria, list) or not criteria or any(not isinstance(c, dict) or not _marks(c.get("marks")) or c["marks"] < 0 for c in criteria):
        raise ValueError("Invalid diagram rubric marks")
    if any(not isinstance(c.get("id"), int) or isinstance(c["id"], bool) for c in criteria):
        raise ValueError("Invalid diagram criterion IDs")
    maxima = {c.get("id"): c for c in criteria}
    if None in maxima or len(maxima) != len(criteria):
        raise ValueError("Missing or duplicate diagram criterion IDs")
    maximum = sum(c["marks"] for c in criteria)
    total = grade.get("agent_marks")
    if (not _marks(total) or maximum <= 0 or not 0 <= total <= maximum
            or not _marks(grade.get("max_marks")) or grade["max_marks"] != maximum
            or not _marks(guideline.get("totalMarks")) or guideline["totalMarks"] != maximum):
        raise ValueError("Missing or inconsistent diagram marks")
    for supplied in (record.get("agent_marks"), result.get("agent_marks")):
        if supplied is not None and (not _marks(supplied) or supplied != total):
            raise ValueError("Conflicting diagram totals")
    if result.get("guideline_object_id") not in (None, record.get("guideline_object_id")):
        raise ValueError("Conflicting nested guideline reference")
    rows = grade.get("criterion_results")
    if not isinstance(rows, list):
        raise ValueError("Missing diagram criterion evaluations")
    normalized, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid diagram criterion evaluation")
        cid, awarded = row.get("id"), row.get("marks")
        if not isinstance(cid, int) or isinstance(cid, bool) or cid not in maxima or cid in seen:
            raise ValueError("Unknown or duplicate diagram criterion evaluation")
        limit = maxima[cid]["marks"]
        if not _marks(awarded) or not 0 <= awarded <= limit:
            raise ValueError("Missing or invalid diagram criterion marks")
        seen.add(cid)
        normalized.append({"criterion_id": cid, "criterion": maxima[cid].get("criterion", f"Criterion {cid}"),
            "awarded_marks": awarded, "max_marks": limit,
            "status": "pass" if awarded == limit else "fail" if awarded == 0 else "partial",
            "remarks": row.get("reason", "")})
    if seen != set(maxima) or not math.isclose(sum(c["awarded_marks"] for c in normalized), total, rel_tol=0, abs_tol=0.001):
        raise ValueError("Incomplete or inconsistent diagram criterion totals")
    result.update(total_score=total, max_score=maximum, criteria_results=normalized,
                  overall_feedback=grade.get("feedback", ""))
    return document
