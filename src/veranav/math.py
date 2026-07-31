"""Numerical rotation utilities for VeraNav.

Quaternions use Hamilton algebra and scalar-first storage ``[w, x, y, z]``.
Rotation vectors are expressed in radians.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]

_NORM_EPS: Final[float] = 1.0e-15
_SMALL_ANGLE: Final[float] = 1.0e-8
_DEFAULT_ROTATION_TOLERANCE: Final[float] = 1.0e-10


def _finite_vector(value: ArrayLike, length: int, name: str) -> FloatArray:
    """Return a finite float64 vector with an exact shape."""
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (length,):
        raise ValueError(f"{name} must have shape ({length},), got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array.copy()


def skew(vector: ArrayLike) -> FloatArray:
    """Return ``[v]_x`` such that ``[v]_x @ x == cross(v, x)``."""
    x, y, z = _finite_vector(vector, 3, "vector")
    return np.array(
        [[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]],
        dtype=np.float64,
    )


def quat_normalize(quaternion: ArrayLike) -> FloatArray:
    """Return a unit quaternion without imposing a sign convention."""
    q = _finite_vector(quaternion, 4, "quaternion")
    norm = float(np.linalg.norm(q))
    if norm <= _NORM_EPS:
        raise ValueError("quaternion norm is too small to normalize")
    return q / norm


def quat_conjugate(quaternion: ArrayLike) -> FloatArray:
    """Return the Hamilton conjugate of a scalar-first quaternion."""
    q = _finite_vector(quaternion, 4, "quaternion")
    return np.array([q[0], -q[1], -q[2], -q[3]], dtype=np.float64)


def quat_inverse(quaternion: ArrayLike) -> FloatArray:
    """Return the multiplicative inverse of a nonzero quaternion."""
    q = _finite_vector(quaternion, 4, "quaternion")
    squared_norm = float(q @ q)
    if squared_norm <= _NORM_EPS**2:
        raise ValueError("quaternion norm is too small to invert")
    return quat_conjugate(q) / squared_norm


def quat_multiply(left: ArrayLike, right: ArrayLike) -> FloatArray:
    """Return the Hamilton product ``left tensor_product right``."""
    q_left = _finite_vector(left, 4, "left")
    q_right = _finite_vector(right, 4, "right")
    w1, v1 = q_left[0], q_left[1:]
    w2, v2 = q_right[0], q_right[1:]
    scalar = w1 * w2 - float(v1 @ v2)
    vector = w1 * v2 + w2 * v1 + np.cross(v1, v2)
    return np.concatenate(([scalar], vector)).astype(np.float64, copy=False)


def quat_exp(rotation_vector: ArrayLike) -> FloatArray:
    """Map a three-dimensional rotation vector to a unit quaternion."""
    delta = _finite_vector(rotation_vector, 3, "rotation_vector")
    theta_squared = float(delta @ delta)
    theta = math.sqrt(theta_squared)
    half_theta = 0.5 * theta
    if theta < _SMALL_ANGLE:
        scale = 0.5 - theta_squared / 48.0 + theta_squared**2 / 3840.0
    else:
        scale = math.sin(half_theta) / theta
    q = np.concatenate(([math.cos(half_theta)], scale * delta))
    return quat_normalize(q)


def quat_log(quaternion: ArrayLike) -> FloatArray:
    """Map a quaternion to the shortest sign-invariant rotation vector."""
    q = quat_normalize(quaternion)
    if q[0] < 0.0:
        q = -q
    vector = q[1:]
    vector_norm = float(np.linalg.norm(vector))
    if vector_norm < _SMALL_ANGLE:
        return (2.0 * vector).astype(np.float64, copy=False)
    angle = 2.0 * math.atan2(vector_norm, float(q[0]))
    return (angle / vector_norm * vector).astype(np.float64, copy=False)


def quat_equivalent(
    first: ArrayLike,
    second: ArrayLike,
    *,
    atol: float = 1.0e-12,
) -> bool:
    """Return whether two quaternions represent the same rotation."""
    if not math.isfinite(atol) or atol < 0.0:
        raise ValueError("atol must be finite and nonnegative")
    q_first = quat_normalize(first)
    q_second = quat_normalize(second)
    direct = float(np.linalg.norm(q_first - q_second))
    antipodal = float(np.linalg.norm(q_first + q_second))
    return min(direct, antipodal) <= atol


def quat_to_rotation_matrix(quaternion: ArrayLike) -> FloatArray:
    """Convert a scalar-first quaternion to a 3 by 3 rotation matrix."""
    w, x, y, z = quat_normalize(quaternion)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float64,
    )


def rotation_matrix_to_quat(
    rotation_matrix: ArrayLike,
    *,
    atol: float = _DEFAULT_ROTATION_TOLERANCE,
) -> FloatArray:
    """Convert a proper 3 by 3 rotation matrix to a unit quaternion."""
    if not math.isfinite(atol) or atol <= 0.0:
        raise ValueError("atol must be finite and positive")
    matrix = np.asarray(rotation_matrix, dtype=np.float64)
    if matrix.shape != (3, 3):
        raise ValueError(f"rotation_matrix must have shape (3, 3), got {matrix.shape}")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("rotation_matrix must contain only finite values")
    if not np.allclose(matrix.T @ matrix, np.eye(3), rtol=0.0, atol=atol):
        raise ValueError("rotation_matrix must be orthonormal")
    determinant = float(np.linalg.det(matrix))
    if not math.isclose(determinant, 1.0, rel_tol=0.0, abs_tol=atol):
        raise ValueError("rotation_matrix determinant must be +1")

    trace = float(np.trace(matrix))
    if trace > 0.0:
        scale = 2.0 * math.sqrt(max(trace + 1.0, 0.0))
        q = np.array(
            [
                0.25 * scale,
                (matrix[2, 1] - matrix[1, 2]) / scale,
                (matrix[0, 2] - matrix[2, 0]) / scale,
                (matrix[1, 0] - matrix[0, 1]) / scale,
            ],
            dtype=np.float64,
        )
    elif matrix[0, 0] > matrix[1, 1] and matrix[0, 0] > matrix[2, 2]:
        scale = 2.0 * math.sqrt(
            max(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2], 0.0)
        )
        q = np.array(
            [
                (matrix[2, 1] - matrix[1, 2]) / scale,
                0.25 * scale,
                (matrix[0, 1] + matrix[1, 0]) / scale,
                (matrix[0, 2] + matrix[2, 0]) / scale,
            ],
            dtype=np.float64,
        )
    elif matrix[1, 1] > matrix[2, 2]:
        scale = 2.0 * math.sqrt(
            max(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2], 0.0)
        )
        q = np.array(
            [
                (matrix[0, 2] - matrix[2, 0]) / scale,
                (matrix[0, 1] + matrix[1, 0]) / scale,
                0.25 * scale,
                (matrix[1, 2] + matrix[2, 1]) / scale,
            ],
            dtype=np.float64,
        )
    else:
        scale = 2.0 * math.sqrt(
            max(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1], 0.0)
        )
        q = np.array(
            [
                (matrix[1, 0] - matrix[0, 1]) / scale,
                (matrix[0, 2] + matrix[2, 0]) / scale,
                (matrix[1, 2] + matrix[2, 1]) / scale,
                0.25 * scale,
            ],
            dtype=np.float64,
        )
    if float(np.linalg.norm(q)) <= _NORM_EPS:
        raise ValueError("rotation_matrix conversion is numerically singular")
    return quat_normalize(q)


__all__ = [
    "quat_conjugate",
    "quat_equivalent",
    "quat_exp",
    "quat_inverse",
    "quat_log",
    "quat_multiply",
    "quat_normalize",
    "quat_to_rotation_matrix",
    "rotation_matrix_to_quat",
    "skew",
]
