"""Common position-trajectory representation and evaluation utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


def _readonly_times(value: ArrayLike, name: str) -> FloatArray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 1 or array.size < 2:
        raise ValueError(f"{name} must be a one-dimensional array with at least two values")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    if not np.all(np.diff(array) > 0.0):
        raise ValueError(f"{name} must be strictly increasing")
    result = array.copy()
    result.setflags(write=False)
    return result


def _readonly_positions(value: ArrayLike, count: int, name: str) -> FloatArray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (count, 3):
        raise ValueError(f"{name} must have shape ({count}, 3)")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    result = array.copy()
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True, eq=False)
class PositionTrajectory:
    """Immutable NED position trajectory with strictly increasing timestamps."""

    timestamps_s: FloatArray
    positions_n_m: FloatArray
    source_name: str
    frame: str = "NED"

    def __post_init__(self) -> None:
        timestamps = _readonly_times(self.timestamps_s, "timestamps_s")
        positions = _readonly_positions(
            self.positions_n_m,
            timestamps.size,
            "positions_n_m",
        )
        source_name = str(self.source_name).strip()
        if not source_name:
            raise ValueError("source_name must not be empty")
        frame = str(self.frame).strip().upper()
        if frame != "NED":
            raise ValueError("frame must be NED in VeraNav V0.1")
        object.__setattr__(self, "timestamps_s", timestamps)
        object.__setattr__(self, "positions_n_m", positions)
        object.__setattr__(self, "source_name", source_name)
        object.__setattr__(self, "frame", frame)


@dataclass(frozen=True, slots=True, eq=False)
class PositionTrajectoryMetrics:
    """Position error metrics after time alignment."""

    sample_count: int
    start_time_s: float
    end_time_s: float
    position_rmse_m: float
    position_mean_m: float
    position_max_m: float

    def __post_init__(self) -> None:
        if not isinstance(self.sample_count, int) or isinstance(self.sample_count, bool):
            raise TypeError("sample_count must be an integer")
        if self.sample_count < 2:
            raise ValueError("sample_count must be at least two")
        start = float(self.start_time_s)
        end = float(self.end_time_s)
        if not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise ValueError("start_time_s and end_time_s must define a finite interval")
        for name in ("position_rmse_m", "position_mean_m", "position_max_m"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "start_time_s", start)
        object.__setattr__(self, "end_time_s", end)


@dataclass(frozen=True, slots=True, eq=False)
class PositionTrajectoryEvaluation:
    """Aligned position errors and their summary metrics."""

    timestamps_s: FloatArray
    errors_n_m: FloatArray
    metrics: PositionTrajectoryMetrics

    def __post_init__(self) -> None:
        timestamps = _readonly_times(self.timestamps_s, "timestamps_s")
        errors = _readonly_positions(self.errors_n_m, timestamps.size, "errors_n_m")
        if not isinstance(self.metrics, PositionTrajectoryMetrics):
            raise TypeError("metrics must be a PositionTrajectoryMetrics")
        if self.metrics.sample_count != timestamps.size:
            raise ValueError("metrics.sample_count must match the aligned sample count")
        object.__setattr__(self, "timestamps_s", timestamps)
        object.__setattr__(self, "errors_n_m", errors)


def interpolate_positions(
    trajectory: PositionTrajectory,
    query_timestamps_s: ArrayLike,
) -> FloatArray:
    """Linearly interpolate NED positions without extrapolation."""
    if not isinstance(trajectory, PositionTrajectory):
        raise TypeError("trajectory must be a PositionTrajectory")
    query = _readonly_times(query_timestamps_s, "query_timestamps_s")
    tolerance = 1.0e-12
    if query[0] < trajectory.timestamps_s[0] - tolerance:
        raise ValueError("query_timestamps_s begin before the trajectory")
    if query[-1] > trajectory.timestamps_s[-1] + tolerance:
        raise ValueError("query_timestamps_s end after the trajectory")
    values = np.column_stack(
        [
            np.interp(
                query,
                trajectory.timestamps_s,
                trajectory.positions_n_m[:, axis],
            )
            for axis in range(3)
        ]
    )
    values.setflags(write=False)
    return values


def evaluate_position_trajectory(
    reference: PositionTrajectory,
    estimate: PositionTrajectory,
) -> PositionTrajectoryEvaluation:
    """Evaluate an estimate on reference timestamps within their common interval."""
    if not isinstance(reference, PositionTrajectory):
        raise TypeError("reference must be a PositionTrajectory")
    if not isinstance(estimate, PositionTrajectory):
        raise TypeError("estimate must be a PositionTrajectory")
    if reference.frame != estimate.frame:
        raise ValueError("reference and estimate frames must match")

    start = max(reference.timestamps_s[0], estimate.timestamps_s[0])
    end = min(reference.timestamps_s[-1], estimate.timestamps_s[-1])
    if end <= start:
        raise ValueError("reference and estimate trajectories do not overlap")

    mask = (reference.timestamps_s >= start) & (reference.timestamps_s <= end)
    timestamps = reference.timestamps_s[mask]
    reference_positions = reference.positions_n_m[mask]
    if timestamps.size < 2:
        raise ValueError("trajectory overlap must contain at least two reference samples")

    estimate_positions = interpolate_positions(estimate, timestamps)
    errors = estimate_positions - reference_positions
    norms = np.linalg.norm(errors, axis=1)
    metrics = PositionTrajectoryMetrics(
        sample_count=int(timestamps.size),
        start_time_s=float(timestamps[0]),
        end_time_s=float(timestamps[-1]),
        position_rmse_m=float(np.sqrt(np.mean(norms * norms))),
        position_mean_m=float(np.mean(norms)),
        position_max_m=float(np.max(norms)),
    )
    return PositionTrajectoryEvaluation(
        timestamps_s=timestamps,
        errors_n_m=errors,
        metrics=metrics,
    )


__all__ = [
    "PositionTrajectory",
    "PositionTrajectoryEvaluation",
    "PositionTrajectoryMetrics",
    "evaluate_position_trajectory",
    "interpolate_positions",
]
