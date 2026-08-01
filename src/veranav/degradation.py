"""Structured GNSS outage and bias injection for VeraNav."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import ArrayLike, NDArray

from veranav.measurement import GnssPositionMeasurement

FloatArray = NDArray[np.float64]


def _optional_time(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be None or a finite nonnegative value")
    return result


def _finite_nonnegative(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def _readonly_vector(value: ArrayLike, name: str) -> FloatArray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values")
    result = vector.copy()
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True, eq=False)
class GnssDegradation:
    """Half-open GNSS outage and additive-bias windows."""

    outage_start_s: float | None = None
    outage_duration_s: float = 0.0
    bias_start_s: float | None = None
    bias_duration_s: float = 0.0
    bias_n: FloatArray = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "outage_start_s",
            _optional_time(self.outage_start_s, "outage_start_s"),
        )
        object.__setattr__(
            self,
            "bias_start_s",
            _optional_time(self.bias_start_s, "bias_start_s"),
        )
        object.__setattr__(
            self,
            "outage_duration_s",
            _finite_nonnegative(self.outage_duration_s, "outage_duration_s"),
        )
        object.__setattr__(
            self,
            "bias_duration_s",
            _finite_nonnegative(self.bias_duration_s, "bias_duration_s"),
        )
        object.__setattr__(self, "bias_n", _readonly_vector(self.bias_n, "bias_n"))
        if self.outage_duration_s > 0.0 and self.outage_start_s is None:
            raise ValueError("outage_start_s is required when outage_duration_s is positive")
        if self.bias_duration_s > 0.0 and self.bias_start_s is None:
            raise ValueError("bias_start_s is required when bias_duration_s is positive")

    def is_outage(self, timestamp: float) -> bool:
        time = float(timestamp)
        if not math.isfinite(time):
            raise ValueError("timestamp must be finite")
        if self.outage_start_s is None or self.outage_duration_s == 0.0:
            return False
        return self.outage_start_s <= time < self.outage_start_s + self.outage_duration_s

    def has_bias(self, timestamp: float) -> bool:
        time = float(timestamp)
        if not math.isfinite(time):
            raise ValueError("timestamp must be finite")
        if self.bias_start_s is None or self.bias_duration_s == 0.0:
            return False
        return self.bias_start_s <= time < self.bias_start_s + self.bias_duration_s


def apply_gnss_degradation(
    measurement: GnssPositionMeasurement,
    degradation: GnssDegradation,
) -> GnssPositionMeasurement | None:
    """Drop or bias one GNSS position measurement without mutating it."""
    if not isinstance(measurement, GnssPositionMeasurement):
        raise TypeError("measurement must be a GnssPositionMeasurement")
    if not isinstance(degradation, GnssDegradation):
        raise TypeError("degradation must be a GnssDegradation")
    if degradation.is_outage(measurement.timestamp):
        return None
    if not degradation.has_bias(measurement.timestamp):
        return measurement
    return GnssPositionMeasurement(
        timestamp=measurement.timestamp,
        position_n=measurement.position_n + degradation.bias_n,
        covariance_n=measurement.covariance_n,
    )


__all__ = ["GnssDegradation", "apply_gnss_degradation"]
