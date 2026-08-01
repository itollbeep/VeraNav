"""Tests for composable VeraNav ESKF prediction and update cycles."""

from __future__ import annotations

import unittest

import numpy as np

from veranav.covariance import ProcessNoise, propagate_error_covariance
from veranav.eskf import propagate_and_update_gnss_position, propagate_eskf
from veranav.imu import ImuSample, STANDARD_GRAVITY_MPS2, propagate_nominal
from veranav.measurement import GnssPositionMeasurement
from veranav.state import NominalState
from veranav.update import gnss_position_update


class EskfCompositionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = NominalState.identity(timestamp=0.0)
        self.sample = ImuSample(
            timestamp=0.0,
            specific_force_b=[0.5, 0.0, -STANDARD_GRAVITY_MPS2],
            angular_rate_b=[0.0, 0.0, 0.1],
        )
        self.noise = ProcessNoise(0.03, 0.004, 0.0003, 0.00004)
        self.covariance = 0.1 * np.eye(15)

    def test_propagation_matches_explicit_nominal_and_covariance_steps(self) -> None:
        result = propagate_eskf(
            self.state,
            self.covariance,
            self.sample,
            self.noise,
            0.1,
        )
        expected_state = propagate_nominal(self.state, self.sample, 0.1)
        expected_covariance = propagate_error_covariance(
            self.state,
            self.sample,
            self.covariance,
            self.noise,
            0.1,
        )
        np.testing.assert_allclose(result.state.position_n, expected_state.position_n)
        np.testing.assert_allclose(result.state.velocity_n, expected_state.velocity_n)
        np.testing.assert_allclose(result.state.quaternion_nb, expected_state.quaternion_nb)
        np.testing.assert_allclose(result.covariance, expected_covariance.covariance)
        np.testing.assert_allclose(result.transition, expected_covariance.transition)
        np.testing.assert_allclose(result.process_covariance, expected_covariance.process_covariance)

    def test_complete_cycle_matches_explicit_steps(self) -> None:
        predicted = propagate_eskf(
            self.state,
            self.covariance,
            self.sample,
            self.noise,
            0.1,
        )
        measurement = GnssPositionMeasurement(
            timestamp=0.1,
            position_n=[0.2, -0.1, 0.05],
            covariance_n=0.5 * np.eye(3),
        )
        expected_update = gnss_position_update(
            predicted.state,
            predicted.covariance,
            measurement,
        )
        cycle = propagate_and_update_gnss_position(
            self.state,
            self.covariance,
            self.sample,
            self.noise,
            0.1,
            measurement,
        )
        np.testing.assert_allclose(cycle.propagation.covariance, predicted.covariance)
        np.testing.assert_allclose(cycle.update.state.position_n, expected_update.state.position_n)
        np.testing.assert_allclose(cycle.update.covariance, expected_update.covariance)
        self.assertAlmostEqual(cycle.update.nis, expected_update.nis, places=15)

    def test_complete_cycle_rejects_measurement_at_wrong_time(self) -> None:
        measurement = GnssPositionMeasurement(
            timestamp=0.2,
            position_n=np.zeros(3),
            covariance_n=np.eye(3),
        )
        with self.assertRaises(ValueError):
            propagate_and_update_gnss_position(
                self.state,
                self.covariance,
                self.sample,
                self.noise,
                0.1,
                measurement,
            )

    def test_result_arrays_are_readonly_and_inputs_unchanged(self) -> None:
        covariance = self.covariance.copy()
        snapshot = covariance.copy()
        result = propagate_eskf(
            self.state,
            covariance,
            self.sample,
            self.noise,
            0.1,
        )
        np.testing.assert_array_equal(covariance, snapshot)
        for array in (result.covariance, result.transition, result.process_covariance):
            self.assertFalse(array.flags.writeable)


if __name__ == "__main__":
    unittest.main()
