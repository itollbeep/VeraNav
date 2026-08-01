"""Tests for VeraNav NEES and right-error construction."""

from __future__ import annotations

import unittest

import numpy as np

from veranav.consistency import nees, state_error_vector
from veranav.math import quat_exp, quat_multiply
from veranav.state import NominalState


class StateErrorVectorTest(unittest.TestCase):
    def test_matches_right_error_definition(self) -> None:
        estimate = NominalState(
            timestamp=1.0,
            position_n=[1.0, 2.0, 3.0],
            velocity_n=[4.0, 5.0, 6.0],
            quaternion_nb=quat_exp([0.2, -0.1, 0.3]),
            accel_bias_b=[0.01, 0.02, 0.03],
            gyro_bias_b=[0.001, 0.002, 0.003],
        )
        delta = np.linspace(-0.07, 0.07, 15)
        truth = NominalState(
            timestamp=1.0,
            position_n=estimate.position_n + delta[0:3],
            velocity_n=estimate.velocity_n + delta[3:6],
            quaternion_nb=quat_multiply(estimate.quaternion_nb, quat_exp(delta[6:9])),
            accel_bias_b=estimate.accel_bias_b + delta[9:12],
            gyro_bias_b=estimate.gyro_bias_b + delta[12:15],
        )
        np.testing.assert_allclose(state_error_vector(estimate, truth), delta, atol=2.0e-16)

    def test_quaternion_sign_does_not_change_error(self) -> None:
        estimate = NominalState.identity()
        truth_positive = NominalState(
            timestamp=0.0,
            position_n=np.zeros(3),
            velocity_n=np.zeros(3),
            quaternion_nb=quat_exp([0.1, -0.2, 0.3]),
            accel_bias_b=np.zeros(3),
            gyro_bias_b=np.zeros(3),
        )
        truth_negative = NominalState(
            timestamp=0.0,
            position_n=np.zeros(3),
            velocity_n=np.zeros(3),
            quaternion_nb=-truth_positive.quaternion_nb,
            accel_bias_b=np.zeros(3),
            gyro_bias_b=np.zeros(3),
        )
        np.testing.assert_allclose(
            state_error_vector(estimate, truth_positive),
            state_error_vector(estimate, truth_negative),
        )

    def test_rejects_invalid_types_and_timestamps(self) -> None:
        state = NominalState.identity()
        with self.assertRaises(TypeError):
            state_error_vector(object(), state)
        with self.assertRaises(TypeError):
            state_error_vector(state, object())
        with self.assertRaises(ValueError):
            state_error_vector(state, NominalState.identity(timestamp=1.0))


class NeesTest(unittest.TestCase):
    def test_zero_error_has_zero_nees(self) -> None:
        state = NominalState.identity()
        self.assertEqual(nees(state, state.copy(), np.eye(15)), 0.0)

    def test_diagonal_closed_form(self) -> None:
        estimate = NominalState.identity()
        truth = NominalState(
            timestamp=0.0,
            position_n=[1.0, 2.0, 3.0],
            velocity_n=np.zeros(3),
            quaternion_nb=[1.0, 0.0, 0.0, 0.0],
            accel_bias_b=np.zeros(3),
            gyro_bias_b=np.zeros(3),
        )
        covariance = np.diag(np.arange(1.0, 16.0))
        expected = 1.0 / 1.0 + 4.0 / 2.0 + 9.0 / 3.0
        self.assertAlmostEqual(nees(estimate, truth, covariance), expected, places=14)

    def test_rejects_invalid_covariance(self) -> None:
        state = NominalState.identity()
        with self.assertRaises(ValueError):
            nees(state, state, np.eye(14))
        with self.assertRaises(ValueError):
            nees(state, state, np.full((15, 15), np.nan))
        asymmetric = np.eye(15)
        asymmetric[0, 1] = 0.1
        with self.assertRaises(ValueError):
            nees(state, state, asymmetric)
        singular = np.eye(15)
        singular[-1, -1] = 0.0
        with self.assertRaises(ValueError):
            nees(state, state, singular)


if __name__ == "__main__":
    unittest.main()
