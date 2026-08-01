"""Tests for deterministic Monte Carlo aggregation."""

from __future__ import annotations

import unittest

from veranav.experiment import ExperimentConfig
from veranav.monte_carlo import FailureCriteria, run_monte_carlo
from veranav.simulation import CircularTrajectoryConfig


def config() -> ExperimentConfig:
    return ExperimentConfig(
        trajectory=CircularTrajectoryConfig(
            duration_s=0.6,
            imu_dt=0.05,
            gnss_dt=0.2,
            accel_noise_std=0.005,
            gyro_noise_std=0.0002,
            gnss_position_std_m=0.2,
        )
    )


class MonteCarloTest(unittest.TestCase):
    def test_summary_is_deterministic(self) -> None:
        first = run_monte_carlo(config(), [1, 2, 3])
        second = run_monte_carlo(config(), [1, 2, 3])
        self.assertEqual(first.position_rmse_mean_m, second.position_rmse_mean_m)
        self.assertEqual(first.divergence_rate, second.divergence_rate)

    def test_lenient_criteria_accept_all_short_baselines(self) -> None:
        summary = run_monte_carlo(
            config(),
            [1, 2],
            FailureCriteria(100.0, 100.0),
        )
        self.assertEqual(summary.divergence_rate, 0.0)

    def test_strict_criteria_can_reject_runs(self) -> None:
        summary = run_monte_carlo(
            config(),
            [1, 2],
            FailureCriteria(1.0e-12, 1.0e-12),
        )
        self.assertEqual(summary.divergence_rate, 1.0)

    def test_rejects_invalid_seeds(self) -> None:
        with self.assertRaises(ValueError):
            run_monte_carlo(config(), [])
        with self.assertRaises(ValueError):
            run_monte_carlo(config(), [1, 1])


if __name__ == "__main__":
    unittest.main()
