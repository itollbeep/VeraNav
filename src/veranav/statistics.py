"""Deterministic confidence intervals for VeraNav reliability studies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from numpy.typing import NDArray
from scipy.stats import norm

FloatArray = NDArray[np.float64]


def _confidence(value: float) -> float:
    result = float(value)
    if not math.isfinite(result) or not 0.0 < result < 1.0:
        raise ValueError("confidence must be finite and strictly between 0 and 1")
    return result


def _paired_values(
    baseline: Iterable[float],
    degraded: Iterable[float],
) -> tuple[FloatArray, FloatArray]:
    first = np.asarray(tuple(baseline), dtype=np.float64)
    second = np.asarray(tuple(degraded), dtype=np.float64)
    if first.ndim != 1 or second.ndim != 1:
        raise ValueError("paired values must be one-dimensional")
    if first.size == 0 or first.shape != second.shape:
        raise ValueError("paired values must have equal nonzero length")
    if not np.all(np.isfinite(first)) or not np.all(np.isfinite(second)):
        raise ValueError("paired values must contain only finite values")
    return first, second


@dataclass(frozen=True, slots=True, eq=False)
class ConfidenceInterval:
    """Immutable scalar estimate and two-sided confidence interval."""

    estimate: float
    lower: float
    upper: float
    confidence: float

    def __post_init__(self) -> None:
        estimate = float(self.estimate)
        lower = float(self.lower)
        upper = float(self.upper)
        confidence = _confidence(self.confidence)
        if not all(math.isfinite(value) for value in (estimate, lower, upper)):
            raise ValueError("interval values must be finite")
        if lower > estimate or estimate > upper:
            raise ValueError("interval must satisfy lower <= estimate <= upper")
        object.__setattr__(self, "estimate", estimate)
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)
        object.__setattr__(self, "confidence", confidence)


@dataclass(frozen=True, slots=True, eq=False)
class BootstrapInterval(ConfidenceInterval):
    """Percentile bootstrap interval for a paired mean difference."""

    resamples: int
    seed: int

    def __post_init__(self) -> None:
        ConfidenceInterval.__post_init__(self)
        if (
            not isinstance(self.resamples, int)
            or isinstance(self.resamples, bool)
            or self.resamples < 1
        ):
            raise ValueError("resamples must be a positive integer")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer")


def wilson_score_interval(
    successes: int,
    trials: int,
    confidence: float = 0.95,
) -> ConfidenceInterval:
    """Return a Wilson score interval for a binomial success probability."""
    if not isinstance(trials, int) or isinstance(trials, bool) or trials < 1:
        raise ValueError("trials must be a positive integer")
    if (
        not isinstance(successes, int)
        or isinstance(successes, bool)
        or successes < 0
        or successes > trials
    ):
        raise ValueError("successes must be an integer between zero and trials")
    level = _confidence(confidence)
    proportion = successes / trials
    z = float(norm.ppf(0.5 + 0.5 * level))
    z2_over_n = z * z / trials
    denominator = 1.0 + z2_over_n
    center = (proportion + 0.5 * z2_over_n) / denominator
    half_width = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials
            + z * z / (4.0 * trials * trials)
        )
        / denominator
    )
    return ConfidenceInterval(
        estimate=proportion,
        lower=min(proportion, max(0.0, center - half_width)),
        upper=max(proportion, min(1.0, center + half_width)),
        confidence=level,
    )


def paired_bootstrap_mean_difference(
    baseline: Iterable[float],
    degraded: Iterable[float],
    *,
    resamples: int = 2_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> BootstrapInterval:
    """Bootstrap the paired mean difference ``degraded - baseline``."""
    first, second = _paired_values(baseline, degraded)
    if not isinstance(resamples, int) or isinstance(resamples, bool) or resamples < 1:
        raise ValueError("resamples must be a positive integer")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    level = _confidence(confidence)
    differences = second - first
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, differences.size, size=(resamples, differences.size))
    bootstrap_means = np.mean(differences[indices], axis=1)
    tail = 0.5 * (1.0 - level)
    lower, upper = np.quantile(bootstrap_means, [tail, 1.0 - tail])
    estimate = float(np.mean(differences))
    lower_value = min(float(lower), estimate)
    upper_value = max(float(upper), estimate)
    return BootstrapInterval(
        estimate=estimate,
        lower=lower_value,
        upper=upper_value,
        confidence=level,
        resamples=resamples,
        seed=seed,
    )


__all__ = [
    "BootstrapInterval",
    "ConfidenceInterval",
    "paired_bootstrap_mean_difference",
    "wilson_score_interval",
]
