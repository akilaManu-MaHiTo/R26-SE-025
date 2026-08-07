import statistics

from app.analytics.evidence import evidence_status, grade_of
from app.analytics.mastery import compute_mastery, topic_weight_for
from app.analytics.recommender import weakness_component
from app.analytics.taxonomy import BLOOM_LEVELS, TOPICS
from app.schemas.student import (
    QuestionPerformance,
    StudentBloomSkill,
    StudentExamPerformance,
    StudentStudyAction,
    StudentTopicSkill,
)


def _dominant_topic(attempt: dict) -> str:
    assignments = attempt.get("topic_assignments", [])
    if not assignments:
        return ""
    return max(assignments, key=lambda a: a["weight"])["topic"]


def question_performance(attempt: dict, pass_threshold: float) -> QuestionPerformance:
    missed = [
        {
            "criterion": c["criterion"],
            "awarded_marks": c["awarded_marks"],
            "max_marks": c["max_marks"],
        }
        for c in attempt.get("criteria_breakdown", [])
        if not c.get("met")
    ]
    return QuestionPerformance(
        question_id=attempt["question_id"],
        question_number=attempt["question_number"],
        part=attempt["part"],
        question_text=attempt["question_text"],
        topic=_dominant_topic(attempt),
        bloom_level=attempt["bloom_level"],
        question_type=attempt["question_type"],
        awarded_marks=attempt["awarded_marks"],
        max_marks=attempt["max_marks"],
        normalized_score=attempt["normalized_score"],
        passed=attempt["normalized_score"] >= pass_threshold,
        feedback=attempt.get("feedback", ""),
        missed_criteria=missed,
    )


def student_exam_performances(
    attempts: list[dict], pass_threshold: float
) -> list[StudentExamPerformance]:
    by_exam: dict[str, list[dict]] = {}
    for a in attempts:
        by_exam.setdefault(a["exam_id"], []).append(a)
    exams = []
    for exam_id in sorted(by_exam):
        exam_attempts = by_exam[exam_id]
        total_awarded = sum(a["awarded_marks"] for a in exam_attempts)
        total_max = sum(a["max_marks"] for a in exam_attempts)
        fraction = (total_awarded / total_max) if total_max else 0.0
        exams.append(
            StudentExamPerformance(
                exam_id=exam_id,
                total_awarded=total_awarded,
                total_max=total_max,
                percentage=round(fraction * 100.0, 4),
                grade=grade_of(fraction),
                attempt_count=len(exam_attempts),
                question_performances=[
                    question_performance(a, pass_threshold) for a in exam_attempts
                ],
            )
        )
    return exams


def _weighted_mastery(attempts: list[dict]) -> float | None:
    if not attempts:
        return None
    den = sum(a["max_marks"] for a in attempts)
    if den <= 0:
        return None
    num = sum(a["normalized_score"] * a["max_marks"] for a in attempts)
    return round(num / den, 6)


def bloom_skill_profile(attempts: list[dict], pass_threshold: float) -> list[StudentBloomSkill]:
    profile = []
    for bloom in BLOOM_LEVELS:
        subset = [a for a in attempts if a["bloom_level"] == bloom]
        scores = [a["normalized_score"] for a in subset]
        profile.append(
            StudentBloomSkill(
                bloom_level=bloom,
                mastery=_weighted_mastery(subset),
                mean=statistics.fmean(scores) if scores else None,
                attempt_count=len(subset),
                evidence_status=evidence_status(
                    statistics.fmean(scores) if scores else None,
                    1,
                    len(subset),
                    pass_threshold,
                    1,
                    1,
                ),
            )
        )
    return profile


def topic_skill_profile(
    attempts: list[dict],
    pass_threshold: float,
    topic_importance: dict[str, float] | None = None,
) -> list[StudentTopicSkill]:
    profile = []
    for topic in TOPICS:
        subset = [a for a in attempts if topic_weight_for(a, topic) > 0]
        scores = [a["normalized_score"] for a in subset]
        missed = [c for a in subset for c in a.get("criteria_breakdown", [])]
        missed_rate = (
            sum(1 for c in missed if not c["met"]) / len(missed) if missed else None
        )
        failure_rate = (
            sum(1 for s in scores if s < 0.5) / len(scores) if scores else None
        )
        mastery = compute_mastery(attempts, topic)
        profile.append(
            StudentTopicSkill(
                topic=topic,
                mastery=mastery,
                mean=statistics.fmean(scores) if scores else None,
                attempt_count=len(subset),
                evidence_status=evidence_status(
                    statistics.fmean(scores) if scores else None,
                    1,
                    len(subset),
                    pass_threshold,
                    1,
                    1,
                ),
                rank=0,
                priority_score=weakness_component(mastery, failure_rate, missed_rate),
            )
        )
    profile.sort(key=lambda s: (-s.priority_score, s.topic))
    for i, skill in enumerate(profile, start=1):
        skill.rank = i
    return profile


def rank_weakest_topics(topic_skills: list[StudentTopicSkill]) -> list[str]:
    return [s.topic for s in sorted(topic_skills, key=lambda s: (-s.priority_score, s.topic))]


def deterministic_study_actions(weakest_topics: list[str]) -> list[StudentStudyAction]:
    templates = [
        "Review core concepts",
        "Practice exam-style questions",
        "Revisit missed criteria",
    ]
    actions = []
    for i, topic in enumerate(weakest_topics[:3]):
        actions.append(
            StudentStudyAction(
                action=templates[i],
                topic=topic,
                rationale=f"{topic} is one of your weakest topics and should be prioritized in your exam preparation.",
                practice_topics=weakest_topics[:3],
                source="deterministic",
            )
        )
    return actions


def _student_masteries(all_attempts: list[dict]) -> dict[str, list[dict]]:
    by_student: dict[str, list[dict]] = {}
    for a in all_attempts:
        by_student.setdefault(a["student_key"], []).append(a)
    return by_student


def _percentile(student_value: float, others: list[float | None]) -> float | None:
    present = [v for v in others if v is not None]
    if not present:
        return None
    return sum(1 for v in present if v < student_value) / len(present)


def cohort_comparison(student_attempts: list[dict], all_attempts: list[dict]) -> dict:
    by_student = _student_masteries(all_attempts)

    topics: dict[str, dict] = {}
    for topic in TOPICS:
        student_mastery = compute_mastery(student_attempts, topic)
        if student_mastery is None:
            continue
        cohort_mastery = compute_mastery(all_attempts, topic)
        others = [
            compute_mastery(att, topic) for att in by_student.values()
        ]
        topics[topic] = {
            "student_mastery": student_mastery,
            "cohort_mastery": cohort_mastery,
            "delta": round(student_mastery - cohort_mastery, 6)
            if cohort_mastery is not None
            else None,
            "percentile": _percentile(student_mastery, others),
        }

    blooms: dict[str, dict] = {}
    for bloom in BLOOM_LEVELS:
        student_mastery = _weighted_mastery(
            [a for a in student_attempts if a["bloom_level"] == bloom]
        )
        if student_mastery is None:
            continue
        cohort_mastery = _weighted_mastery(
            [a for a in all_attempts if a["bloom_level"] == bloom]
        )
        others = [
            _weighted_mastery([a for a in att if a["bloom_level"] == bloom])
            for att in by_student.values()
        ]
        blooms[bloom] = {
            "student_mastery": student_mastery,
            "cohort_mastery": cohort_mastery,
            "delta": round(student_mastery - cohort_mastery, 6)
            if cohort_mastery is not None
            else None,
            "percentile": _percentile(student_mastery, others),
        }

    return {"topics": topics, "blooms": blooms}