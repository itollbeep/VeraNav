"""Composable ESKF propagation and GNSS correction steps for VeraNav."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from veranav.covariance import (
    CovariancePropagation,
    ProcessNoise,
    propagate_error_covariance,
)
from veranav.imu import ImuSample, propagate_nominal
from veranav.linearization import ERROR_STATE_SIZE
from veranav.measurement import GnssPositionMeasurement
from veranav.state import NominalState
from veranav.update import GnssPositionUpdate, gnss_position_update

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True, eq=False)
class EskfPropagation:
    """Nominal and covariance results for one IMU propagation interval."""

    state: NominalState
    covariance: FloatArray
    transition: FloatArray
    process_covariance: FloatArray

    def __post_init__(self) -> None:
        if not isinstance(self.state, NominalState):
            raise TypeError("state must be a NominalState")
        for name in ("covariance", "transition", "process_covariance"):
            matrix = np.asarray(getattr(self, name), dtype=np.float64)
            if matrix.shape != (ERROR_STATE_SIZE, ERROR_STATE_SIZE):
                raise ValueError(
                    f"{name} must have shape "
                    f"({ERROR_STATE_SIZE}, {ERROR_STATE_SIZE}), got {matrix.shape}"
                )
            if not np.all(np.isfinite(matrix)):
                raise ValueError(f"{name} must contain only finite values")
            result = matrix.copy()
            result.setflags(write=False)
            object.__setattr__(self, name, result)


@dataclass(frozen=True, slots=True, eq=False)
class EskfPositionCycle:
    """Prediction and GNSS position correction for one complete ESKF cycle."""

    propagation: EskfPropagation
    update: GnssPositionUpdate

    def __post_init__(self) -> None:
        if not isinstance(self.propagation, EskfPropagation):
            raise TypeError("propagation must be an EskfPropagation")
        if not isinstance(self.update, GnssPositionUpdate):
            raise TypeError("update must be a GnssPositionUpdate")


def propagate_eskf(
    state: NominalState,
    covariance: ArrayLike,
    sample: ImuSample,
    process_noise: ProcessNoise,
    dt: float,
) -> EskfPropagation:
    """Propagate nominal state and error covariance over one IMU interval."""
    covariance_result: CovariancePropagation = propagate_error_covariance(
        state,
        sample,
        covariance,
        process_noise,
        dt,
    )
    propagated_state = propagate_nominal(state, sample, dt)
    return EskfPropagation(
        state=propagated_state,
        covariance=covariance_result.covariance,
        transition=covariance_result.transition,
        process_covariance=covariance_result.process_covariance,
    )


def propagate_and_update_gnss_position(
    state: NominalState,
    covariance: ArrayLike,
    sample: ImuSample,
    process_noise: ProcessNoise,
    dt: float,
    measurement: GnssPositionMeasurement,
) -> EskfPositionCycle:
    """Run one IMU prediction followed by one GNSS position correction."""
    propagation = propagate_eskf(
        state,
        covariance,
        sample,
        process_noise,
        dt,
    )
    update = gnss_position_update(
        propagation.state,
        propagation.covariance,
        measurement,
    )
    return EskfPositionCycle(propagation=propagation, update=update)


__all__ = [
    "EskfPositionCycle",
    "EskfPropagation",
    "propagate_and_update_gnss_position",
    "propagate_eskf",
]
