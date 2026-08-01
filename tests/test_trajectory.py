"""Tests for common position trajectories and time-aligned metrics."""

from __future__ import annotations

import unittest

import numpy as np

from veranav.trajectory import (
    PositionTrajectory,
    evaluate_position_trajectory,
    interpolate_positions,
)


class PositionTrajectoryTest(unittest.TestCase):
    def test_constructor_copies_and_freezes_arrays(self) -> None:
        timestamps = np.array([0.0, 1.0, 2.0])
        positions = np.array([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0], [2.0, 4.0, 6.0]])
        value = PositionTrajectory(timestamps, positions, "test")
        timestamps[0] = 99.0
        positions[0, 0] = 99.0
        self.assertEqual(value.timestamps_s[0], 0.0)
        self.assertEqual(value.positions_n_m[0, 0], 0.0)
        self.assertFalse(value.timestamps_s.flags.writeable)
        self.assertFalse(value.positions_n_m.flags.writeable)

    def test_rejects_invalid_shapes_times_and_frame(self) -> None:
        with self.assertRaises(ValueError):
            PositionTrajectory([0.0], [[0.0, 0.0, 0.0]], "x")
        with self.assertRaises(ValueError):
            PositionTrajectory([0.0, 0.0], np.zeros((2, 3)), "x")
        with self.assertRaises(ValueError):
            PositionTrajectory([0.0, 1.0], np.zeros((2, 2)), "x")
        with self.assertRaises(ValueError):
            PositionTrajectory([0.0, 1.0], np.zeros((2, 3)), "")
        with self.assertRaises(ValueError):
            PositionTrajectory([0.0, 1.0], np.zeros((2, 3)), "x", frame="ENU")

    def test_linear_interpolation(self) -> None:
        trajectory = PositionTrajectory(
            [0.0, 1.0, 2.0],
            [[0.0, 0.0, 0.0], [2.0, 4.0, 6.0], [4.0, 8.0, 12.0]],
            "linear",
        )
        result = interpolate_positions(trajectory, [0.5, 1.5])
        np.testing.assert_allclose(result, [[1.0, 2.0, 3.0], [3.0, 6.0, 9.0]])
        self.assertFalse(result.flags.writeable)

    def test_interpolation_rejects_extrapolation(self) -> None:
        trajectory = PositionTrajectory([0.0, 1.0], np.zeros((2, 3)), "x")
        with self.assertRaises(ValueError):
            interpolate_positions(trajectory, [-0.1, 0.5])
        with self.assertRaises(ValueError):
            interpolate_positions(trajectory, [0.5, 1.1])

    def test_evaluation_closed_form(self) -> None:
        reference = PositionTrajectory(
            [0.0, 1.0, 2.0],
            np.zeros((3, 3)),
            "reference",
        )
        estimate = PositionTrajectory(
            [0.0, 2.0],
            [[1.0, 0.0, 0.0], [3.0, 0.0, 0.0]],
            "estimate",
        )
        result = evaluate_position_trajectory(reference, estimate)
        np.testing.assert_allclose(result.errors_n_m[:, 0], [1.0, 2.0, 3.0])
        self.assertAlmostEqual(result.metrics.position_mean_m, 2.0)
        self.assertAlmostEqual(result.metrics.position_rmse_m, np.sqrt(14.0 / 3.0))
        self.assertAlmostEqual(result.metrics.position_max_m, 3.0)
        self.assertEqual(result.metrics.sample_count, 3)

    def test_evaluation_uses_common_interval(self) -> None:
        reference = PositionTrajectory(
            [0.0, 1.0, 2.0, 3.0],
            np.zeros((4, 3)),
            "reference",
        )
        estimate = PositionTrajectory(
            [1.0, 2.0, 3.0],
            np.zeros((3, 3)),
            "estimate",
        )
        result = evaluate_position_trajectory(reference, estimate)
        np.testing.assert_array_equal(result.timestamps_s, [1.0, 2.0, 3.0])
        self.assertEqual(result.metrics.sample_count, 3)

    def test_evaluation_rejects_no_overlap_and_invalid_types(self) -> None:
        first = PositionTrajectory([0.0, 1.0], np.zeros((2, 3)), "first")
        second = PositionTrajectory([2.0, 3.0], np.zeros((2, 3)), "second")
        with self.assertRaises(ValueError):
            evaluate_position_trajectory(first, second)
        with self.assertRaises(TypeError):
            evaluate_position_trajectory("bad", second)
        with self.assertRaises(TypeError):
            interpolate_positions("bad", [0.0, 1.0])


if __name__ == "__main__":
    unittest.main()
