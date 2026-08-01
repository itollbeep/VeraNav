"""Run-level error and statistical consistency summaries for VeraNav."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.stats import chi2

FloatArray = NDArray[np.float64]


def _error_matrix(value: ArrayLike) -> FloatArray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != 3 or matrix.shape[0] < 1:
        raise ValueError("position_errors must have shape (N, 3) with N >= 1")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("position_errors must contain only finite values")
    return matrix.copy()


def _finite_values(values: Iterable[float], name: str, *, allow_empty: bool) -> FloatArray:
    array = np.asarray(tuple(values), dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not allow_empty and array.size == 0:
        raise ValueError(f"{name} must not be empty")
    if not np.all(np.isfinite(array)) or np.any(array < 0.0):
        raise ValueError(f"{name} must contain finite nonnegative values")
    return array


def root_mean_square_position_error(position_errors: ArrayLike) -> float:
    errors = _error_matrix(position_errors)
    return float(np.sqrt(np.mean(np.sum(errors * errors, axis=1))))


def maximum_position_error(position_errors: ArrayLike) -> float:
    errors = _error_matrix(position_errors)
    return float(np.max(np.linalg.norm(errors, axis=1)))


def chi_square_interval(dof: int, confidence: float = 0.95) -> tuple[float, float]:
    if not isinstance(dof, int) or isinstance(dof, bool) or dof <= 0:
        raise ValueError("dof must be a positive integer")
    level = float(confidence)
    if not math.isfinite(level) or not 0.0 < level < 1.0:
        raise ValueError("confidence must be finite and strictly between 0 and 1")
    tail = 0.5 * (1.0 - level)
    return float(chi2.ppf(tail, dof)), float(chi2.ppf(1.0 - tail, dof))


def chi_square_coverage(
    values: Iterable[float],
    dof: int,
    confidence: float = 0.95,
) -> float:
    array = _finite_values(values, "values", allow_empty=False)
    lower, upper = chi_square_interval(dof, confidence)
    return float(np.mean((array >= lower) & (array <= upper)))


@dataclass(frozen=True, slots=True)
class RunMetrics:
    """Scalar summary of one estimator run."""

    position_rmse_m: float
    position_max_m: float
    nis_mean: float | None
    nis_coverage_95: float | None
    nees_mean: float
    nees_coverage_95: float
    update_count: int
    sample_count: int

    def __post_init__(self) -> None:
        for name in ("position_rmse_m", "position_max_m", "nees_mean"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
            object.__setattr__(self, name, value)
        for name in ("nis_mean", "nis_coverage_95"):
            value = getattr(self, name)
            if value is not None:
                scalar = float(value)
                if not math.isfinite(scalar) or scalar < 0.0:
                    raise ValueError(f"{name} must be None or finite and nonnegative")
                object.__setattr__(self, name, scalar)
        coverage = float(self.nees_coverage_95)
        if not math.isfinite(coverage) or not 0.0 <= coverage <= 1.0:
            raise ValueError("nees_coverage_95 must be between 0 and 1")
        object.__setattr__(self, "nees_coverage_95", coverage)
        if self.nis_coverage_95 is not None and self.nis_coverage_95 > 1.0:
            raise ValueError("nis_coverage_95 must not exceed 1")
        for name in ("update_count", "sample_count"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.sample_count < 1:
            raise ValueError("sample_count must be at least one")


def summarize_run(
    position_errors: ArrayLike,
    nis_values: Iterable[float],
    nees_values: Iterable[float],
) -> RunMetrics:
    errors = _error_matrix(position_errors)
    nis = _finite_values(nis_values, "nis_values", allow_empty=True)
    nees = _finite_values(nees_values, "nees_values", allow_empty=False)
    if nees.size != errors.shape[0]:
        raise ValueError("nees_values must contain one value per position error")
    return RunMetrics(
        position_rmse_m=root_mean_square_position_error(errors),
        position_max_m=maximum_position_error(errors),
        nis_mean=None if nis.size == 0 else float(np.mean(nis)),
        nis_coverage_95=None if nis.size == 0 else chi_square_coverage(nis, 3),
        nees_mean=float(np.mean(nees)),
        nees_coverage_95=chi_square_coverage(nees, 15),
        update_count=int(nis.size),
        sample_count=int(errors.shape[0]),
    )


__all__ = [
    "RunMetrics",
    "chi_square_coverage",
    "chi_square_interval",
    "maximum_position_error",
    "root_mean_square_position_error",
    "summarize_run",
]
