from app.classifier.rules import classify_by_rules
from app.schemas.catalog import QuestionAttempt, QuestionCatalog


def flatten_paper(paper: dict) -> list[dict]:
    parts = []
    for q in paper.get("questions", []):
        for p in q.get("parts", []):
            parts.append(
                {
                    "exam_id": paper["exam_id"],
                    "course_code": paper.get("course_code", ""),
                    "question_number": q["question_number"],
                    "part": p["part"],
                    "text": p["text"],
                    "max_marks": p["max_marks"],
                }
            )
    return parts


def _catalog_from_part(part: dict, algorithm_version: str) -> dict:
    question_id = f"{part['exam_id']}-{part['question_number']}{part['part']}"
    classification = classify_by_rules(part["text"])
    return {
        "question_id": question_id,
        "course_code": part["course_code"],
        "exam_id": part["exam_id"],
        "question_number": part["question_number"],
        "part": part["part"],
        "question_text": part["text"],
        "max_marks": part["max_marks"],
        "topic_assignments": [a.model_dump() for a in classification.topic_assignments],
        "bloom_level": classification.bloom_level,
        "question_type": classification.question_type,
        "key_concepts": classification.key_concepts,
        "source_paper_year": part.get("year"),
        "classification_status": "model_suggested",
        "classification_confidence": classification.confidence,
        "algorithm_version": algorithm_version,
    }


def to_question_catalog(paper: dict, algorithm_version: str = "analytics-v1") -> list[dict]:
    return [_catalog_from_part(p, algorithm_version) for p in flatten_paper(paper)]


def to_question_attempts(
    submissions: list[dict],
    catalog_lookup: dict[str, dict],
    run_id: str,
    algorithm_version: str = "analytics-v1",
) -> list[dict]:
    attempts = []
    for sub in submissions:
        key = f"{sub['exam_id']}-{sub['question_number']}{sub['part']}"
        catalog = catalog_lookup[key]
        awarded = float(sub["awarded_marks"])
        max_marks = float(catalog["max_marks"])
        attempts.append(
            {
                "attempt_id": f"{key}-{sub['student_key']}",
                "analysis_run_id": run_id,
                "course_code": catalog["course_code"],
                "exam_id": catalog["exam_id"],
                "student_key": sub["student_key"],
                "question_id": key,
                "question_number": catalog["question_number"],
                "part": catalog["part"],
                "question_text": catalog["question_text"],
                "topic_assignments": catalog["topic_assignments"],
                "bloom_level": catalog["bloom_level"],
                "question_type": catalog["question_type"],
                "key_concepts": catalog["key_concepts"],
                "awarded_marks": awarded,
                "max_marks": max_marks,
                "normalized_score": round(awarded / max_marks, 6),
                "criteria_breakdown": sub.get("criteria_breakdown", []),
                "answer_text": sub.get("answer_text", ""),
                "feedback": sub.get("feedback", ""),
                "classification_status": catalog["classification_status"],
                "classification_confidence": catalog["classification_confidence"],
                "algorithm_version": algorithm_version,
            }
        )
    return attempts


def ingest(
    courses: list[dict],
    papers: list[dict],
    submissions: list[dict],
    run_id: str,
    algorithm_version: str = "analytics-v1",
) -> tuple[list[dict], list[dict]]:
    catalog_records = []
    for paper in papers:
        catalog_records.extend(to_question_catalog(paper, algorithm_version))
    lookup = {c["question_id"]: c for c in catalog_records}
    attempt_records = to_question_attempts(submissions, lookup, run_id, algorithm_version)
    for c in catalog_records:
        QuestionCatalog(**c)
    for a in attempt_records:
        QuestionAttempt(**a)
    return catalog_records, attempt_records