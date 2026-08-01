"""Statistical consistency metrics for VeraNav state estimates."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray

from veranav.linearization import ERROR_STATE_SIZE
from veranav.math import quat_inverse, quat_log, quat_multiply
from veranav.state import NominalState

FloatArray = NDArray[np.float64]

_TIMESTAMP_ATOL = 1.0e-12
_DEFAULT_SYMMETRY_TOLERANCE = 1.0e-10


def state_error_vector(
    estimate: NominalState,
    truth: NominalState,
) -> FloatArray:
    """Return the 15-state right error satisfying truth = estimate plus error."""
    if not isinstance(estimate, NominalState):
        raise TypeError("estimate must be a NominalState")
    if not isinstance(truth, NominalState):
        raise TypeError("truth must be a NominalState")
    if not math.isclose(
        estimate.timestamp,
        truth.timestamp,
        rel_tol=0.0,
        abs_tol=_TIMESTAMP_ATOL,
    ):
        raise ValueError("estimate and truth timestamps must match")

    attitude_error = quat_log(
        quat_multiply(
            quat_inverse(estimate.quaternion_nb),
            truth.quaternion_nb,
        )
    )
    return np.concatenate(
        (
            truth.position_n - estimate.position_n,
            truth.velocity_n - estimate.velocity_n,
            attitude_error,
            truth.accel_bias_b - estimate.accel_bias_b,
            truth.gyro_bias_b - estimate.gyro_bias_b,
        )
    ).astype(np.float64, copy=False)


def normalized_estimation_error_squared(
    estimate: NominalState,
    truth: NominalState,
    covariance: ArrayLike,
) -> float:
    """Return the 15-degree-of-freedom NEES statistic."""
    matrix = np.asarray(covariance, dtype=np.float64)
    if matrix.shape != (ERROR_STATE_SIZE, ERROR_STATE_SIZE):
        raise ValueError(
            "covariance must have shape "
            f"({ERROR_STATE_SIZE}, {ERROR_STATE_SIZE}), got {matrix.shape}"
        )
    if not np.all(np.isfinite(matrix)):
        raise ValueError("covariance must contain only finite values")
    if not np.allclose(
        matrix,
        matrix.T,
        rtol=0.0,
        atol=_DEFAULT_SYMMETRY_TOLERANCE,
    ):
        raise ValueError("covariance must be symmetric")
    symmetric = 0.5 * (matrix + matrix.T)
    if float(np.min(np.linalg.eigvalsh(symmetric))) <= 0.0:
        raise ValueError("covariance must be positive definite for NEES")

    error = state_error_vector(estimate, truth)
    try:
        solved = np.linalg.solve(symmetric, error)
    except np.linalg.LinAlgError as exception:
        raise ValueError("covariance must be nonsingular for NEES") from exception
    result = float(error @ solved)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError("computed NEES must be finite and nonnegative")
    return result


nees = normalized_estimation_error_squared


__all__ = [
    "nees",
    "normalized_estimation_error_squared",
    "state_error_vector",
]
