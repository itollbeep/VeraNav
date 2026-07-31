"""IMU sample validation and nominal-state propagation for VeraNav V0.1."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import ArrayLike, NDArray

from veranav.math import (
    quat_exp,
    quat_multiply,
    quat_normalize,
    quat_to_rotation_matrix,
)
from veranav.state import NominalState

FloatArray = NDArray[np.float64]

STANDARD_GRAVITY_MPS2: Final[float] = 9.80665
_TIMESTAMP_ATOL: Final[float] = 1.0e-12


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


@dataclass(frozen=True, slots=True, eq=False)
class ImuSample:
    """Body-frame IMU measurement held from ``timestamp`` for one interval."""

    timestamp: float
    specific_force_b: FloatArray
    angular_rate_b: FloatArray

    def __post_init__(self) -> None:
        timestamp = float(self.timestamp)
        if not math.isfinite(timestamp):
            raise ValueError("timestamp must be finite")
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(
            self,
            "specific_force_b",
            _readonly_vector(self.specific_force_b, 3, "specific_force_b"),
        )
        object.__setattr__(
            self,
            "angular_rate_b",
            _readonly_vector(self.angular_rate_b, 3, "angular_rate_b"),
        )


def propagate_nominal(
    state: NominalState,
    sample: ImuSample,
    dt: float,
    *,
    gravity_magnitude: float = STANDARD_GRAVITY_MPS2,
) -> NominalState:
    """Propagate a nominal state over one zero-order-held IMU interval.

    The sample timestamp must match the state timestamp. The returned timestamp
    is exactly ``state.timestamp + dt``. Translation uses the midpoint attitude
    defined in ``docs/eskf_model.md``.
    """
    if not isinstance(state, NominalState):
        raise TypeError("state must be a NominalState")
    if not isinstance(sample, ImuSample):
        raise TypeError("sample must be an ImuSample")

    interval = float(dt)
    if not math.isfinite(interval) or interval <= 0.0:
        raise ValueError("dt must be finite and strictly positive")

    gravity = float(gravity_magnitude)
    if not math.isfinite(gravity) or gravity <= 0.0:
        raise ValueError("gravity_magnitude must be finite and strictly positive")

    if not math.isclose(
        sample.timestamp,
        state.timestamp,
        rel_tol=0.0,
        abs_tol=_TIMESTAMP_ATOL,
    ):
        raise ValueError("sample timestamp must match state timestamp")

    next_timestamp = state.timestamp + interval
    if not math.isfinite(next_timestamp):
        raise ValueError("propagated timestamp must be finite")
    if next_timestamp <= state.timestamp:
        raise ValueError(
            "propagated timestamp must be strictly greater than state timestamp"
        )

    corrected_force_b = sample.specific_force_b - state.accel_bias_b
    corrected_rate_b = sample.angular_rate_b - state.gyro_bias_b

    half_increment = quat_exp(0.5 * corrected_rate_b * interval)
    midpoint_quaternion = quat_normalize(
        quat_multiply(state.quaternion_nb, half_increment)
    )
    midpoint_rotation = quat_to_rotation_matrix(midpoint_quaternion)

    gravity_n = np.array([0.0, 0.0, gravity], dtype=np.float64)
    acceleration_mid_n = midpoint_rotation @ corrected_force_b + gravity_n

    next_position_n = (
        state.position_n
        + state.velocity_n * interval
        + 0.5 * acceleration_mid_n * interval * interval
    )
    next_velocity_n = state.velocity_n + acceleration_mid_n * interval

    full_increment = quat_exp(corrected_rate_b * interval)
    next_quaternion_nb = quat_normalize(
        quat_multiply(state.quaternion_nb, full_increment)
    )

    return NominalState(
        timestamp=next_timestamp,
        position_n=next_position_n,
        velocity_n=next_velocity_n,
        quaternion_nb=next_quaternion_nb,
        accel_bias_b=state.accel_bias_b,
        gyro_bias_b=state.gyro_bias_b,
    )


__all__ = ["ImuSample", "STANDARD_GRAVITY_MPS2", "propagate_nominal"]
