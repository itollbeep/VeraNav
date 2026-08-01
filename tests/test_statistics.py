"""Tests for deterministic reliability-study confidence intervals."""

import math
import unittest

import numpy as np

from veranav.statistics import (
    BootstrapInterval,
    ConfidenceInterval,
    paired_bootstrap_mean_difference,
    wilson_score_interval,
)


class ConfidenceIntervalTest(unittest.TestCase):
    def test_accepts_ordered_finite_values(self) -> None:
        interval = ConfidenceInterval(0.5, 0.2, 0.8, 0.95)
        self.assertEqual(interval.estimate, 0.5)

    def test_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            ConfidenceInterval(0.5, 0.6, 0.8, 0.95)
        with self.assertRaises(ValueError):
            ConfidenceInterval(0.5, 0.2, math.inf, 0.95)
        with self.assertRaises(ValueError):
            ConfidenceInterval(0.5, 0.2, 0.8, 1.0)


class WilsonIntervalTest(unittest.TestCase):
    def test_known_midpoint_interval(self) -> None:
        interval = wilson_score_interval(5, 10)
        self.assertAlmostEqual(interval.estimate, 0.5)
        self.assertAlmostEqual(interval.lower, 0.2365930905, places=9)
        self.assertAlmostEqual(interval.upper, 0.7634069095, places=9)

    def test_zero_and_all_successes_stay_in_probability_range(self) -> None:
        zero = wilson_score_interval(0, 20)
        full = wilson_score_interval(20, 20)
        self.assertEqual(zero.estimate, 0.0)
        self.assertGreaterEqual(zero.lower, 0.0)
        self.assertLessEqual(zero.upper, 1.0)
        self.assertEqual(full.estimate, 1.0)
        self.assertGreaterEqual(full.lower, 0.0)
        self.assertLessEqual(full.upper, 1.0)

    def test_rejects_invalid_counts(self) -> None:
        for args in ((-1, 10), (11, 10), (0, 0), (True, 10)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                wilson_score_interval(*args)


class PairedBootstrapTest(unittest.TestCase):
    def test_constant_difference_is_exact(self) -> None:
        interval = paired_bootstrap_mean_difference(
            [1.0, 2.0, 3.0],
            [2.5, 3.5, 4.5],
            resamples=100,
            seed=7,
        )
        self.assertIsInstance(interval, BootstrapInterval)
        self.assertAlmostEqual(interval.estimate, 1.5)
        self.assertAlmostEqual(interval.lower, 1.5)
        self.assertAlmostEqual(interval.upper, 1.5)

    def test_fixed_seed_is_repeatable(self) -> None:
        first = paired_bootstrap_mean_difference(
            [1.0, 3.0, 5.0, 8.0],
            [2.0, 2.0, 8.0, 7.0],
            resamples=500,
            seed=91,
        )
        second = paired_bootstrap_mean_difference(
            [1.0, 3.0, 5.0, 8.0],
            [2.0, 2.0, 8.0, 7.0],
            resamples=500,
            seed=91,
        )
        self.assertEqual(first.estimate, second.estimate)
        self.assertEqual(first.lower, second.lower)
        self.assertEqual(first.upper, second.upper)

    def test_estimate_matches_direct_paired_mean(self) -> None:
        baseline = np.array([1.0, 3.0, 2.0, 6.0])
        degraded = np.array([4.0, 2.0, 5.0, 8.0])
        interval = paired_bootstrap_mean_difference(
            baseline,
            degraded,
            resamples=250,
            seed=3,
        )
        self.assertAlmostEqual(
            interval.estimate,
            float(np.mean(degraded - baseline)),
        )
        self.assertLessEqual(interval.lower, interval.estimate)
        self.assertGreaterEqual(interval.upper, interval.estimate)

    def test_rejects_invalid_inputs(self) -> None:
        cases = (
            ([], []),
            ([1.0], [1.0, 2.0]),
            ([1.0, math.nan], [1.0, 2.0]),
        )
        for baseline, degraded in cases:
            with self.subTest(baseline=baseline), self.assertRaises(ValueError):
                paired_bootstrap_mean_difference(baseline, degraded)
        with self.assertRaises(ValueError):
            paired_bootstrap_mean_difference([1.0], [2.0], resamples=0)


if __name__ == "__main__":
    unittest.main()
