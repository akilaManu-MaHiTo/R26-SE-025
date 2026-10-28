"""Lecturer status rows from the same verified component grades as reconstruction."""

from app.analytics.student_document import performance_status
from app.services.exam_paper import reconstruct_exam_paper


def build_lecturer_grading_rows(exam_key, sources):
    paper = reconstruct_exam_paper(exam_key, sources)
    if paper["validation"]["examDefinitionStatus"] != "valid":
        raise ValueError("Exam identity is missing or ambiguous; grading status cannot be established")
    records = {name: {str(r.get("_id")): r for r in sources.get(name, [])}
               for name in ("submissions", "diagram_evaluations")}
    rows = []
    for student in paper["students"]:
        own = [r for r in sources.get("submissions", []) if r.get("student_id") == student["studentId"]
               and r.get("archived_at") is None and r.get("archived_reason") != "superseded_by_new_batch"]
        if len(own) == 1 and any(i["code"] == "duplicate_question" for i in paper["issues"]):
            # Different students may still use different versions of the same exam rubric.
            rubrics = [r for r in sources.get("rubrics", []) if str(r.get("_id")) == str(own[0].get("rubric_ref"))]
            if len(rubrics) == 1:
                individual = reconstruct_exam_paper(exam_key, {**sources, "rubrics": rubrics})
                student = next((s for s in individual["students"] if s["studentId"] == student["studentId"]), student)
        grade, components = student["grading"], {}
        submitted_at = None
        for kind, collection in (("essay", "submissions"), ("diagram", "diagram_evaluations")):
            component = grade["components"].get(kind)
            if component is None:
                components[kind] = {"status": "not_required", "obtained": None, "maximum": None}
                continue
            refs = component["sourceRefs"]
            own = [records[collection][ref["id"]] for ref in refs if ref["id"] in records[collection]]
            amount = component["awardedMarks"]
            if len(own) > 1:
                status = "needs_review"
            elif not own:
                status = "missing_submission"
            elif amount is not None:
                status = "graded"
            elif kind == "essay" and own[0].get("status") in ("processing", "not_started", "failed"):
                status = own[0]["status"]
            else:
                status = "needs_review"
            components[kind] = {"status": status, "obtained": amount, "maximum": component["maximumMarks"]}
            if kind == "essay" and len(own) == 1:
                submitted_at = own[0].get("processed_at")
        review_reasons = []
        if grade["status"] == "needs_review":
            messages = {"criterion_mismatch": "Criterion labels do not match the marking rubric.",
                        "invalid_criterion_marks": "Some criterion marks need review.",
                        "duplicate_submission": "Multiple essay attempts need to be resolved.",
                        "duplicate_evaluation": "Multiple evaluations need to be resolved.",
                        "evaluation_total_mismatch": "The saved total does not match the question marks."}
            review_reasons = list(dict.fromkeys(messages[i["code"]] for i in student["issues"] if i["code"] in messages))
            if not review_reasons:
                review_reasons = ["Grading evidence needs review before the overall result is final."]
        rows.append({"student_id": student["studentId"], "components": components,
            "grading_status": grade["status"], "review_reasons": review_reasons,
            "score": {"obtained": grade["awardedMarks"], "maximum": grade["maximumMarks"], "percentage": grade["percentage"]},
            "status": performance_status(grade["percentage"]) if grade["status"] == "complete" else
                      "Review needed" if grade["status"] == "needs_review" else "Pending",
            "analysis_status": "diagram_only" if components["diagram"]["status"] == "graded" else "pending",
            "submitted_at": submitted_at})
    return rows
