"""Tests for seed-paired baseline and degradation comparison."""

import unittest
from dataclasses import replace

import numpy as np

from veranav.comparison import compare_experiment_configs
from veranav.degradation import GnssDegradation
from veranav.experiment import ExperimentConfig
from veranav.monte_carlo import FailureCriteria
from veranav.simulation import CircularTrajectoryConfig


def short_config() -> ExperimentConfig:
    return ExperimentConfig(
        trajectory=CircularTrajectoryConfig(
            duration_s=1.0,
            imu_dt=0.02,
            gnss_dt=0.2,
        )
    )


class PairedComparisonTest(unittest.TestCase):
    def test_identical_configs_have_zero_differences(self) -> None:
        config = short_config()
        result = compare_experiment_configs(
            config,
            config,
            [0, 1, 2],
            bootstrap_resamples=100,
            bootstrap_seed=9,
        )
        np.testing.assert_array_equal(result.rmse_differences_m, np.zeros(3))
        np.testing.assert_array_equal(
            result.maximum_error_differences_m,
            np.zeros(3),
        )
        self.assertEqual(result.rmse_difference_interval_m.lower, 0.0)
        self.assertEqual(result.rmse_difference_interval_m.upper, 0.0)
        self.assertEqual(result.degraded_only_failure_count, 0)
        self.assertEqual(result.recovered_failure_count, 0)

    def test_degradation_changes_paired_result(self) -> None:
        baseline = short_config()
        degraded = replace(
            baseline,
            degradation=GnssDegradation(
                bias_start_s=0.2,
                bias_duration_s=1.0,
                bias_n=[20.0, 0.0, 0.0],
            ),
        )
        result = compare_experiment_configs(
            baseline,
            degraded,
            [3, 4, 5],
            FailureCriteria(max_position_rmse_m=1.0, max_position_error_m=2.0),
            bootstrap_resamples=100,
            bootstrap_seed=10,
        )
        self.assertTrue(np.any(result.rmse_differences_m != 0.0))
        self.assertGreaterEqual(result.degraded_failure_rate, result.baseline_failure_rate)
        self.assertGreaterEqual(result.rmse_worsening_probability, 0.0)
        self.assertLessEqual(result.rmse_worsening_probability, 1.0)

    def test_result_arrays_are_readonly(self) -> None:
        config = short_config()
        result = compare_experiment_configs(
            config,
            config,
            [1, 2],
            bootstrap_resamples=20,
        )
        for array in (
            result.rmse_differences_m,
            result.maximum_error_differences_m,
            result.baseline_failures,
            result.degraded_failures,
        ):
            self.assertFalse(array.flags.writeable)

    def test_fixed_inputs_are_repeatable(self) -> None:
        config = short_config()
        first = compare_experiment_configs(
            config,
            config,
            [1, 2],
            bootstrap_resamples=50,
            bootstrap_seed=12,
        )
        second = compare_experiment_configs(
            config,
            config,
            [1, 2],
            bootstrap_resamples=50,
            bootstrap_seed=12,
        )
        np.testing.assert_array_equal(
            first.rmse_differences_m,
            second.rmse_differences_m,
        )
        self.assertEqual(
            first.rmse_difference_interval_m.lower,
            second.rmse_difference_interval_m.lower,
        )

    def test_rejects_invalid_inputs(self) -> None:
        config = short_config()
        with self.assertRaises(TypeError):
            compare_experiment_configs(object(), config, [0])
        with self.assertRaises(ValueError):
            compare_experiment_configs(config, config, [])
        with self.assertRaises(ValueError):
            compare_experiment_configs(config, config, [0, 0])


if __name__ == "__main__":
    unittest.main()
