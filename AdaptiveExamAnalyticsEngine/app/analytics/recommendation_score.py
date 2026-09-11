"""Phase 4: Recommendation scoring - pure deterministic formula.

Recommendation Score =
    0.35 * Student Weakness
  + 0.20 * Lecture Coverage
  + 0.15 * Tutorial Evidence
  + 0.15 * Exam Relevance
  + 0.15 * Bloom Gap

All components 0..1. Weakness from Phase 3, others from question_bank.
Weights tunable experimentally - defaults below.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreWeights:
    weakness: float = 0.35
    lecture_coverage: float = 0.20
    tutorial_evidence: float = 0.15
    exam_relevance: float = 0.15
    bloom_gap: float = 0.15

    def as_dict(self) -> dict[str, float]:
        return {
            "weakness": self.weakness,
            "lecture_coverage": self.lecture_coverage,
            "tutorial_evidence": self.tutorial_evidence,
            "exam_relevance": self.exam_relevance,
            "bloom_gap": self.bloom_gap,
        }

    def validates(self) -> bool:
        return abs(sum(self.as_dict().values()) - 1.0) < 1e-6


DEFAULT_WEIGHTS = ScoreWeights()


def recommendation_score(
    weakness: float,
    lecture_coverage: float,
    tutorial_evidence: float,
    exam_relevance: float,
    bloom_gap: float,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
) -> float:
    """Compute 0..1 recommendation score. All inputs 0..1."""
    assert 0 <= weakness <= 1, "weakness out of range"
    assert 0 <= lecture_coverage <= 1
    assert 0 <= tutorial_evidence <= 1
    assert 0 <= exam_relevance <= 1
    assert 0 <= bloom_gap <= 1
    assert weights.validates(), "weights must sum to 1.0"
    return round(
        weights.weakness * weakness
        + weights.lecture_coverage * lecture_coverage
        + weights.tutorial_evidence * tutorial_evidence
        + weights.exam_relevance * exam_relevance
        + weights.bloom_gap * bloom_gap,
        4,
    )


def priority_from_score(score: float) -> str:
    if score >= 0.65:
        return "High"
    if score >= 0.40:
        return "Medium"
    return "Low"


def bloom_gap_for_level(
    bloom_level: str,
    current_distribution: dict[str, float],
    target_distribution: dict[str, float],
) -> float:
    """Gap 0..1 for a bloom level: how under-represented it is vs target.

    target e.g., {"Remember":0.10,"Understand":0.20,"Apply":0.40,"Analyze":0.30}
    current is actual proportion in recent exams or candidate set.
    Returns max(0, target - current) normalized to 0..1.
    """
    target = target_distribution.get(bloom_level, 0)
    current = current_distribution.get(bloom_level, 0)
    gap = max(0.0, target - current)
    # scale gap relative to target to make it 0..1
    return round(gap / target if target > 0 else 0.0, 4)
