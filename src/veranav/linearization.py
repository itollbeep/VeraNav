"""Continuous-time error-state linearization for VeraNav V0.1."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from veranav.imu import ImuSample
from veranav.math import quat_to_rotation_matrix, skew
from veranav.state import NominalState

FloatArray = NDArray[np.float64]

ERROR_STATE_SIZE = 15
PROCESS_NOISE_SIZE = 12
_TIMESTAMP_ATOL = 1.0e-12


def continuous_error_dynamics(
    state: NominalState,
    sample: ImuSample,
) -> tuple[FloatArray, FloatArray]:
    """Return continuous-time ``F`` and ``G`` for the right-error ESKF.

    Error-state ordering is ``[dp_n, dv_n, dtheta_b, db_a, db_g]``.
    Process-noise ordering is ``[n_a, n_g, n_ba, n_bg]``.
    """
    if not isinstance(state, NominalState):
        raise TypeError("state must be a NominalState")
    if not isinstance(sample, ImuSample):
        raise TypeError("sample must be an ImuSample")
    if not math.isclose(
        sample.timestamp,
        state.timestamp,
        rel_tol=0.0,
        abs_tol=_TIMESTAMP_ATOL,
    ):
        raise ValueError("sample timestamp must match state timestamp")

    corrected_force_b = sample.specific_force_b - state.accel_bias_b
    corrected_rate_b = sample.angular_rate_b - state.gyro_bias_b
    rotation_nb = quat_to_rotation_matrix(state.quaternion_nb)
    identity = np.eye(3, dtype=np.float64)

    system = np.zeros(
        (ERROR_STATE_SIZE, ERROR_STATE_SIZE),
        dtype=np.float64,
    )
    system[0:3, 3:6] = identity
    system[3:6, 6:9] = -rotation_nb @ skew(corrected_force_b)
    system[3:6, 9:12] = -rotation_nb
    system[6:9, 6:9] = -skew(corrected_rate_b)
    system[6:9, 12:15] = -identity

    noise_mapping = np.zeros(
        (ERROR_STATE_SIZE, PROCESS_NOISE_SIZE),
        dtype=np.float64,
    )
    noise_mapping[3:6, 0:3] = -rotation_nb
    noise_mapping[6:9, 3:6] = -identity
    noise_mapping[9:12, 6:9] = identity
    noise_mapping[12:15, 9:12] = identity

    return system, noise_mapping


__all__ = [
    "ERROR_STATE_SIZE",
    "PROCESS_NOISE_SIZE",
    "continuous_error_dynamics",
]
