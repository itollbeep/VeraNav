"""Tests for structured GNSS degradation."""

from __future__ import annotations

import unittest

import numpy as np

from veranav.degradation import GnssDegradation, apply_gnss_degradation
from veranav.measurement import GnssPositionMeasurement


def measurement(timestamp: float) -> GnssPositionMeasurement:
    return GnssPositionMeasurement(timestamp, [1.0, 2.0, 3.0], np.eye(3))


class GnssDegradationTest(unittest.TestCase):
    def test_outage_uses_half_open_window(self) -> None:
        model = GnssDegradation(outage_start_s=2.0, outage_duration_s=3.0)
        self.assertFalse(model.is_outage(1.999))
        self.assertTrue(model.is_outage(2.0))
        self.assertTrue(model.is_outage(4.999))
        self.assertFalse(model.is_outage(5.0))

    def test_bias_uses_half_open_window(self) -> None:
        model = GnssDegradation(bias_start_s=1.0, bias_duration_s=2.0, bias_n=[4.0, -1.0, 0.5])
        biased = apply_gnss_degradation(measurement(2.0), model)
        self.assertIsNotNone(biased)
        np.testing.assert_allclose(biased.position_n, [5.0, 1.0, 3.5], atol=0.0)
        outside = apply_gnss_degradation(measurement(3.0), model)
        np.testing.assert_array_equal(outside.position_n, [1.0, 2.0, 3.0])

    def test_outage_precedes_bias(self) -> None:
        model = GnssDegradation(
            outage_start_s=1.0,
            outage_duration_s=2.0,
            bias_start_s=1.0,
            bias_duration_s=2.0,
            bias_n=[10.0, 0.0, 0.0],
        )
        self.assertIsNone(apply_gnss_degradation(measurement(2.0), model))

    def test_clean_measurement_is_returned_without_copy(self) -> None:
        original = measurement(0.0)
        self.assertIs(apply_gnss_degradation(original, GnssDegradation()), original)

    def test_rejects_invalid_models_and_types(self) -> None:
        with self.assertRaises(ValueError):
            GnssDegradation(outage_duration_s=1.0)
        with self.assertRaises(ValueError):
            GnssDegradation(bias_duration_s=1.0, bias_n=[1.0, 0.0, 0.0])
        with self.assertRaises(TypeError):
            apply_gnss_degradation(object(), GnssDegradation())


if __name__ == "__main__":
    unittest.main()
