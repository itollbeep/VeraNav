"""Tests for error and consistency summaries."""

from __future__ import annotations

import unittest

import numpy as np

from veranav.metrics import (
    chi_square_coverage,
    chi_square_interval,
    maximum_position_error,
    root_mean_square_position_error,
    summarize_run,
)


class MetricsTest(unittest.TestCase):
    def test_position_rmse_closed_form(self) -> None:
        errors = np.array([[3.0, 4.0, 0.0], [0.0, 0.0, 0.0]])
        self.assertAlmostEqual(root_mean_square_position_error(errors), np.sqrt(12.5))

    def test_maximum_position_error(self) -> None:
        errors = np.array([[3.0, 4.0, 0.0], [1.0, 2.0, 2.0]])
        self.assertEqual(maximum_position_error(errors), 5.0)

    def test_chi_square_interval_is_ordered(self) -> None:
        lower, upper = chi_square_interval(3, 0.95)
        self.assertGreater(lower, 0.0)
        self.assertGreater(upper, lower)

    def test_chi_square_coverage(self) -> None:
        lower, upper = chi_square_interval(3)
        values = [lower, 0.5 * (lower + upper), upper, upper + 1.0]
        self.assertEqual(chi_square_coverage(values, 3), 0.75)

    def test_summary_handles_no_gnss_updates(self) -> None:
        summary = summarize_run(np.zeros((2, 3)), [], [15.0, 15.0])
        self.assertIsNone(summary.nis_mean)
        self.assertIsNone(summary.nis_coverage_95)
        self.assertEqual(summary.update_count, 0)

    def test_summary_counts_samples_and_updates(self) -> None:
        summary = summarize_run(np.zeros((3, 3)), [3.0, 3.0], [15.0, 15.0, 15.0])
        self.assertEqual(summary.sample_count, 3)
        self.assertEqual(summary.update_count, 2)

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            root_mean_square_position_error(np.zeros((0, 3)))
        with self.assertRaises(ValueError):
            chi_square_interval(0)
        with self.assertRaises(ValueError):
            summarize_run(np.zeros((2, 3)), [], [1.0])


if __name__ == "__main__":
    unittest.main()
