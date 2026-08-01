"""Tests for adaptive reliability-boundary search."""

import unittest
from unittest.mock import patch

from veranav.boundary import (
    ReliabilityRequirement,
    search_reliability_boundary,
)
from veranav.experiment import ExperimentConfig
from veranav.metrics import RunMetrics
from veranav.monte_carlo import FailureCriteria, MonteCarloSummary
from veranav.simulation import CircularTrajectoryConfig


def summary(rate: float, count: int = 10) -> MonteCarloSummary:
    failures = int(round(rate * count))
    metrics = []
    for index in range(count):
        failed = index < failures
        metrics.append(
            RunMetrics(
                position_rmse_m=10.0 if failed else 1.0,
                position_max_m=20.0 if failed else 2.0,
                nis_mean=1.0,
                nis_coverage_95=1.0,
                nees_mean=1.0,
                nees_coverage_95=1.0,
                update_count=1,
                sample_count=1,
            )
        )
    return MonteCarloSummary(
        seeds=tuple(range(count)),
        run_metrics=tuple(metrics),
        position_rmse_mean_m=1.0,
        position_rmse_p95_m=1.0,
        position_max_p95_m=2.0,
        divergence_rate=rate,
    )


def config() -> ExperimentConfig:
    return ExperimentConfig(
        trajectory=CircularTrajectoryConfig(
            duration_s=2.0,
            imu_dt=0.02,
            gnss_dt=0.2,
        )
    )


class ReliabilityRequirementTest(unittest.TestCase):
    def test_observed_rate_classification(self) -> None:
        requirement = ReliabilityRequirement(max_divergence_rate=0.2)
        accepted, interval = requirement.classify(summary(0.1))
        self.assertTrue(accepted)
        self.assertAlmostEqual(interval.estimate, 0.1)

    def test_upper_bound_can_be_stricter(self) -> None:
        requirement = ReliabilityRequirement(
            max_divergence_rate=0.2,
            use_upper_confidence_bound=True,
        )
        accepted, interval = requirement.classify(summary(0.0))
        self.assertFalse(accepted)
        self.assertGreater(interval.upper, 0.2)

    def test_rejects_invalid_requirement(self) -> None:
        with self.assertRaises(ValueError):
            ReliabilityRequirement(max_divergence_rate=-0.1)
        with self.assertRaises(TypeError):
            ReliabilityRequirement(use_upper_confidence_bound=1)


class BoundarySearchTest(unittest.TestCase):
    def test_bounded_transition_is_bisected(self) -> None:
        def fake_run(current_config, seeds, criteria):
            bias = float(current_config.degradation.bias_n[0])
            return summary(0.0 if bias <= 6.0 else 1.0, len(tuple(seeds)))

        with patch("veranav.boundary.run_monte_carlo", side_effect=fake_run):
            result = search_reliability_boundary(
                config(),
                [0.0, 1.0],
                range(10),
                fault_start_s=0.5,
                max_bias_m=10.0,
                tolerance_m=0.25,
                max_iterations=10,
            )
        self.assertEqual(len(result.points), 2)
        for point in result.points:
            self.assertEqual(point.status, "bounded")
            self.assertLessEqual(point.bracket_width_m, 0.25)
            self.assertLessEqual(point.lower_reliable_bias_m, 6.0)
            self.assertGreater(point.upper_unreliable_bias_m, 6.0)
        self.assertEqual(result.midpoint_boundary_m()[0], result.midpoint_boundary_m()[1])

    def test_all_reliable_and_none_reliable_statuses(self) -> None:
        with patch("veranav.boundary.run_monte_carlo", return_value=summary(0.0)):
            all_reliable = search_reliability_boundary(
                config(),
                [0.0],
                range(10),
                fault_start_s=0.5,
                max_bias_m=5.0,
            )
        self.assertEqual(all_reliable.points[0].status, "all_reliable")
        self.assertEqual(all_reliable.points[0].lower_reliable_bias_m, 5.0)

        with patch("veranav.boundary.run_monte_carlo", return_value=summary(1.0)):
            none_reliable = search_reliability_boundary(
                config(),
                [0.0],
                range(10),
                fault_start_s=0.5,
                max_bias_m=5.0,
            )
        self.assertEqual(none_reliable.points[0].status, "none_reliable")
        self.assertEqual(none_reliable.points[0].upper_unreliable_bias_m, 0.0)

    def test_evaluation_cache_avoids_duplicate_runs(self) -> None:
        calls = []

        def fake_run(current_config, seeds, criteria):
            bias = float(current_config.degradation.bias_n[0])
            calls.append(bias)
            return summary(0.0 if bias < 2.0 else 1.0, len(tuple(seeds)))

        with patch("veranav.boundary.run_monte_carlo", side_effect=fake_run):
            search_reliability_boundary(
                config(),
                [0.0],
                range(10),
                fault_start_s=0.5,
                max_bias_m=4.0,
                tolerance_m=0.25,
            )
        self.assertEqual(len(calls), len(set(calls)))

    def test_rejects_invalid_search_inputs(self) -> None:
        with self.assertRaises(ValueError):
            search_reliability_boundary(
                config(),
                [],
                [0],
                fault_start_s=0.5,
                max_bias_m=5.0,
            )
        with self.assertRaises(ValueError):
            search_reliability_boundary(
                config(),
                [0.0],
                [0],
                fault_start_s=0.5,
                max_bias_m=5.0,
                tolerance_m=5.0,
            )


if __name__ == "__main__":
    unittest.main()
