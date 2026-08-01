"""Seed-paired experiment comparison for structured navigation degradation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from veranav.experiment import ExperimentConfig, run_synthetic_experiment
from veranav.metrics import RunMetrics
from veranav.monte_carlo import FailureCriteria
from veranav.statistics import BootstrapInterval, paired_bootstrap_mean_difference

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


def _seeds(values: Iterable[int]) -> tuple[int, ...]:
    result = tuple(values)
    if len(result) == 0 or len(set(result)) != len(result):
        raise ValueError("seeds must be a nonempty sequence of unique values")
    if any(
        not isinstance(seed, int) or isinstance(seed, bool) or seed < 0
        for seed in result
    ):
        raise ValueError("seeds must contain nonnegative integers")
    return result


def _readonly_vector(value: NDArray[np.generic], dtype: np.dtype) -> NDArray[np.generic]:
    array = np.asarray(value, dtype=dtype)
    if array.ndim != 1 or not np.all(np.isfinite(array.astype(np.float64))):
        raise ValueError("comparison arrays must be finite and one-dimensional")
    result = array.copy()
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True, eq=False)
class PairedComparison:
    """Run-by-run paired degradation effect for a common seed sequence."""

    seeds: tuple[int, ...]
    baseline_metrics: tuple[RunMetrics, ...]
    degraded_metrics: tuple[RunMetrics, ...]
    rmse_differences_m: FloatArray
    maximum_error_differences_m: FloatArray
    baseline_failures: BoolArray
    degraded_failures: BoolArray
    rmse_difference_interval_m: BootstrapInterval
    maximum_error_difference_interval_m: BootstrapInterval
    degraded_only_failure_count: int
    recovered_failure_count: int

    def __post_init__(self) -> None:
        count = len(self.seeds)
        if count < 1 or len(set(self.seeds)) != count:
            raise ValueError("seeds must be unique and nonempty")
        if any(
            not isinstance(seed, int) or isinstance(seed, bool) or seed < 0
            for seed in self.seeds
        ):
            raise ValueError("seeds must contain nonnegative integers")
        if len(self.baseline_metrics) != count or len(self.degraded_metrics) != count:
            raise ValueError("metric sequences must match the seed count")
        if any(not isinstance(item, RunMetrics) for item in self.baseline_metrics):
            raise TypeError("baseline_metrics must contain RunMetrics objects")
        if any(not isinstance(item, RunMetrics) for item in self.degraded_metrics):
            raise TypeError("degraded_metrics must contain RunMetrics objects")
        rmse = _readonly_vector(self.rmse_differences_m, np.dtype(np.float64))
        maxima = _readonly_vector(
            self.maximum_error_differences_m,
            np.dtype(np.float64),
        )
        baseline_failures = _readonly_vector(
            self.baseline_failures,
            np.dtype(bool),
        )
        degraded_failures = _readonly_vector(
            self.degraded_failures,
            np.dtype(bool),
        )
        if any(array.size != count for array in (rmse, maxima, baseline_failures, degraded_failures)):
            raise ValueError("comparison arrays must match the seed count")
        object.__setattr__(self, "rmse_differences_m", rmse)
        object.__setattr__(self, "maximum_error_differences_m", maxima)
        object.__setattr__(self, "baseline_failures", baseline_failures)
        object.__setattr__(self, "degraded_failures", degraded_failures)
        for name in ("rmse_difference_interval_m", "maximum_error_difference_interval_m"):
            if not isinstance(getattr(self, name), BootstrapInterval):
                raise TypeError(f"{name} must be a BootstrapInterval")
        for name in ("degraded_only_failure_count", "recovered_failure_count"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= count:
                raise ValueError(f"{name} must be between zero and the seed count")

    @property
    def degraded_failure_rate(self) -> float:
        return float(np.mean(self.degraded_failures))

    @property
    def baseline_failure_rate(self) -> float:
        return float(np.mean(self.baseline_failures))

    @property
    def rmse_worsening_probability(self) -> float:
        return float(np.mean(self.rmse_differences_m > 0.0))


def compare_experiment_configs(
    baseline_config: ExperimentConfig,
    degraded_config: ExperimentConfig,
    seeds: Iterable[int],
    criteria: FailureCriteria = FailureCriteria(),
    *,
    bootstrap_resamples: int = 2_000,
    confidence: float = 0.95,
    bootstrap_seed: int = 0,
) -> PairedComparison:
    """Compare baseline and degraded runs with identical random seeds."""
    if not isinstance(baseline_config, ExperimentConfig):
        raise TypeError("baseline_config must be an ExperimentConfig")
    if not isinstance(degraded_config, ExperimentConfig):
        raise TypeError("degraded_config must be an ExperimentConfig")
    if not isinstance(criteria, FailureCriteria):
        raise TypeError("criteria must be a FailureCriteria")
    seed_tuple = _seeds(seeds)
    baseline = tuple(
        run_synthetic_experiment(baseline_config, seed).metrics
        for seed in seed_tuple
    )
    degraded = tuple(
        run_synthetic_experiment(degraded_config, seed).metrics
        for seed in seed_tuple
    )
    baseline_rmse = np.asarray(
        [item.position_rmse_m for item in baseline],
        dtype=np.float64,
    )
    degraded_rmse = np.asarray(
        [item.position_rmse_m for item in degraded],
        dtype=np.float64,
    )
    baseline_maximum = np.asarray(
        [item.position_max_m for item in baseline],
        dtype=np.float64,
    )
    degraded_maximum = np.asarray(
        [item.position_max_m for item in degraded],
        dtype=np.float64,
    )
    baseline_failures = np.asarray(
        [not criteria.accepts(item) for item in baseline],
        dtype=bool,
    )
    degraded_failures = np.asarray(
        [not criteria.accepts(item) for item in degraded],
        dtype=bool,
    )
    return PairedComparison(
        seeds=seed_tuple,
        baseline_metrics=baseline,
        degraded_metrics=degraded,
        rmse_differences_m=degraded_rmse - baseline_rmse,
        maximum_error_differences_m=degraded_maximum - baseline_maximum,
        baseline_failures=baseline_failures,
        degraded_failures=degraded_failures,
        rmse_difference_interval_m=paired_bootstrap_mean_difference(
            baseline_rmse,
            degraded_rmse,
            resamples=bootstrap_resamples,
            confidence=confidence,
            seed=bootstrap_seed,
        ),
        maximum_error_difference_interval_m=paired_bootstrap_mean_difference(
            baseline_maximum,
            degraded_maximum,
            resamples=bootstrap_resamples,
            confidence=confidence,
            seed=bootstrap_seed + 1,
        ),
        degraded_only_failure_count=int(
            np.sum(~baseline_failures & degraded_failures)
        ),
        recovered_failure_count=int(
            np.sum(baseline_failures & ~degraded_failures)
        ),
    )


__all__ = ["PairedComparison", "compare_experiment_configs"]
