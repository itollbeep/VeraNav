"""Tests for GNSS reliability-envelope evaluation."""

from __future__ import annotations

import unittest

import numpy as np

from veranav.experiment import ExperimentConfig
from veranav.monte_carlo import FailureCriteria
from veranav.reliability import evaluate_reliability_envelope
from veranav.simulation import CircularTrajectoryConfig


def config() -> ExperimentConfig:
    return ExperimentConfig(
        trajectory=CircularTrajectoryConfig(
            duration_s=0.6,
            imu_dt=0.05,
            gnss_dt=0.2,
            accel_noise_std=0.002,
            gyro_noise_std=0.0001,
            gnss_position_std_m=0.1,
        )
    )


class ReliabilityEnvelopeTest(unittest.TestCase):
    def test_grid_shape_and_cell_count(self) -> None:
        envelope = evaluate_reliability_envelope(
            config(),
            [0.0, 2.0],
            [0.0, 0.2],
            [1, 2],
            fault_start_s=0.2,
            criteria=FailureCriteria(100.0, 100.0),
        )
        self.assertEqual(envelope.reliable_mask.shape, (2, 2))
        self.assertEqual(len(envelope.cells), 4)
        self.assertFalse(envelope.reliable_mask.flags.writeable)
        self.assertFalse(envelope.divergence_rates.flags.writeable)

    def test_lenient_criteria_marks_all_cells_reliable(self) -> None:
        envelope = evaluate_reliability_envelope(
            config(),
            [0.0, 1.0],
            [0.0, 0.2],
            [1],
            fault_start_s=0.2,
            criteria=FailureCriteria(1000.0, 1000.0),
        )
        self.assertTrue(np.all(envelope.reliable_mask))
        self.assertEqual(envelope.maximum_reliable_bias_by_outage(), (1.0, 1.0))

    def test_strict_criteria_marks_all_cells_unreliable(self) -> None:
        envelope = evaluate_reliability_envelope(
            config(),
            [0.0, 1.0],
            [0.0],
            [1],
            fault_start_s=0.2,
            criteria=FailureCriteria(1.0e-12, 1.0e-12),
        )
        self.assertFalse(np.any(envelope.reliable_mask))
        self.assertEqual(envelope.maximum_reliable_bias_by_outage(), (None,))

    def test_rejects_unsorted_levels(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_reliability_envelope(
                config(),
                [1.0, 0.0],
                [0.0],
                [1],
                fault_start_s=0.2,
            )


if __name__ == "__main__":
    unittest.main()
