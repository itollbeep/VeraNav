"""Deterministic Monte Carlo aggregation for VeraNav experiments."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from veranav.experiment import ExperimentConfig, run_synthetic_experiment
from veranav.metrics import RunMetrics


@dataclass(frozen=True, slots=True)
class FailureCriteria:
    """Run-level thresholds used to classify estimator reliability."""

    max_position_rmse_m: float = 5.0
    max_position_error_m: float = 15.0

    def __post_init__(self) -> None:
        for name in ("max_position_rmse_m", "max_position_error_m"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and strictly positive")
            object.__setattr__(self, name, value)

    def accepts(self, metrics: RunMetrics) -> bool:
        if not isinstance(metrics, RunMetrics):
            raise TypeError("metrics must be a RunMetrics")
        return (
            metrics.position_rmse_m <= self.max_position_rmse_m
            and metrics.position_max_m <= self.max_position_error_m
        )


@dataclass(frozen=True, slots=True, eq=False)
class MonteCarloSummary:
    """Aggregate metrics from a fixed sequence of deterministic seeds."""

    seeds: tuple[int, ...]
    run_metrics: tuple[RunMetrics, ...]
    position_rmse_mean_m: float
    position_rmse_p95_m: float
    position_max_p95_m: float
    divergence_rate: float

    def __post_init__(self) -> None:
        if len(self.seeds) == 0 or len(self.seeds) != len(self.run_metrics):
            raise ValueError("seeds and run_metrics must have equal nonzero length")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("seeds must be unique")
        for seed in self.seeds:
            if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
                raise ValueError("all seeds must be nonnegative integers")
        for metrics in self.run_metrics:
            if not isinstance(metrics, RunMetrics):
                raise TypeError("run_metrics must contain only RunMetrics objects")
        for name in (
            "position_rmse_mean_m",
            "position_rmse_p95_m",
            "position_max_p95_m",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
            object.__setattr__(self, name, value)
        rate = float(self.divergence_rate)
        if not math.isfinite(rate) or not 0.0 <= rate <= 1.0:
            raise ValueError("divergence_rate must be between 0 and 1")
        object.__setattr__(self, "divergence_rate", rate)


def _validated_seeds(seeds: Iterable[int]) -> tuple[int, ...]:
    result = tuple(seeds)
    if len(result) == 0:
        raise ValueError("seeds must not be empty")
    if len(set(result)) != len(result):
        raise ValueError("seeds must be unique")
    if any(
        not isinstance(seed, int) or isinstance(seed, bool) or seed < 0
        for seed in result
    ):
        raise ValueError("all seeds must be nonnegative integers")
    return result


def run_monte_carlo(
    config: ExperimentConfig,
    seeds: Iterable[int],
    criteria: FailureCriteria = FailureCriteria(),
) -> MonteCarloSummary:
    """Run a deterministic seed sequence and aggregate reliability metrics."""
    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    if not isinstance(criteria, FailureCriteria):
        raise TypeError("criteria must be a FailureCriteria")
    seed_tuple = _validated_seeds(seeds)
    metrics = tuple(run_synthetic_experiment(config, seed).metrics for seed in seed_tuple)
    rmse = np.asarray([item.position_rmse_m for item in metrics], dtype=np.float64)
    maxima = np.asarray([item.position_max_m for item in metrics], dtype=np.float64)
    accepted = np.asarray([criteria.accepts(item) for item in metrics], dtype=bool)
    return MonteCarloSummary(
        seeds=seed_tuple,
        run_metrics=metrics,
        position_rmse_mean_m=float(np.mean(rmse)),
        position_rmse_p95_m=float(np.quantile(rmse, 0.95)),
        position_max_p95_m=float(np.quantile(maxima, 0.95)),
        divergence_rate=float(1.0 - np.mean(accepted)),
    )


__all__ = ["FailureCriteria", "MonteCarloSummary", "run_monte_carlo"]
