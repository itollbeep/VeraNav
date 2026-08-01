"""Validated navigation measurements for VeraNav V0.1."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]

_DEFAULT_SYMMETRY_TOLERANCE = 1.0e-10


def _readonly_vector(value: ArrayLike, length: int, name: str) -> FloatArray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (length,):
        raise ValueError(f"{name} must have shape ({length},), got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    result = array.copy()
    result.setflags(write=False)
    return result


def _readonly_positive_definite_matrix(
    value: ArrayLike,
    size: int,
    name: str,
) -> FloatArray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.shape != (size, size):
        raise ValueError(
            f"{name} must have shape ({size}, {size}), got {matrix.shape}"
        )
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")
    if not np.allclose(
        matrix,
        matrix.T,
        rtol=0.0,
        atol=_DEFAULT_SYMMETRY_TOLERANCE,
    ):
        raise ValueError(f"{name} must be symmetric")
    symmetric = 0.5 * (matrix + matrix.T)
    if float(np.min(np.linalg.eigvalsh(symmetric))) <= 0.0:
        raise ValueError(f"{name} must be positive definite")
    result = symmetric.copy()
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True, eq=False)
class GnssPositionMeasurement:
    """Three-dimensional GNSS position measurement in the NED frame."""

    timestamp: float
    position_n: FloatArray
    covariance_n: FloatArray

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
            "covariance_n",
            _readonly_positive_definite_matrix(
                self.covariance_n,
                3,
                "covariance_n",
            ),
        )


__all__ = ["GnssPositionMeasurement"]
