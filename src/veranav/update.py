"""GNSS position update, error injection and reset for VeraNav."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from veranav.linearization import ERROR_STATE_SIZE
from veranav.math import quat_exp, quat_multiply, quat_normalize, skew
from veranav.measurement import GnssPositionMeasurement
from veranav.state import NominalState

FloatArray = NDArray[np.float64]

MEASUREMENT_SIZE = 3
_TIMESTAMP_ATOL = 1.0e-12
_DEFAULT_SYMMETRY_TOLERANCE = 1.0e-10
_DEFAULT_PSD_TOLERANCE = 1.0e-10


def _finite_vector(value: ArrayLike, length: int, name: str) -> FloatArray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.shape != (length,):
        raise ValueError(f"{name} must have shape ({length},), got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values")
    return vector.copy()


def _finite_matrix(
    value: ArrayLike,
    shape: tuple[int, int],
    name: str,
) -> FloatArray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, got {matrix.shape}")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")
    return matrix.copy()


def _validated_covariance(value: ArrayLike, name: str) -> FloatArray:
    matrix = _finite_matrix(
        value,
        (ERROR_STATE_SIZE, ERROR_STATE_SIZE),
        name,
    )
    if not np.allclose(
        matrix,
        matrix.T,
        rtol=0.0,
        atol=_DEFAULT_SYMMETRY_TOLERANCE,
    ):
        raise ValueError(f"{name} must be symmetric")
    symmetric = 0.5 * (matrix + matrix.T)
    if float(np.min(np.linalg.eigvalsh(symmetric))) < -_DEFAULT_PSD_TOLERANCE:
        raise ValueError(f"{name} must be positive semidefinite")
    return symmetric


def _readonly_vector(value: ArrayLike, length: int, name: str) -> FloatArray:
    result = _finite_vector(value, length, name)
    result.setflags(write=False)
    return result


def _readonly_matrix(
    value: ArrayLike,
    shape: tuple[int, int],
    name: str,
) -> FloatArray:
    result = _finite_matrix(value, shape, name)
    result.setflags(write=False)
    return result


def position_measurement_matrix() -> FloatArray:
    """Return the 3 by 15 GNSS position measurement Jacobian."""
    measurement_matrix = np.zeros(
        (MEASUREMENT_SIZE, ERROR_STATE_SIZE),
        dtype=np.float64,
    )
    measurement_matrix[:, 0:3] = np.eye(3, dtype=np.float64)
    measurement_matrix.setflags(write=False)
    return measurement_matrix


def inject_error(
    state: NominalState,
    correction: ArrayLike,
) -> NominalState:
    """Inject a 15-dimensional right-error correction into a nominal state."""
    if not isinstance(state, NominalState):
        raise TypeError("state must be a NominalState")
    delta = _finite_vector(correction, ERROR_STATE_SIZE, "correction")
    attitude_increment = quat_exp(delta[6:9])
    corrected_quaternion = quat_normalize(
        quat_multiply(state.quaternion_nb, attitude_increment)
    )
    return NominalState(
        timestamp=state.timestamp,
        position_n=state.position_n + delta[0:3],
        velocity_n=state.velocity_n + delta[3:6],
        quaternion_nb=corrected_quaternion,
        accel_bias_b=state.accel_bias_b + delta[9:12],
        gyro_bias_b=state.gyro_bias_b + delta[12:15],
    )


def reset_jacobian(attitude_correction_b: ArrayLike) -> FloatArray:
    """Return the first-order covariance reset Jacobian after injection."""
    attitude = _finite_vector(
        attitude_correction_b,
        3,
        "attitude_correction_b",
    )
    reset = np.eye(ERROR_STATE_SIZE, dtype=np.float64)
    reset[6:9, 6:9] = np.eye(3) - 0.5 * skew(attitude)
    reset.setflags(write=False)
    return reset


def reset_covariance(
    covariance: ArrayLike,
    attitude_correction_b: ArrayLike,
) -> FloatArray:
    """Apply the first-order attitude reset to a posterior covariance."""
    posterior = _validated_covariance(covariance, "covariance")
    reset = reset_jacobian(attitude_correction_b)
    result = reset @ posterior @ reset.T
    result = 0.5 * (result + result.T)
    if float(np.min(np.linalg.eigvalsh(result))) < -_DEFAULT_PSD_TOLERANCE:
        raise ValueError("reset covariance is not positive semidefinite")
    return result


@dataclass(frozen=True, slots=True, eq=False)
class GnssPositionUpdate:
    """Immutable result of one GNSS position correction."""

    state: NominalState
    covariance: FloatArray
    innovation: FloatArray
    innovation_covariance: FloatArray
    gain: FloatArray
    correction: FloatArray
    nis: float

    def __post_init__(self) -> None:
        if not isinstance(self.state, NominalState):
            raise TypeError("state must be a NominalState")
        covariance = _validated_covariance(self.covariance, "covariance")
        nis = float(self.nis)
        if not math.isfinite(nis) or nis < 0.0:
            raise ValueError("nis must be finite and nonnegative")
        object.__setattr__(
            self,
            "covariance",
            _readonly_matrix(
                covariance,
                (ERROR_STATE_SIZE, ERROR_STATE_SIZE),
                "covariance",
            ),
        )
        object.__setattr__(
            self,
            "innovation",
            _readonly_vector(
                self.innovation,
                MEASUREMENT_SIZE,
                "innovation",
            ),
        )
        object.__setattr__(
            self,
            "innovation_covariance",
            _readonly_matrix(
                self.innovation_covariance,
                (MEASUREMENT_SIZE, MEASUREMENT_SIZE),
                "innovation_covariance",
            ),
        )
        object.__setattr__(
            self,
            "gain",
            _readonly_matrix(
                self.gain,
                (ERROR_STATE_SIZE, MEASUREMENT_SIZE),
                "gain",
            ),
        )
        object.__setattr__(
            self,
            "correction",
            _readonly_vector(
                self.correction,
                ERROR_STATE_SIZE,
                "correction",
            ),
        )
        object.__setattr__(self, "nis", nis)


def gnss_position_update(
    state: NominalState,
    covariance: ArrayLike,
    measurement: GnssPositionMeasurement,
) -> GnssPositionUpdate:
    """Apply a linear GNSS position update using Joseph covariance form."""
    if not isinstance(state, NominalState):
        raise TypeError("state must be a NominalState")
    if not isinstance(measurement, GnssPositionMeasurement):
        raise TypeError("measurement must be a GnssPositionMeasurement")
    if not math.isclose(
        measurement.timestamp,
        state.timestamp,
        rel_tol=0.0,
        abs_tol=_TIMESTAMP_ATOL,
    ):
        raise ValueError("measurement timestamp must match state timestamp")

    prior = _validated_covariance(covariance, "covariance")
    measurement_matrix = position_measurement_matrix()
    innovation = measurement.position_n - state.position_n
    innovation_covariance = (
        measurement_matrix @ prior @ measurement_matrix.T
        + measurement.covariance_n
    )
    innovation_covariance = 0.5 * (
        innovation_covariance + innovation_covariance.T
    )

    try:
        solved_projection = np.linalg.solve(
            innovation_covariance,
            measurement_matrix @ prior,
        )
        solved_innovation = np.linalg.solve(
            innovation_covariance,
            innovation,
        )
    except np.linalg.LinAlgError as error:
        raise ValueError("innovation covariance must be nonsingular") from error

    gain = solved_projection.T
    correction = gain @ innovation
    nis = float(innovation @ solved_innovation)

    identity = np.eye(ERROR_STATE_SIZE, dtype=np.float64)
    residual_mapping = identity - gain @ measurement_matrix
    posterior = (
        residual_mapping @ prior @ residual_mapping.T
        + gain @ measurement.covariance_n @ gain.T
    )
    posterior = 0.5 * (posterior + posterior.T)

    corrected_state = inject_error(state, correction)
    corrected_covariance = reset_covariance(posterior, correction[6:9])

    return GnssPositionUpdate(
        state=corrected_state,
        covariance=corrected_covariance,
        innovation=innovation,
        innovation_covariance=innovation_covariance,
        gain=gain,
        correction=correction,
        nis=nis,
    )


__all__ = [
    "GnssPositionUpdate",
    "MEASUREMENT_SIZE",
    "gnss_position_update",
    "inject_error",
    "position_measurement_matrix",
    "reset_covariance",
    "reset_jacobian",
]
