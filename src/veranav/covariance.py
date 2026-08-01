"""Process-noise discretization and covariance propagation for VeraNav."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.linalg import expm

from veranav.imu import ImuSample
from veranav.linearization import (
    ERROR_STATE_SIZE,
    PROCESS_NOISE_SIZE,
    continuous_error_dynamics,
)
from veranav.state import NominalState

FloatArray = NDArray[np.float64]

_DEFAULT_SYMMETRY_TOLERANCE = 1.0e-10
_DEFAULT_PSD_TOLERANCE = 1.0e-12


def _finite_nonnegative(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


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


def _validated_covariance(
    value: ArrayLike,
    size: int,
    name: str,
    *,
    symmetry_tolerance: float = _DEFAULT_SYMMETRY_TOLERANCE,
    psd_tolerance: float = _DEFAULT_PSD_TOLERANCE,
) -> FloatArray:
    matrix = _finite_matrix(value, (size, size), name)
    if not np.allclose(
        matrix,
        matrix.T,
        rtol=0.0,
        atol=symmetry_tolerance,
    ):
        raise ValueError(f"{name} must be symmetric")
    symmetric = 0.5 * (matrix + matrix.T)
    minimum_eigenvalue = float(np.min(np.linalg.eigvalsh(symmetric)))
    if minimum_eigenvalue < -psd_tolerance:
        raise ValueError(f"{name} must be positive semidefinite")
    return symmetric


def _readonly_matrix(value: ArrayLike) -> FloatArray:
    result = np.asarray(value, dtype=np.float64).copy()
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True, eq=False)
class ProcessNoise:
    """Continuous white-noise standard deviations for the ESKF.

    The first two fields are accelerometer and gyroscope noise densities.
    The final two fields are accelerometer- and gyroscope-bias random-walk
    densities. All values may be zero but must be finite and nonnegative.
    """

    accel_noise_density: float
    gyro_noise_density: float
    accel_bias_random_walk: float
    gyro_bias_random_walk: float

    def __post_init__(self) -> None:
        for name in (
            "accel_noise_density",
            "gyro_noise_density",
            "accel_bias_random_walk",
            "gyro_bias_random_walk",
        ):
            object.__setattr__(
                self,
                name,
                _finite_nonnegative(getattr(self, name), name),
            )

    def continuous_covariance(self) -> FloatArray:
        """Return the 12 by 12 continuous process-noise covariance ``Q_c``."""
        standard_deviations = np.repeat(
            np.array(
                [
                    self.accel_noise_density,
                    self.gyro_noise_density,
                    self.accel_bias_random_walk,
                    self.gyro_bias_random_walk,
                ],
                dtype=np.float64,
            ),
            3,
        )
        covariance = np.diag(standard_deviations * standard_deviations)
        covariance.setflags(write=False)
        return covariance


@dataclass(frozen=True, slots=True, eq=False)
class CovariancePropagation:
    """Immutable result of one error-covariance propagation interval."""

    transition: FloatArray
    process_covariance: FloatArray
    covariance: FloatArray

    def __post_init__(self) -> None:
        transition = _finite_matrix(
            self.transition,
            (ERROR_STATE_SIZE, ERROR_STATE_SIZE),
            "transition",
        )
        process_covariance = _validated_covariance(
            self.process_covariance,
            ERROR_STATE_SIZE,
            "process_covariance",
        )
        covariance = _validated_covariance(
            self.covariance,
            ERROR_STATE_SIZE,
            "covariance",
        )
        object.__setattr__(self, "transition", _readonly_matrix(transition))
        object.__setattr__(
            self,
            "process_covariance",
            _readonly_matrix(process_covariance),
        )
        object.__setattr__(self, "covariance", _readonly_matrix(covariance))


def van_loan_discretize(
    system: ArrayLike,
    noise_mapping: ArrayLike,
    continuous_noise_covariance: ArrayLike,
    dt: float,
) -> tuple[FloatArray, FloatArray]:
    """Discretize constant ``F``, ``G`` and ``Q_c`` using Van Loan's method."""
    system_matrix = _finite_matrix(
        system,
        (ERROR_STATE_SIZE, ERROR_STATE_SIZE),
        "system",
    )
    mapping_matrix = _finite_matrix(
        noise_mapping,
        (ERROR_STATE_SIZE, PROCESS_NOISE_SIZE),
        "noise_mapping",
    )
    continuous_covariance = _validated_covariance(
        continuous_noise_covariance,
        PROCESS_NOISE_SIZE,
        "continuous_noise_covariance",
    )
    interval = float(dt)
    if not math.isfinite(interval) or interval <= 0.0:
        raise ValueError("dt must be finite and strictly positive")

    spectral_density = (
        mapping_matrix @ continuous_covariance @ mapping_matrix.T
    )
    van_loan = np.zeros((2 * ERROR_STATE_SIZE,) * 2, dtype=np.float64)
    van_loan[0:ERROR_STATE_SIZE, 0:ERROR_STATE_SIZE] = -system_matrix
    van_loan[0:ERROR_STATE_SIZE, ERROR_STATE_SIZE:] = spectral_density
    van_loan[ERROR_STATE_SIZE:, ERROR_STATE_SIZE:] = system_matrix.T
    exponential = expm(van_loan * interval)

    upper_right = exponential[0:ERROR_STATE_SIZE, ERROR_STATE_SIZE:]
    lower_right = exponential[ERROR_STATE_SIZE:, ERROR_STATE_SIZE:]
    transition = lower_right.T
    process_covariance = transition @ upper_right
    process_covariance = 0.5 * (
        process_covariance + process_covariance.T
    )
    return transition, process_covariance


