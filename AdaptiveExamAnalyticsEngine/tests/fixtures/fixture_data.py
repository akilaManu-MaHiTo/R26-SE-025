"""Deterministic fixtures for analytics tests.

Two papers (exam-2023, exam-2024), each with three question parts. Twelve
students. Values are hand-computed so test expectations are exact.
"""

COURSE = "SE2032"

SQL_Q = {"topic": "SQL", "bloom": "Apply", "type": "problem_solving"}
SCHEMA_Q = {"topic": "Schema Refinement", "bloom": "Analyze", "type": "problem_solving"}
LOGICAL_Q = {"topic": "Logical Database Design", "bloom": "Understand", "type": "short_answer"}

QUESTIONS = {
    "exam-2023": [
        {"question_number": "01", "part": "a", "max_marks": 2.0, "text": "Write a SQL SELECT.", **SQL_Q},
        {"question_number": "01", "part": "b", "max_marks": 3.0, "text": "Find the primary key.", **SCHEMA_Q},
        {"question_number": "02", "part": "a", "max_marks": 1.0, "text": "Explain an ER entity.", **LOGICAL_Q},
    ],
    "exam-2024": [
        {"question_number": "01", "part": "a", "max_marks": 2.0, "text": "Write a SQL UPDATE.", **SQL_Q},
        {"question_number": "01", "part": "b", "max_marks": 3.0, "text": "Normalize to 3NF.", **SCHEMA_Q},
        {"question_number": "02", "part": "a", "max_marks": 1.0, "text": "Define a foreign key.", **LOGICAL_Q},
    ],
}

sample_papers = []
for year in [2023, 2024]:
    for exam_id in QUESTIONS:
        if (exam_id == "exam-2023" and year == 2023) or (exam_id == "exam-2024" and year == 2024):
            sample_papers.append(
                {
                    "exam_id": exam_id,
                    "course_code": COURSE,
                    "year": year,
                    "title": f"DBMS {year}",
                    "questions": [
                        {
                            "question_number": q["question_number"],
                            "parts": [
                                {"part": q["part"], "text": q["text"], "max_marks": q["max_marks"]}
                            ],
                        }
                        for q in QUESTIONS[exam_id]
                    ],
                }
            )

STUDENT_KEYS = [f"stu-{i:03d}" for i in range(1, 13)]

_marks = {
    "exam-2023": {
        "01a": [2.0, 2.0, 1.5, 1.0, 2.0, 0.5, 2.0, 1.0, 2.0, 2.0, 1.0, 0.0],
        "01b": [3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 2.0, 0.0, 3.0, 2.0, 1.0, 1.5],
        "02a": [1.0, 1.0, 0.5, 1.0, 0.0, 0.5, 1.0, 1.0, 0.5, 1.0, 0.5, 0.0],
    },
    "exam-2024": {
        "01a": [2.0, 1.5, 2.0, 1.0, 0.5, 2.0, 1.0, 2.0, 2.0, 1.5, 0.5, 1.0],
        "01b": [2.0, 3.0, 1.5, 2.0, 0.0, 1.0, 2.0, 1.5, 3.0, 1.0, 2.0, 1.5],
        "02a": [1.0, 0.5, 1.0, 1.0, 0.5, 1.0, 0.0, 1.0, 1.0, 0.5, 0.5, 1.0],
    },
}

sample_submissions = []
for exam_id, exam_questions in QUESTIONS.items():
    for q in exam_questions:
        key = f"{q['question_number']}{q['part']}"
        for i, student_key in enumerate(STUDENT_KEYS):
            awarded = _marks[exam_id][key][i]
            sample_submissions.append(
                {
                    "exam_id": exam_id,
                    "course_code": COURSE,
                    "student_key": student_key,
                    "question_number": q["question_number"],
                    "part": q["part"],
                    "awarded_marks": awarded,
                    "max_marks": q["max_marks"],
                    "answer_text": f"answer for {key} by {student_key}",
                    "feedback": "ok",
                    "criteria_breakdown": [],
                }
            )


def course_settings(course_code: str = COURSE) -> dict:
    return {
        "course_code": course_code,
        "course_name": "Database Management Systems",
        "settings": {
            "pass_threshold": 0.5,
            "min_students": 10,
            "min_attempts": 2,
            "topic_importance": {},
            "blueprint_targets": {},
        },
    }


def _normalize(awarded: float, max_marks: float) -> float:
    return awarded / max_marks


expected_attempt_records = []
for exam_id, exam_questions in QUESTIONS.items():
    for q in exam_questions:
        key = f"{q['question_number']}{q['part']}"
        for i, student_key in enumerate(STUDENT_KEYS):
            awarded = _marks[exam_id][key][i]
            expected_attempt_records.append(
                {
                    "attempt_id": f"{exam_id}-{key}-{student_key}",
                    "analysis_run_id": "run-fixture",
                    "course_code": COURSE,
                    "exam_id": exam_id,
                    "student_key": student_key,
                    "question_id": f"{exam_id}-{key}",
                    "question_number": q["question_number"],
                    "part": q["part"],
                    "question_text": q["text"],
                    "topic_assignments": [{"topic": q["topic"], "weight": 1.0}],
                    "bloom_level": q["bloom"],
                    "question_type": q["type"],
                    "key_concepts": [],
                    "awarded_marks": awarded,
                    "max_marks": q["max_marks"],
                    "normalized_score": _normalize(awarded, q["max_marks"]),
                    "criteria_breakdown": [],
                    "answer_text": f"answer for {key} by {student_key}",
                    "feedback": "ok",
                    "classification_status": "lecturer_validated",
                    "classification_confidence": "high",
                    "algorithm_version": "analytics-v1",
                }
            )