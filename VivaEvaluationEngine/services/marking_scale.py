"""How a viva is marked: the mark scale, the technical-score scale and the letter grades.

This is the ONE place that knows the marking scale. Everything else (the scorer, the server
and, through the server, the web client) asks a `MarkingScale` instead of hard-coding "20".
Moving a viva to another scale, for example out of 25, 30 or 100, is a configuration change:

    VIVA_MARK_MAX=30          official mark is out of 30
    VIVA_TECHNICAL_MAX=30     the examiner's technical score is out of 30 (defaults to the mark scale)
    VIVA_MARK_DECIMALS=2      the official mark is rounded to this many decimals

The scoring pipeline itself works on a 0-100 percentage; the official mark is that percentage
scaled to `mark_max` and rounded. Letter grades are defined once, as minimum percentages of the
full mark, so they follow any scale automatically (90% is 18/20, 22.5/25, 27/30 or 90/100).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

PERCENT_MAX = 100.0

DEFAULT_MARK_MAX = 20.0
DEFAULT_MARK_DECIMALS = 2

# Letter grade -> minimum percentage of the full mark, highest band first, last band 0.
DEFAULT_GRADE_BANDS_PERCENT: Tuple[Tuple[str, float], ...] = (
    ("A+", 90.0),
    ("A", 80.0),
    ("B+", 70.0),
    ("B", 60.0),
    ("C+", 50.0),
    ("C", 40.0),
    ("F", 0.0),
)

ENV_MARK_MAX = "VIVA_MARK_MAX"
ENV_TECHNICAL_MAX = "VIVA_TECHNICAL_MAX"
ENV_MARK_DECIMALS = "VIVA_MARK_DECIMALS"

GradeBandsPercent = Tuple[Tuple[str, float], ...]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class MarkingScale:
    """An immutable description of the marking scale, with the conversions that depend on it."""

    mark_max: float = DEFAULT_MARK_MAX
    technical_max: float = DEFAULT_MARK_MAX
    decimals: int = DEFAULT_MARK_DECIMALS
    grade_bands_percent: GradeBandsPercent = DEFAULT_GRADE_BANDS_PERCENT

    def __post_init__(self) -> None:
        if not self.mark_max > 0:
            raise ValueError(f"mark_max must be greater than 0, got {self.mark_max}")
        if not self.technical_max > 0:
            raise ValueError(f"technical_max must be greater than 0, got {self.technical_max}")
        if not 0 <= self.decimals <= 4:
            raise ValueError(f"decimals must be between 0 and 4, got {self.decimals}")
        self._validate_bands(self.grade_bands_percent)

    @staticmethod
    def _validate_bands(bands: GradeBandsPercent) -> None:
        if not bands:
            raise ValueError("grade bands must not be empty")
        minimums = [minimum for _, minimum in bands]
        if minimums != sorted(minimums, reverse=True):
            raise ValueError("grade bands must be listed from the highest minimum to the lowest")
        if minimums[-1] != 0:
            raise ValueError("the lowest grade band must start at 0 so every mark gets a grade")
        if not all(0 <= minimum <= PERCENT_MAX for minimum in minimums):
            raise ValueError("grade band minimums must be percentages between 0 and 100")

    # ---- conversions -------------------------------------------------------------------------
    def percent_to_mark(self, percent: Optional[float]) -> Optional[float]:
        """Scale a 0-100 percentage to the official mark, rounded to `decimals`."""
        if percent is None:
            return None
        clamped = _clamp(float(percent), 0.0, PERCENT_MAX)
        return round(clamped / PERCENT_MAX * self.mark_max, self.decimals)

    def technical_to_percent(self, technical: float) -> float:
        """The examiner's technical score (out of `technical_max`) as a 0-100 percentage."""
        return _clamp(float(technical) / self.technical_max, 0.0, 1.0) * PERCENT_MAX

    def clamp_technical(self, technical: float) -> float:
        """Keep a technical score inside 0..technical_max, rounded to `decimals`."""
        return round(_clamp(float(technical), 0.0, self.technical_max), self.decimals)

    # ---- grades ------------------------------------------------------------------------------
    def grade_bands(self) -> Tuple[Tuple[str, float], ...]:
        """(grade, minimum mark) with each band scaled to this mark scale and rounded like a mark."""
        return tuple(
            (grade, round(minimum / PERCENT_MAX * self.mark_max, self.decimals))
            for grade, minimum in self.grade_bands_percent
        )

    def resolve_grade(self, mark: Optional[float]) -> Optional[str]:
        """Grade for an official mark. Pass the ROUNDED mark so the grade matches what is shown."""
        if mark is None:
            return None
        value = _clamp(float(mark), 0.0, self.mark_max)
        for grade, minimum in self.grade_bands():
            if value >= minimum:
                return grade
        return self.grade_bands_percent[-1][0]

    def resolve_grade_from_percent(self, percent: Optional[float]) -> Optional[str]:
        """Grade for a raw 0-100 percentage, with no rounding to a mark first."""
        if percent is None:
            return None
        value = _clamp(float(percent), 0.0, PERCENT_MAX)
        for grade, minimum in self.grade_bands_percent:
            if value >= minimum:
                return grade
        return self.grade_bands_percent[-1][0]

    # ---- sharing -----------------------------------------------------------------------------
    def as_dict(self) -> Dict[str, Any]:
        """The scale as sent to the web client, so it never hard-codes the numbers."""
        return {
            "mark_max": self.mark_max,
            "technical_max": self.technical_max,
            "decimals": self.decimals,
            "grade_bands": [
                {"grade": grade, "min_percent": minimum_percent, "min_mark": minimum_mark}
                for (grade, minimum_percent), (_, minimum_mark) in zip(
                    self.grade_bands_percent, self.grade_bands()
                )
            ],
        }

    # ---- configuration -----------------------------------------------------------------------
    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "MarkingScale":
        """Read the scale from the environment. A bad value is an error, never a silent default:
        marking on the wrong scale is worse than refusing to start."""
        source = os.environ if env is None else env
        mark_max = _read_number(source, ENV_MARK_MAX, DEFAULT_MARK_MAX)
        technical_max = _read_number(source, ENV_TECHNICAL_MAX, mark_max)
        decimals = int(_read_number(source, ENV_MARK_DECIMALS, DEFAULT_MARK_DECIMALS))
        return cls(mark_max=mark_max, technical_max=technical_max, decimals=decimals)


def _read_number(source: Mapping[str, str], name: str, default: float) -> float:
    raw = (source.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}") from None


MARKING_SCALE = MarkingScale.from_env()
