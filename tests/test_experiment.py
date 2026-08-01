"""Tests for end-to-end synthetic ESKF experiments."""

from __future__ import annotations

import unittest

import numpy as np

from veranav.degradation import GnssDegradation
from veranav.experiment import ExperimentConfig, run_synthetic_experiment
from veranav.simulation import CircularTrajectoryConfig


def short_trajectory() -> CircularTrajectoryConfig:
    return CircularTrajectoryConfig(
        duration_s=1.0,
        imu_dt=0.05,
        gnss_dt=0.2,
        accel_noise_std=0.005,
        gyro_noise_std=0.0002,
        gnss_position_std_m=0.2,
    )


class ExperimentTest(unittest.TestCase):
    def test_baseline_run_shapes_and_counts(self) -> None:
        config = ExperimentConfig(trajectory=short_trajectory())
        result = run_synthetic_experiment(config, 10)
        self.assertEqual(len(result.estimates), 21)
        self.assertEqual(len(result.truth_states), 21)
        self.assertEqual(len(result.nees_values), 20)
        self.assertEqual(result.metrics.update_count, 5)
        self.assertEqual(result.final_covariance.shape, (15, 15))

    def test_fixed_seed_is_bitwise_repeatable(self) -> None:
        config = ExperimentConfig(trajectory=short_trajectory())
        first = run_synthetic_experiment(config, 12)
        second = run_synthetic_experiment(config, 12)
        self.assertEqual(first.metrics, second.metrics)
        np.testing.assert_array_equal(first.final_covariance, second.final_covariance)
        for a, b in zip(first.estimates, second.estimates, strict=True):
            np.testing.assert_array_equal(a.position_n, b.position_n)

    def test_full_outage_has_no_updates(self) -> None:
        trajectory = short_trajectory()
        config = ExperimentConfig(
            trajectory=trajectory,
            degradation=GnssDegradation(outage_start_s=0.0, outage_duration_s=2.0),
        )
        result = run_synthetic_experiment(config, 4)
        self.assertEqual(result.metrics.update_count, 0)
        self.assertIsNone(result.metrics.nis_mean)

    def test_large_bias_changes_result(self) -> None:
        trajectory = short_trajectory()
        clean = run_synthetic_experiment(ExperimentConfig(trajectory=trajectory), 2)
        degraded = run_synthetic_experiment(
            ExperimentConfig(
                trajectory=trajectory,
                degradation=GnssDegradation(
                    bias_start_s=0.2,
                    bias_duration_s=2.0,
                    bias_n=[10.0, 0.0, 0.0],
                ),
            ),
            2,
        )
        self.assertGreater(degraded.metrics.position_rmse_m, clean.metrics.position_rmse_m)

    def test_rejects_invalid_seed(self) -> None:
        with self.assertRaises(ValueError):
            run_synthetic_experiment(ExperimentConfig(trajectory=short_trajectory()), -1)


if __name__ == "__main__":
    unittest.main()
