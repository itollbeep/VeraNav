"""Tests for synthetic trajectory and sensor generation."""

from __future__ import annotations

import math
import unittest

import numpy as np

from veranav.imu import STANDARD_GRAVITY_MPS2
from veranav.math import quat_equivalent
from veranav.simulation import (
    CircularTrajectoryConfig,
    circular_truth_state,
    generate_circular_dataset,
)


class CircularTrajectoryTest(unittest.TestCase):
    def test_analytic_initial_state(self) -> None:
        config = CircularTrajectoryConfig(duration_s=2.0, imu_dt=0.1, gnss_dt=0.5)
        state = circular_truth_state(config, 0.0)
        np.testing.assert_allclose(state.position_n, np.zeros(3), atol=0.0)
        np.testing.assert_allclose(state.velocity_n, [6.0, 0.0, 0.0], atol=0.0)
        self.assertTrue(quat_equivalent(state.quaternion_nb, [1.0, 0.0, 0.0, 0.0]))

    def test_quarter_turn_geometry(self) -> None:
        config = CircularTrajectoryConfig(
            duration_s=math.pi / 2.0,
            imu_dt=math.pi / 20.0,
            gnss_dt=math.pi / 10.0,
            radius_m=1.0,
            speed_mps=1.0,
        )
        state = circular_truth_state(config, math.pi / 2.0)
        np.testing.assert_allclose(state.position_n, [1.0, 1.0, 0.0], atol=1.0e-14)
        np.testing.assert_allclose(state.velocity_n, [0.0, 1.0, 0.0], atol=1.0e-14)

    def test_dataset_lengths_and_alignment(self) -> None:
        config = CircularTrajectoryConfig(duration_s=2.0, imu_dt=0.1, gnss_dt=0.5)
        dataset = generate_circular_dataset(config, 7)
        self.assertEqual(len(dataset.truth_states), 21)
        self.assertEqual(len(dataset.imu_samples), 20)
        self.assertEqual(dataset.gnss_step_indices, (5, 10, 15, 20))
        self.assertEqual(len(dataset.gnss_measurements), 4)

    def test_zero_noise_imu_matches_analytic_measurement(self) -> None:
        config = CircularTrajectoryConfig(
            duration_s=1.0,
            imu_dt=0.1,
            gnss_dt=0.5,
            accel_noise_std=0.0,
            gyro_noise_std=0.0,
        )
        dataset = generate_circular_dataset(config, 1)
        sample = dataset.imu_samples[0]
        omega = config.speed_mps / config.radius_m
        np.testing.assert_allclose(
            sample.specific_force_b,
            [0.0, config.speed_mps * omega, -STANDARD_GRAVITY_MPS2],
            atol=0.0,
        )
        np.testing.assert_allclose(sample.angular_rate_b, [0.0, 0.0, omega], atol=0.0)

    def test_fixed_seed_is_repeatable(self) -> None:
        config = CircularTrajectoryConfig(duration_s=1.0, imu_dt=0.1, gnss_dt=0.5)
        first = generate_circular_dataset(config, 123)
        second = generate_circular_dataset(config, 123)
        for a, b in zip(first.imu_samples, second.imu_samples, strict=True):
            np.testing.assert_array_equal(a.specific_force_b, b.specific_force_b)
            np.testing.assert_array_equal(a.angular_rate_b, b.angular_rate_b)
        for a, b in zip(first.gnss_measurements, second.gnss_measurements, strict=True):
            np.testing.assert_array_equal(a.position_n, b.position_n)

    def test_different_seed_changes_noisy_measurements(self) -> None:
        config = CircularTrajectoryConfig(duration_s=1.0, imu_dt=0.1, gnss_dt=0.5)
        first = generate_circular_dataset(config, 1)
        second = generate_circular_dataset(config, 2)
        self.assertFalse(np.array_equal(first.imu_samples[0].specific_force_b, second.imu_samples[0].specific_force_b))

    def test_biases_are_present_in_imu_measurements(self) -> None:
        config = CircularTrajectoryConfig(
            duration_s=1.0,
            imu_dt=0.1,
            gnss_dt=0.5,
            accel_noise_std=0.0,
            gyro_noise_std=0.0,
            accel_bias_b=[0.1, 0.2, 0.3],
            gyro_bias_b=[0.01, 0.02, 0.03],
        )
        sample = generate_circular_dataset(config, 0).imu_samples[0]
        omega = config.angular_rate_rad_s
        np.testing.assert_allclose(
            sample.specific_force_b,
            [0.1, config.speed_mps * omega + 0.2, -STANDARD_GRAVITY_MPS2 + 0.3],
            atol=1.0e-15,
        )
        np.testing.assert_allclose(sample.angular_rate_b, [0.01, 0.02, omega + 0.03], atol=1.0e-15)

    def test_rejects_invalid_config_and_seed(self) -> None:
        with self.assertRaises(ValueError):
            CircularTrajectoryConfig(duration_s=1.05, imu_dt=0.1, gnss_dt=0.5)
        with self.assertRaises(ValueError):
            CircularTrajectoryConfig(duration_s=1.0, imu_dt=0.1, gnss_dt=0.25)
        with self.assertRaises(ValueError):
            generate_circular_dataset(CircularTrajectoryConfig(), -1)


if __name__ == "__main__":
    unittest.main()
