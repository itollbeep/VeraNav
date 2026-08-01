"""Tests for continuous-time ESKF error-state linearization."""

from __future__ import annotations

import unittest

import numpy as np

from veranav.imu import ImuSample
from veranav.linearization import continuous_error_dynamics
from veranav.math import (
    quat_exp,
    quat_inverse,
    quat_log,
    quat_multiply,
    quat_to_rotation_matrix,
    skew,
)
from veranav.state import NominalState


class ContinuousErrorDynamicsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = NominalState(
            timestamp=2.0,
            position_n=[1.0, 2.0, 3.0],
            velocity_n=[-1.0, 0.5, 4.0],
            quaternion_nb=quat_exp([0.2, -0.1, 0.3]),
            accel_bias_b=[0.01, -0.02, 0.03],
            gyro_bias_b=[0.001, -0.002, 0.003],
        )
        self.sample = ImuSample(
            timestamp=2.0,
            specific_force_b=[0.4, -0.5, -9.1],
            angular_rate_b=[0.1, 0.2, -0.3],
        )

    def test_shapes_and_finite_values(self) -> None:
        system, noise_mapping = continuous_error_dynamics(
            self.state,
            self.sample,
        )
        self.assertEqual(system.shape, (15, 15))
        self.assertEqual(noise_mapping.shape, (15, 12))
        self.assertTrue(np.all(np.isfinite(system)))
        self.assertTrue(np.all(np.isfinite(noise_mapping)))

    def test_expected_system_blocks(self) -> None:
        system, _ = continuous_error_dynamics(self.state, self.sample)
        rotation = quat_to_rotation_matrix(self.state.quaternion_nb)
        force = self.sample.specific_force_b - self.state.accel_bias_b
        rate = self.sample.angular_rate_b - self.state.gyro_bias_b

        np.testing.assert_array_equal(system[0:3, 3:6], np.eye(3))
        np.testing.assert_allclose(
            system[3:6, 6:9],
            -rotation @ skew(force),
            rtol=0.0,
            atol=1.0e-15,
        )
        np.testing.assert_allclose(
            system[3:6, 9:12],
            -rotation,
            rtol=0.0,
            atol=1.0e-15,
        )
        np.testing.assert_allclose(
            system[6:9, 6:9],
            -skew(rate),
            rtol=0.0,
            atol=1.0e-15,
        )
        np.testing.assert_array_equal(system[6:9, 12:15], -np.eye(3))

    def test_expected_noise_mapping_blocks(self) -> None:
        _, noise_mapping = continuous_error_dynamics(self.state, self.sample)
        rotation = quat_to_rotation_matrix(self.state.quaternion_nb)
        expected = np.zeros((15, 12))
        expected[3:6, 0:3] = -rotation
        expected[6:9, 3:6] = -np.eye(3)
        expected[9:12, 6:9] = np.eye(3)
        expected[12:15, 9:12] = np.eye(3)
        np.testing.assert_allclose(
            noise_mapping,
            expected,
            rtol=0.0,
            atol=1.0e-15,
        )

    def test_unassigned_system_blocks_are_zero(self) -> None:
        system, _ = continuous_error_dynamics(self.state, self.sample)
        expected = np.zeros((15, 15))
        rotation = quat_to_rotation_matrix(self.state.quaternion_nb)
        force = self.sample.specific_force_b - self.state.accel_bias_b
        rate = self.sample.angular_rate_b - self.state.gyro_bias_b
        expected[0:3, 3:6] = np.eye(3)
        expected[3:6, 6:9] = -rotation @ skew(force)
        expected[3:6, 9:12] = -rotation
        expected[6:9, 6:9] = -skew(rate)
        expected[6:9, 12:15] = -np.eye(3)
        np.testing.assert_allclose(system, expected, rtol=0.0, atol=1.0e-15)

    def test_velocity_attitude_jacobian_by_finite_difference(self) -> None:
        system, _ = continuous_error_dynamics(self.state, self.sample)
        rotation = quat_to_rotation_matrix(self.state.quaternion_nb)
        force = self.sample.specific_force_b - self.state.accel_bias_b
        epsilon = 1.0e-7

        for axis in range(3):
            perturbation = np.zeros(3)
            perturbation[axis] = epsilon
            plus_rotation = rotation @ quat_to_rotation_matrix(
                quat_exp(perturbation)
            )
            minus_rotation = rotation @ quat_to_rotation_matrix(
                quat_exp(-perturbation)
            )
            derivative = (
                plus_rotation @ force - minus_rotation @ force
            ) / (2.0 * epsilon)
            np.testing.assert_allclose(
                derivative,
                system[3:6, 6 + axis],
                rtol=0.0,
                atol=2.0e-8,
            )

    def test_velocity_accel_bias_jacobian_by_finite_difference(self) -> None:
        system, _ = continuous_error_dynamics(self.state, self.sample)
        rotation = quat_to_rotation_matrix(self.state.quaternion_nb)
        epsilon = 1.0e-7

        for axis in range(3):
            perturbation = np.zeros(3)
            perturbation[axis] = epsilon
            plus_force = (
                self.sample.specific_force_b
                - (self.state.accel_bias_b + perturbation)
            )
            minus_force = (
                self.sample.specific_force_b
                - (self.state.accel_bias_b - perturbation)
            )
            derivative = (
                rotation @ plus_force - rotation @ minus_force
            ) / (2.0 * epsilon)
            np.testing.assert_allclose(
                derivative,
                system[3:6, 9 + axis],
                rtol=0.0,
                atol=2.0e-8,
            )

    def test_attitude_and_gyro_bias_dynamics_by_small_step(self) -> None:
        system, _ = continuous_error_dynamics(self.state, self.sample)
        corrected_rate = self.sample.angular_rate_b - self.state.gyro_bias_b
        delta_theta = np.array([2.0e-6, -3.0e-6, 1.0e-6])
        delta_bias = np.array([-1.0e-6, 2.0e-6, 3.0e-6])
        dt = 1.0e-5

        nominal_next = quat_multiply(
            self.state.quaternion_nb,
            quat_exp(corrected_rate * dt),
        )
        true_initial = quat_multiply(
            self.state.quaternion_nb,
            quat_exp(delta_theta),
        )
        true_next = quat_multiply(
            true_initial,
            quat_exp((corrected_rate - delta_bias) * dt),
        )
        next_error = quat_log(
            quat_multiply(quat_inverse(nominal_next), true_next)
        )
        numerical_derivative = (next_error - delta_theta) / dt
        expected_derivative = (
            system[6:9, 6:9] @ delta_theta
            + system[6:9, 12:15] @ delta_bias
        )
        np.testing.assert_allclose(
            numerical_derivative,
            expected_derivative,
            rtol=0.0,
            atol=3.0e-10,
        )

    def test_rejects_invalid_types_and_timestamp(self) -> None:
        with self.assertRaises(TypeError):
            continuous_error_dynamics(object(), self.sample)
        with self.assertRaises(TypeError):
            continuous_error_dynamics(self.state, object())
        mismatched = ImuSample(
            timestamp=3.0,
            specific_force_b=np.zeros(3),
            angular_rate_b=np.zeros(3),
        )
        with self.assertRaises(ValueError):
            continuous_error_dynamics(self.state, mismatched)


if __name__ == "__main__":
    unittest.main()
