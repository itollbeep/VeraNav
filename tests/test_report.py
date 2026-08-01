"""Tests for deterministic reliability-study report export."""

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from veranav.boundary import search_reliability_boundary
from veranav.comparison import compare_experiment_configs
from veranav.experiment import ExperimentConfig
from veranav.metrics import RunMetrics
from veranav.monte_carlo import MonteCarloSummary
from veranav.report import StudyReport, study_report_dict, write_study_report
from veranav.simulation import CircularTrajectoryConfig


def config() -> ExperimentConfig:
    return ExperimentConfig(
        trajectory=CircularTrajectoryConfig(
            duration_s=1.0,
            imu_dt=0.02,
            gnss_dt=0.2,
        )
    )


def summary(rate: float, count: int = 2) -> MonteCarloSummary:
    metrics = tuple(
        RunMetrics(
            position_rmse_m=1.0,
            position_max_m=2.0,
            nis_mean=1.0,
            nis_coverage_95=1.0,
            nees_mean=1.0,
            nees_coverage_95=1.0,
            update_count=1,
            sample_count=1,
        )
        for _ in range(count)
    )
    return MonteCarloSummary(
        seeds=tuple(range(count)),
        run_metrics=metrics,
        position_rmse_mean_m=1.0,
        position_rmse_p95_m=1.0,
        position_max_p95_m=2.0,
        divergence_rate=rate,
    )


def report() -> StudyReport:
    baseline = config()
    comparison = compare_experiment_configs(
        baseline,
        baseline,
        [0, 1],
        bootstrap_resamples=20,
        bootstrap_seed=1,
    )

    def fake_run(current_config, seeds, criteria):
        bias = float(current_config.degradation.bias_n[0])
        return summary(0.0 if bias <= 2.0 else 1.0, len(tuple(seeds)))

    with patch("veranav.boundary.run_monte_carlo", side_effect=fake_run):
        boundary = search_reliability_boundary(
            baseline,
            [0.0, 0.5],
            [0, 1],
            fault_start_s=0.2,
            max_bias_m=4.0,
            tolerance_m=0.5,
        )
    return StudyReport(
        title="Test reliability study",
        comparison_name="identity comparison",
        comparison=comparison,
        boundary=boundary,
    )


class StudyReportTest(unittest.TestCase):
    def test_dictionary_is_json_serializable(self) -> None:
        payload = study_report_dict(report())
        rendered = json.dumps(payload, allow_nan=False, sort_keys=True)
        self.assertIn("paired_comparison", rendered)
        self.assertIn("adaptive_boundary", rendered)
        self.assertEqual(payload["schema_version"], 1)

    def test_writes_four_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = write_study_report(report(), directory)
            self.assertEqual(
                {path.name for path in paths},
                {
                    "study.json",
                    "paired_comparison.csv",
                    "adaptive_boundary.csv",
                    "report.md",
                },
            )
            self.assertTrue(all(path.is_file() for path in paths))

    def test_json_and_csv_contents_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            json_path, comparison_path, boundary_path, _ = write_study_report(
                report(),
                directory,
            )
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["paired_comparison"]["runs"]), 2)
            self.assertEqual(len(payload["adaptive_boundary"]["points"]), 2)
            with comparison_path.open(encoding="utf-8", newline="") as stream:
                comparison_rows = list(csv.DictReader(stream))
            with boundary_path.open(encoding="utf-8", newline="") as stream:
                boundary_rows = list(csv.DictReader(stream))
            self.assertEqual(len(comparison_rows), 2)
            self.assertEqual(len(boundary_rows), 2)

    def test_repeated_write_is_byte_deterministic(self) -> None:
        value = report()
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_paths = write_study_report(value, first)
            second_paths = write_study_report(value, second)
            for left, right in zip(first_paths, second_paths, strict=True):
                self.assertEqual(left.read_bytes(), right.read_bytes())

    def test_markdown_contains_method_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            *_, markdown_path = write_study_report(report(), directory)
            text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("## Paired comparison", text)
            self.assertIn("## Adaptive reliability boundary", text)
            self.assertIn("## Reproducibility", text)

    def test_rejects_invalid_report_and_output_path(self) -> None:
        with self.assertRaises(ValueError):
            StudyReport("", "scenario", report().comparison, report().boundary)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "file.txt"
            path.write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                write_study_report(report(), path)


if __name__ == "__main__":
    unittest.main()
