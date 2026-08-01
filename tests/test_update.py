"""Tests for GNSS position updates, injection and covariance reset."""

from __future__ import annotations

import unittest

import numpy as np

from veranav.math import quat_equivalent, quat_exp, quat_multiply, skew
from veranav.measurement import GnssPositionMeasurement
from veranav.state import NominalState
from veranav.update import (
    gnss_position_update,
    inject_error,
    position_measurement_matrix,
    reset_covariance,
    reset_jacobian,
)


class ErrorInjectionTest(unittest.TestCase):
    def test_injects_all_error_blocks_with_right_attitude_perturbation(self) -> None:
        state = NominalState(
            timestamp=3.0,
            position_n=[1.0, 2.0, 3.0],
            velocity_n=[4.0, 5.0, 6.0],
            quaternion_nb=quat_exp([0.2, -0.1, 0.3]),
            accel_bias_b=[0.01, 0.02, 0.03],
            gyro_bias_b=[0.001, 0.002, 0.003],
        )
        correction = np.linspace(-0.07, 0.07, 15)
        result = inject_error(state, correction)
        np.testing.assert_allclose(result.position_n, state.position_n + correction[0:3])
        np.testing.assert_allclose(result.velocity_n, state.velocity_n + correction[3:6])
        self.assertTrue(
            quat_equivalent(
                result.quaternion_nb,
                quat_multiply(state.quaternion_nb, quat_exp(correction[6:9])),
            )
        )
        np.testing.assert_allclose(result.accel_bias_b, state.accel_bias_b + correction[9:12])
        np.testing.assert_allclose(result.gyro_bias_b, state.gyro_bias_b + correction[12:15])
        self.assertEqual(result.timestamp, state.timestamp)

    def test_injection_does_not_mutate_inputs(self) -> None:
        state = NominalState.identity()
        correction = np.arange(15, dtype=np.float64) * 1.0e-3
        snapshot = correction.copy()
        result = inject_error(state, correction)
        np.testing.assert_array_equal(correction, snapshot)
        np.testing.assert_array_equal(state.position_n, np.zeros(3))
        self.assertIsNot(result.position_n, state.position_n)

    def test_rejects_invalid_injection_inputs(self) -> None:
        with self.assertRaises(TypeError):
            inject_error(object(), np.zeros(15))
        with self.assertRaises(ValueError):
            inject_error(NominalState.identity(), np.zeros(14))
        invalid = np.zeros(15)
        invalid[3] = np.nan
        with self.assertRaises(ValueError):
            inject_error(NominalState.identity(), invalid)


class CovarianceResetTest(unittest.TestCase):
    def test_reset_jacobian_attitude_block(self) -> None:
        correction = np.array([0.1, -0.2, 0.3])
        jacobian = reset_jacobian(correction)
        expected = np.eye(15)
        expected[6:9, 6:9] = np.eye(3) - 0.5 * skew(correction)
        np.testing.assert_allclose(jacobian, expected, atol=0.0)
        self.assertFalse(jacobian.flags.writeable)

    def test_reset_covariance_matches_formula_and_is_symmetric(self) -> None:
        rng = np.random.default_rng(10)
        basis = rng.normal(size=(15, 15))
        covariance = basis @ basis.T
        correction = np.array([0.02, -0.01, 0.03])
        jacobian = reset_jacobian(correction)
        result = reset_covariance(covariance, correction)
        expected = jacobian @ covariance @ jacobian.T
        expected = 0.5 * (expected + expected.T)
        np.testing.assert_allclose(result, expected, rtol=0.0, atol=2.0e-14)
        np.testing.assert_allclose(result, result.T, rtol=0.0, atol=0.0)

    def test_rejects_invalid_reset_inputs(self) -> None:
        with self.assertRaises(ValueError):
            reset_jacobian(np.zeros(2))
        with self.assertRaises(ValueError):
            reset_covariance(np.eye(14), np.zeros(3))
        invalid = np.eye(15)
        invalid[0, 1] = 0.1
        with self.assertRaises(ValueError):
            reset_covariance(invalid, np.zeros(3))


class GnssPositionUpdateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = NominalState(
            timestamp=5.0,
            position_n=[10.0, -2.0, 3.0],
            velocity_n=[1.0, 2.0, 3.0],
            quaternion_nb=quat_exp([0.1, -0.2, 0.3]),
            accel_bias_b=[0.01, 0.02, 0.03],
            gyro_bias_b=[0.001, 0.002, 0.003],
        )
        self.prior = np.diag(np.linspace(0.5, 1.9, 15))
        self.measurement = GnssPositionMeasurement(
            timestamp=5.0,
            position_n=[11.0, -4.0, 3.5],
            covariance_n=np.diag([0.25, 0.5, 0.75]),
        )

    def test_measurement_matrix(self) -> None:
        matrix = position_measurement_matrix()
        expected = np.zeros((3, 15))
        expected[:, 0:3] = np.eye(3)
        np.testing.assert_array_equal(matrix, expected)
        self.assertFalse(matrix.flags.writeable)

    def test_update_matches_linear_and_joseph_formulas(self) -> None:
        result = gnss_position_update(self.state, self.prior, self.measurement)
        h = position_measurement_matrix()
        innovation = self.measurement.position_n - self.state.position_n
        s = h @ self.prior @ h.T + self.measurement.covariance_n
        gain = np.linalg.solve(s, h @ self.prior).T
        correction = gain @ innovation
        residual = np.eye(15) - gain @ h
        joseph = residual @ self.prior @ residual.T + gain @ self.measurement.covariance_n @ gain.T
        reset = reset_jacobian(correction[6:9])
        expected_covariance = reset @ joseph @ reset.T
        expected_covariance = 0.5 * (expected_covariance + expected_covariance.T)

        np.testing.assert_allclose(result.innovation, innovation, atol=0.0)
        np.testing.assert_allclose(result.innovation_covariance, s, atol=1.0e-15)
        np.testing.assert_allclose(result.gain, gain, atol=2.0e-15)
        np.testing.assert_allclose(result.correction, correction, atol=2.0e-15)
        np.testing.assert_allclose(result.covariance, expected_covariance, atol=2.0e-15)
        self.assertAlmostEqual(result.nis, float(innovation @ np.linalg.solve(s, innovation)), places=14)

    def test_diagonal_position_update_has_closed_form(self) -> None:
        state = NominalState.identity(timestamp=2.0)
        prior = np.eye(15)
        measurement = GnssPositionMeasurement(2.0, [2.0, -4.0, 6.0], 3.0 * np.eye(3))
        result = gnss_position_update(state, prior, measurement)
        np.testing.assert_allclose(result.state.position_n, [0.5, -1.0, 1.5], atol=1.0e-15)
        np.testing.assert_allclose(np.diag(result.covariance)[0:3], 0.75 * np.ones(3), atol=1.0e-15)
        np.testing.assert_allclose(result.correction[3:], np.zeros(12), atol=0.0)

    def test_zero_innovation_preserves_state_and_reduces_position_variance(self) -> None:
        measurement = GnssPositionMeasurement(
            self.state.timestamp,
            self.state.position_n,
            0.1 * np.eye(3),
        )
        result = gnss_position_update(self.state, self.prior, measurement)
        np.testing.assert_array_equal(result.correction, np.zeros(15))
        np.testing.assert_array_equal(result.state.position_n, self.state.position_n)
        self.assertEqual(result.nis, 0.0)
        self.assertTrue(np.all(np.diag(result.covariance)[0:3] < np.diag(self.prior)[0:3]))

    def test_correlations_update_nonposition_states(self) -> None:
        prior = np.eye(15)
        prior[0, 3] = prior[3, 0] = 0.25
        measurement = GnssPositionMeasurement(5.0, [11.0, -2.0, 3.0], np.eye(3))
        result = gnss_position_update(self.state, prior, measurement)
        self.assertGreater(result.correction[3], 0.0)
        self.assertGreater(result.state.velocity_n[0], self.state.velocity_n[0])

    def test_result_arrays_are_readonly_and_inputs_unchanged(self) -> None:
        prior = self.prior.copy()
        prior_snapshot = prior.copy()
        state_snapshot = self.state.position_n.copy()
        measurement_snapshot = self.measurement.position_n.copy()
        result = gnss_position_update(self.state, prior, self.measurement)
        np.testing.assert_array_equal(prior, prior_snapshot)
        np.testing.assert_array_equal(self.state.position_n, state_snapshot)
        np.testing.assert_array_equal(self.measurement.position_n, measurement_snapshot)
        for array in (
            result.covariance,
            result.innovation,
            result.innovation_covariance,
            result.gain,
            result.correction,
        ):
            self.assertFalse(array.flags.writeable)

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(TypeError):
            gnss_position_update(object(), self.prior, self.measurement)
        with self.assertRaises(TypeError):
            gnss_position_update(self.state, self.prior, object())
        with self.assertRaises(ValueError):
            gnss_position_update(
                self.state,
                self.prior,
                GnssPositionMeasurement(6.0, np.zeros(3), np.eye(3)),
            )
        with self.assertRaises(ValueError):
            gnss_position_update(self.state, np.eye(14), self.measurement)
        invalid = self.prior.copy()
        invalid[0, 1] = 0.1
        with self.assertRaises(ValueError):
            gnss_position_update(self.state, invalid, self.measurement)


if __name__ == "__main__":
    unittest.main()
