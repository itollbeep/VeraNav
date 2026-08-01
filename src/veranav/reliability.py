"""Reliability-envelope grid evaluation under structured GNSS degradation."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from veranav.degradation import GnssDegradation
from veranav.experiment import ExperimentConfig
from veranav.monte_carlo import FailureCriteria, MonteCarloSummary, run_monte_carlo

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


def _levels(values: Iterable[float], name: str) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)
    if len(result) == 0:
        raise ValueError(f"{name} must not be empty")
    if any(not math.isfinite(value) or value < 0.0 for value in result):
        raise ValueError(f"{name} must contain finite nonnegative values")
    if tuple(sorted(set(result))) != result:
        raise ValueError(f"{name} must be strictly increasing without duplicates")
    return result


@dataclass(frozen=True, slots=True, eq=False)
class ReliabilityCell:
    """Monte Carlo outcome at one bias/outage degradation coordinate."""

    bias_magnitude_m: float
    outage_duration_s: float
    summary: MonteCarloSummary
    reliable: bool

    def __post_init__(self) -> None:
        for name in ("bias_magnitude_m", "outage_duration_s"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
            object.__setattr__(self, name, value)
        if not isinstance(self.summary, MonteCarloSummary):
            raise TypeError("summary must be a MonteCarloSummary")
        if not isinstance(self.reliable, bool):
            raise TypeError("reliable must be a bool")


@dataclass(frozen=True, slots=True, eq=False)
class ReliabilityEnvelope:
    """Rectangular reliability grid indexed by outage then bias level."""

    bias_magnitudes_m: tuple[float, ...]
    outage_durations_s: tuple[float, ...]
    cells: tuple[ReliabilityCell, ...]
    reliable_mask: BoolArray
    divergence_rates: FloatArray

    def __post_init__(self) -> None:
        expected_shape = (len(self.outage_durations_s), len(self.bias_magnitudes_m))
        if len(self.cells) != expected_shape[0] * expected_shape[1]:
            raise ValueError("cell count must match the rectangular grid")
        mask = np.asarray(self.reliable_mask, dtype=bool)
        rates = np.asarray(self.divergence_rates, dtype=np.float64)
        if mask.shape != expected_shape or rates.shape != expected_shape:
            raise ValueError("grid arrays must match outage-by-bias shape")
        if not np.all(np.isfinite(rates)) or np.any((rates < 0.0) | (rates > 1.0)):
            raise ValueError("divergence_rates must be finite and between 0 and 1")
        mask_copy = mask.copy()
        rates_copy = rates.copy()
        mask_copy.setflags(write=False)
        rates_copy.setflags(write=False)
        object.__setattr__(self, "reliable_mask", mask_copy)
        object.__setattr__(self, "divergence_rates", rates_copy)

    def maximum_reliable_bias_by_outage(self) -> tuple[float | None, ...]:
        boundary = []
        for row in self.reliable_mask:
            indices = np.flatnonzero(row)
            boundary.append(
                None if indices.size == 0 else self.bias_magnitudes_m[int(indices[-1])]
            )
        return tuple(boundary)


def evaluate_reliability_envelope(
    base_config: ExperimentConfig,
    bias_magnitudes_m: Iterable[float],
    outage_durations_s: Iterable[float],
    seeds: Iterable[int],
    *,
    fault_start_s: float,
    criteria: FailureCriteria = FailureCriteria(),
) -> ReliabilityEnvelope:
    """Evaluate a deterministic bias-by-outage reliability envelope."""
    if not isinstance(base_config, ExperimentConfig):
        raise TypeError("base_config must be an ExperimentConfig")
    if not isinstance(criteria, FailureCriteria):
        raise TypeError("criteria must be a FailureCriteria")
    start = float(fault_start_s)
    if not math.isfinite(start) or start < 0.0 or start > base_config.trajectory.duration_s:
        raise ValueError("fault_start_s must lie within the trajectory duration")
    bias_levels = _levels(bias_magnitudes_m, "bias_magnitudes_m")
    outage_levels = _levels(outage_durations_s, "outage_durations_s")
    seed_tuple = tuple(seeds)
    if len(seed_tuple) == 0:
        raise ValueError("seeds must not be empty")

    remaining = base_config.trajectory.duration_s - start + base_config.trajectory.imu_dt
    cells = []
    mask = np.zeros((len(outage_levels), len(bias_levels)), dtype=bool)
    rates = np.zeros_like(mask, dtype=np.float64)

    for row, outage_duration in enumerate(outage_levels):
        for column, bias_magnitude in enumerate(bias_levels):
            degradation = GnssDegradation(
                outage_start_s=start if outage_duration > 0.0 else None,
                outage_duration_s=outage_duration,
                bias_start_s=start if bias_magnitude > 0.0 else None,
                bias_duration_s=remaining if bias_magnitude > 0.0 else 0.0,
                bias_n=[bias_magnitude, 0.0, 0.0],
            )
            config = replace(base_config, degradation=degradation)
            summary = run_monte_carlo(config, seed_tuple, criteria)
            reliable = summary.divergence_rate == 0.0
            mask[row, column] = reliable
            rates[row, column] = summary.divergence_rate
            cells.append(
                ReliabilityCell(
                    bias_magnitude_m=bias_magnitude,
                    outage_duration_s=outage_duration,
                    summary=summary,
                    reliable=reliable,
                )
            )

    return ReliabilityEnvelope(
        bias_magnitudes_m=bias_levels,
        outage_durations_s=outage_levels,
        cells=tuple(cells),
        reliable_mask=mask,
        divergence_rates=rates,
    )


__all__ = [
    "ReliabilityCell",
    "ReliabilityEnvelope",
    "evaluate_reliability_envelope",
]
