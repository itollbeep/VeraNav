"""Tests for deterministic study SVG rendering."""

from __future__ import annotations

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.render_study_svg import (
    render_paired_rmse_svg,
    render_reliability_boundary_svg,
    write_study_svgs,
)


def _payload() -> dict:
    return {
        "schema_version": 1,
        "paired_comparison": {
            "rmse_difference_interval_m": {
                "estimate": 0.1,
                "lower": 0.02,
                "upper": 0.18,
            },
            "runs": [
                {"seed": 0, "rmse_difference_m": 0.05},
                {"seed": 1, "rmse_difference_m": 0.15},
                {"seed": 2, "rmse_difference_m": -0.02},
            ],
        },
        "adaptive_boundary": {
            "max_bias_m": 12.0,
            "points": [
                {
                    "outage_duration_s": 0.0,
                    "status": "bounded",
                    "lower_reliable_bias_m": 9.5,
                    "upper_unreliable_bias_m": 10.0,
                },
                {
                    "outage_duration_s": 1.0,
                    "status": "all_reliable",
                    "lower_reliable_bias_m": 12.0,
                    "upper_unreliable_bias_m": None,
                },
                {
                    "outage_duration_s": 2.0,
                    "status": "none_reliable",
                    "lower_reliable_bias_m": None,
                    "upper_unreliable_bias_m": 0.0,
                },
            ],
        },
    }


class StudySvgTest(unittest.TestCase):
    def test_boundary_svg_is_valid_and_deterministic(self) -> None:
        first = render_reliability_boundary_svg(_payload())
        second = render_reliability_boundary_svg(_payload())
        self.assertEqual(first, second)
        root = ET.fromstring(first)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertIn("bounded transition", first)
        self.assertIn("all reliable in range", first)

    def test_paired_svg_is_valid_and_contains_interval(self) -> None:
        svg = render_paired_rmse_svg(_payload())
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertIn("95% CI [0.020, 0.180]", svg)
        self.assertIn("positive values indicate worse RMSE", svg)

    def test_writer_creates_two_repeatable_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            study = root / "study.json"
            study.write_text(
                json.dumps(_payload(), sort_keys=True),
                encoding="utf-8",
            )
            output = root / "figures"
            first = write_study_svgs(study, output)
            first_bytes = tuple(path.read_bytes() for path in first)
            second = write_study_svgs(study, output)
            second_bytes = tuple(path.read_bytes() for path in second)
            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(
                tuple(path.name for path in first),
                ("reliability_boundary.svg", "paired_rmse_differences.svg"),
            )

    def test_rejects_invalid_schema_and_boundary_status(self) -> None:
        invalid_schema = _payload()
        invalid_schema["schema_version"] = 2
        with tempfile.TemporaryDirectory() as temporary:
            study = Path(temporary) / "study.json"
            study.write_text(json.dumps(invalid_schema), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schema_version"):
                write_study_svgs(study, Path(temporary) / "figures")

        invalid_status = _payload()
        invalid_status["adaptive_boundary"]["points"][0]["status"] = "unknown"
        with self.assertRaisesRegex(ValueError, "boundary status"):
            render_reliability_boundary_svg(invalid_status)

    def test_rejects_missing_runs(self) -> None:
        payload = _payload()
        payload["paired_comparison"]["runs"] = []
        with self.assertRaisesRegex(ValueError, "nonempty"):
            render_paired_rmse_svg(payload)


if __name__ == "__main__":
    unittest.main()
