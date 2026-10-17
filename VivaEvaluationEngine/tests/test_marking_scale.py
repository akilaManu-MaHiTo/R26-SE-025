"""The marking scale is configuration: changing it must change every mark, grade and limit."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from services import assessment_scoring
from services.assessment_scoring import MODE_WITH, MODE_WITHOUT, build_assessment, fuse_final_score
from services.marking_scale import (
    DEFAULT_GRADE_BANDS_PERCENT,
    ENV_MARK_DECIMALS,
    ENV_MARK_MAX,
    ENV_TECHNICAL_MAX,
    MarkingScale,
)
from tests.test_assessment_scoring import _sample_result


class DefaultScaleTests(unittest.TestCase):
    def test_default_is_out_of_20(self):
        scale = MarkingScale()
        self.assertEqual(scale.mark_max, 20.0)
        self.assertEqual(scale.technical_max, 20.0)
        self.assertEqual(scale.decimals, 2)

    def test_default_bands_scale_to_20(self):
        self.assertEqual(
            MarkingScale().grade_bands(),
            (("A+", 18.0), ("A", 16.0), ("B+", 14.0), ("B", 12.0), ("C+", 10.0), ("C", 8.0), ("F", 0.0)),
        )


class OtherScaleTests(unittest.TestCase):
    """A viva out of 25, 30 or 100 needs only a different MarkingScale."""

    def test_percent_to_mark_follows_the_scale(self):
        for mark_max, expected in ((20, 15.0), (25, 18.75), (30, 22.5), (100, 75.0)):
            scale = MarkingScale(mark_max=mark_max, technical_max=mark_max)
            self.assertEqual(scale.percent_to_mark(75), expected, mark_max)

    def test_bands_are_the_same_percentages_on_any_scale(self):
        scale = MarkingScale(mark_max=30, technical_max=30)
        self.assertEqual(scale.grade_bands()[0], ("A+", 27.0))  # 90% of 30
        self.assertEqual(scale.grade_bands()[3], ("B", 18.0))  # 60% of 30
        # The same percentage always lands on the same letter, whatever the scale.
        for percent in (0, 39.9, 40, 59.9, 60, 69.9, 70, 79.9, 80, 89.9, 90, 100):
            letters = {
                MarkingScale(mark_max=m, technical_max=m).resolve_grade(
                    MarkingScale(mark_max=m, technical_max=m).percent_to_mark(percent)
                )
                for m in (20, 25, 30, 100)
            }
            self.assertEqual(len(letters), 1, f"percent {percent} graded differently: {letters}")

    def test_grade_follows_the_rounded_mark_on_any_scale(self):
        scale = MarkingScale(mark_max=25, technical_max=25)
        mark = scale.percent_to_mark(69.998)  # 17.4995 -> 17.50, which is exactly the B+ minimum
        self.assertEqual(mark, 17.5)
        self.assertEqual(scale.resolve_grade(mark), "B+")

    def test_technical_score_has_its_own_maximum(self):
        scale = MarkingScale(mark_max=20, technical_max=10)
        self.assertEqual(scale.technical_to_percent(5), 50.0)
        self.assertEqual(scale.technical_to_percent(99), 100.0)  # clamped
        self.assertEqual(scale.clamp_technical(12), 10.0)

    def test_decimals_are_configurable(self):
        scale = MarkingScale(mark_max=20, decimals=0)
        self.assertEqual(scale.percent_to_mark(69.44), 14.0)
        self.assertEqual(MarkingScale(mark_max=20, decimals=1).percent_to_mark(69.44), 13.9)


class ValidationTests(unittest.TestCase):
    def test_rejects_a_non_positive_scale(self):
        for bad in (0, -5):
            with self.assertRaises(ValueError):
                MarkingScale(mark_max=bad)
            with self.assertRaises(ValueError):
                MarkingScale(technical_max=bad)

    def test_rejects_bad_decimals(self):
        for bad in (-1, 5):
            with self.assertRaises(ValueError):
                MarkingScale(decimals=bad)

    def test_rejects_malformed_bands(self):
        with self.assertRaises(ValueError):
            MarkingScale(grade_bands_percent=())
        with self.assertRaises(ValueError):  # ascending
            MarkingScale(grade_bands_percent=(("F", 0.0), ("A", 80.0)))
        with self.assertRaises(ValueError):  # no band at 0
            MarkingScale(grade_bands_percent=(("A", 80.0), ("B", 50.0)))
        with self.assertRaises(ValueError):  # over 100%
            MarkingScale(grade_bands_percent=(("A", 120.0), ("F", 0.0)))


class EnvironmentTests(unittest.TestCase):
    def test_reads_the_scale_from_the_environment(self):
        scale = MarkingScale.from_env({ENV_MARK_MAX: "30", ENV_MARK_DECIMALS: "1"})
        self.assertEqual(scale.mark_max, 30.0)
        self.assertEqual(scale.technical_max, 30.0)  # follows the mark scale by default
        self.assertEqual(scale.decimals, 1)

    def test_technical_max_can_differ(self):
        scale = MarkingScale.from_env({ENV_MARK_MAX: "100", ENV_TECHNICAL_MAX: "40"})
        self.assertEqual((scale.mark_max, scale.technical_max), (100.0, 40.0))

    def test_empty_environment_gives_the_default(self):
        self.assertEqual(MarkingScale.from_env({}), MarkingScale())

    def test_a_bad_value_is_an_error_not_a_silent_default(self):
        with self.assertRaises(ValueError):
            MarkingScale.from_env({ENV_MARK_MAX: "twenty"})
        with self.assertRaises(ValueError):
            MarkingScale.from_env({ENV_MARK_MAX: "0"})

    def test_shared_with_the_client_as_a_dict(self):
        shared = MarkingScale(mark_max=30, technical_max=30).as_dict()
        self.assertEqual(shared["mark_max"], 30.0)
        self.assertEqual(shared["grade_bands"][0], {"grade": "A+", "min_percent": 90.0, "min_mark": 27.0})
        self.assertEqual(len(shared["grade_bands"]), len(DEFAULT_GRADE_BANDS_PERCENT))


class AssessmentUnderAnotherScaleTests(unittest.TestCase):
    """The scorer must follow whatever scale is configured, with no 20 left in it."""

    def _under(self, mark_max, technical_max=None):
        return patch.object(
            assessment_scoring,
            "MARKING_SCALE",
            MarkingScale(mark_max=mark_max, technical_max=technical_max or mark_max),
        )

    def test_without_technical_mark_scales(self):
        base = build_assessment(_sample_result(), mode=MODE_WITHOUT)
        percent = base["final_score"]
        for mark_max in (25, 30, 100):
            with self._under(mark_max):
                scaled = build_assessment(_sample_result(), mode=MODE_WITHOUT)
            self.assertEqual(scaled["final_score"], percent)  # the percentage never changes
            self.assertEqual(scaled["final_mark"], round(percent / 100 * mark_max, 2))
            self.assertEqual(scaled["final_mark_max"], float(mark_max))
            self.assertEqual(scaled["grade"], base["grade"])  # same percentage, same letter

    def test_technical_fusion_uses_the_technical_maximum(self):
        with self._under(30, technical_max=10):
            fused = fuse_final_score(mode=MODE_WITH, ai_performance=60.0, technical_accuracy=8.0)
        self.assertEqual(fused["technical_accuracy_100"], 80.0)
        self.assertEqual(fused["final_score"], 70.0)  # 0.5*60 + 0.5*80
        self.assertEqual(fused["final_mark"], 21.0)  # 70% of 30

    def test_technical_input_is_clamped_to_its_maximum(self):
        with self._under(25):
            fused = fuse_final_score(mode=MODE_WITH, ai_performance=60.0, technical_accuracy=99.0)
        self.assertEqual(fused["technical_accuracy"], 25.0)

    def test_the_assessment_records_the_scale_it_used(self):
        with self._under(30, technical_max=15):
            assessment = build_assessment(_sample_result(), mode=MODE_WITHOUT)
        self.assertEqual(assessment["final_mark_max"], 30.0)
        self.assertEqual(assessment["technical_max"], 15.0)


if __name__ == "__main__":
    unittest.main()
