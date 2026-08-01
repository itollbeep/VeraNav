"""Tests for validated VeraNav measurements."""

from __future__ import annotations

import unittest

import numpy as np

from veranav.measurement import GnssPositionMeasurement


class GnssPositionMeasurementTest(unittest.TestCase):
    def test_copies_inputs_and_stores_readonly_arrays(self) -> None:
        position = np.array([1.0, 2.0, 3.0])
        covariance = np.diag([1.0, 2.0, 3.0])
        measurement = GnssPositionMeasurement(4.0, position, covariance)
        position[0] = 99.0
        covariance[0, 0] = 99.0
        np.testing.assert_array_equal(measurement.position_n, [1.0, 2.0, 3.0])
        np.testing.assert_array_equal(
            measurement.covariance_n,
            np.diag([1.0, 2.0, 3.0]),
        )
        self.assertFalse(measurement.position_n.flags.writeable)
        self.assertFalse(measurement.covariance_n.flags.writeable)

    def test_accepts_correlated_positive_definite_covariance(self) -> None:
        covariance = np.array(
            [[2.0, 0.2, 0.1], [0.2, 1.5, -0.1], [0.1, -0.1, 1.0]]
        )
        measurement = GnssPositionMeasurement(0.0, np.zeros(3), covariance)
        np.testing.assert_allclose(measurement.covariance_n, covariance)

    def test_rejects_invalid_timestamp_and_position(self) -> None:
        with self.assertRaises(ValueError):
            GnssPositionMeasurement(np.nan, np.zeros(3), np.eye(3))
        with self.assertRaises(ValueError):
            GnssPositionMeasurement(0.0, np.zeros(2), np.eye(3))
        with self.assertRaises(ValueError):
            GnssPositionMeasurement(0.0, [0.0, np.inf, 0.0], np.eye(3))

    def test_rejects_invalid_covariance(self) -> None:
        invalid = (
            np.eye(2),
            np.full((3, 3), np.nan),
            np.array([[1.0, 0.2, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
            np.diag([1.0, 1.0, 0.0]),
            np.diag([1.0, 1.0, -1.0]),
        )
        for covariance in invalid:
            with self.subTest(covariance=covariance):
                with self.assertRaises(ValueError):
                    GnssPositionMeasurement(0.0, np.zeros(3), covariance)

    def test_distinct_measurements_use_identity_equality(self) -> None:
        first = GnssPositionMeasurement(0.0, np.zeros(3), np.eye(3))
        second = GnssPositionMeasurement(0.0, np.zeros(3), np.eye(3))
        self.assertTrue(first == first)
        self.assertFalse(first == second)


if __name__ == "__main__":
    unittest.main()