def propagate_covariance(
    covariance: ArrayLike,
    transition: ArrayLike,
    process_covariance: ArrayLike,
) -> FloatArray:
    """Apply ``P_next = Phi P Phi.T + Q_d`` and return a symmetric matrix."""
    prior = _validated_covariance(
        covariance,
        ERROR_STATE_SIZE,
        "covariance",
    )
    transition_matrix = _finite_matrix(
        transition,
        (ERROR_STATE_SIZE, ERROR_STATE_SIZE),
        "transition",
    )
    discrete_process_covariance = _validated_covariance(
        process_covariance,
        ERROR_STATE_SIZE,
        "process_covariance",
    )
    propagated = (
        transition_matrix @ prior @ transition_matrix.T
        + discrete_process_covariance
    )
    propagated = 0.5 * (propagated + propagated.T)
    minimum_eigenvalue = float(np.min(np.linalg.eigvalsh(propagated)))
    if minimum_eigenvalue < -_DEFAULT_PSD_TOLERANCE:
        raise ValueError("propagated covariance is not positive semidefinite")
    return propagated


def propagate_error_covariance(
    state: NominalState,
    sample: ImuSample,
    covariance: ArrayLike,
    process_noise: ProcessNoise,
    dt: float,
) -> CovariancePropagation:
    """Linearize, discretize and propagate the 15-state covariance once."""
    if not isinstance(process_noise, ProcessNoise):
        raise TypeError("process_noise must be a ProcessNoise")
    system, noise_mapping = continuous_error_dynamics(state, sample)
    transition, process_covariance = van_loan_discretize(
        system,
        noise_mapping,
        process_noise.continuous_covariance(),
        dt,
    )
    propagated = propagate_covariance(
        covariance,
        transition,
        process_covariance,
    )
    return CovariancePropagation(
        transition=transition,
        process_covariance=process_covariance,
        covariance=propagated,
    )


__all__ = [
    "CovariancePropagation",
    "ProcessNoise",
    "propagate_covariance",
    "propagate_error_covariance",
    "van_loan_discretize",
]
