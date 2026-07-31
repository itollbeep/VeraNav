"""Nominal navigation state for VeraNav V0.1."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from veranav.math import quat_normalize

FloatArray = NDArray[np.float64]


def _readonly_vector(value: ArrayLike, length: int, name: str) -> FloatArray:
    """Return an immutable finite float64 vector with an exact shape."""
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (length,):
        raise ValueError(f"{name} must have shape ({length},), got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    result = array.copy()
    result.setflags(write=False)
    return result


def _readonly_quaternion(value: ArrayLike) -> FloatArray:
    """Return an immutable normalized scalar-first quaternion."""
    result = quat_normalize(value)
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True, eq=False)
class NominalState:
    """Immutable nominal state ``[p_n, v_n, q_nb, b_a, b_g]``.

    The constructor copies every input array and normalizes ``quaternion_nb``.
    Stored arrays are read-only so a propagated state cannot be modified through
    an alias held by the caller.
    """

    timestamp: float
    position_n: FloatArray
    velocity_n: FloatArray
    quaternion_nb: FloatArray
    accel_bias_b: FloatArray
    gyro_bias_b: FloatArray

    def __post_init__(self) -> None:
        timestamp = float(self.timestamp)
        if not math.isfinite(timestamp):
            raise ValueError("timestamp must be finite")

        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(
            self,
            "position_n",
            _readonly_vector(self.position_n, 3, "position_n"),
        )
        object.__setattr__(
            self,
            "velocity_n",
            _readonly_vector(self.velocity_n, 3, "velocity_n"),
        )
        object.__setattr__(
            self,
            "quaternion_nb",
            _readonly_quaternion(self.quaternion_nb),
        )
        object.__setattr__(
            self,
            "accel_bias_b",
            _readonly_vector(self.accel_bias_b, 3, "accel_bias_b"),
        )
        object.__setattr__(
            self,
            "gyro_bias_b",
            _readonly_vector(self.gyro_bias_b, 3, "gyro_bias_b"),
        )

    @classmethod
    def identity(cls, *, timestamp: float = 0.0) -> "NominalState":
        """Return a zero-motion, zero-bias state with identity attitude."""
        return cls(
            timestamp=timestamp,
            position_n=np.zeros(3, dtype=np.float64),
            velocity_n=np.zeros(3, dtype=np.float64),
            quaternion_nb=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64),
            accel_bias_b=np.zeros(3, dtype=np.float64),
            gyro_bias_b=np.zeros(3, dtype=np.float64),
        )

    def copy(self) -> "NominalState":
        """Return a value-equivalent state with independent arrays."""
        return NominalState(
            timestamp=self.timestamp,
            position_n=self.position_n,
            velocity_n=self.velocity_n,
            quaternion_nb=self.quaternion_nb,
            accel_bias_b=self.accel_bias_b,
            gyro_bias_b=self.gyro_bias_b,
        )


__all__ = ["NominalState"]
