from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]

WGS84_SEMI_MAJOR_AXIS_M = 6378137.0
WGS84_FLATTENING = 1.0 / 298.257223563
WGS84_ECCENTRICITY_SQUARED = WGS84_FLATTENING * (2.0 - WGS84_FLATTENING)


def _finite_array(value: ArrayLike, name: str) -> FloatArray:
    array = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def geodetic_to_ecef(
    latitude_deg: ArrayLike,
    longitude_deg: ArrayLike,
    height_m: ArrayLike,
) -> FloatArray:
    """Convert WGS84 geodetic coordinates to ECEF metres."""
    latitude, longitude, height = np.broadcast_arrays(
        _finite_array(latitude_deg, "latitude_deg"),
        _finite_array(longitude_deg, "longitude_deg"),
        _finite_array(height_m, "height_m"),
    )
    if np.any((latitude < -90.0) | (latitude > 90.0)):
        raise ValueError("latitude_deg must be within [-90, 90]")
    if np.any((longitude < -180.0) | (longitude > 180.0)):
        raise ValueError("longitude_deg must be within [-180, 180]")

    latitude_rad = np.deg2rad(latitude)
    longitude_rad = np.deg2rad(longitude)
    sin_latitude = np.sin(latitude_rad)
    cos_latitude = np.cos(latitude_rad)
    sin_longitude = np.sin(longitude_rad)
    cos_longitude = np.cos(longitude_rad)

    prime_vertical_radius = WGS84_SEMI_MAJOR_AXIS_M / np.sqrt(
        1.0 - WGS84_ECCENTRICITY_SQUARED * sin_latitude * sin_latitude
    )
    x = (prime_vertical_radius + height) * cos_latitude * cos_longitude
    y = (prime_vertical_radius + height) * cos_latitude * sin_longitude
    z = (
        prime_vertical_radius * (1.0 - WGS84_ECCENTRICITY_SQUARED) + height
    ) * sin_latitude
    return np.stack((x, y, z), axis=-1)


def ecef_to_local_ned(
    ecef_m: ArrayLike,
    anchor_latitude_deg: float,
    anchor_longitude_deg: float,
    anchor_height_m: float,
) -> FloatArray:
    """Express ECEF positions in a WGS84 anchor-centred NED frame."""
    ecef = _finite_array(ecef_m, "ecef_m")
    if ecef.ndim < 1 or ecef.shape[-1] != 3:
        raise ValueError("ecef_m must have final dimension three")

    anchor_latitude = float(anchor_latitude_deg)
    anchor_longitude = float(anchor_longitude_deg)
    anchor_height = float(anchor_height_m)
    if not all(math.isfinite(value) for value in (
        anchor_latitude,
        anchor_longitude,
        anchor_height,
    )):
        raise ValueError("anchor coordinates must be finite")
    if not -90.0 <= anchor_latitude <= 90.0:
        raise ValueError("anchor_latitude_deg must be within [-90, 90]")
    if not -180.0 <= anchor_longitude <= 180.0:
        raise ValueError("anchor_longitude_deg must be within [-180, 180]")

    anchor_ecef = geodetic_to_ecef(
        anchor_latitude,
        anchor_longitude,
        anchor_height,
    )
    latitude_rad = math.radians(anchor_latitude)
    longitude_rad = math.radians(anchor_longitude)
    sin_latitude = math.sin(latitude_rad)
    cos_latitude = math.cos(latitude_rad)
    sin_longitude = math.sin(longitude_rad)
    cos_longitude = math.cos(longitude_rad)

    ecef_to_ned = np.array(
        [
            [
                -sin_latitude * cos_longitude,
                -sin_latitude * sin_longitude,
                cos_latitude,
            ],
            [-sin_longitude, cos_longitude, 0.0],
            [
                -cos_latitude * cos_longitude,
                -cos_latitude * sin_longitude,
                -sin_latitude,
            ],
        ],
        dtype=np.float64,
    )
    return (ecef - anchor_ecef) @ ecef_to_ned.T


def geodetic_to_local_ned(
    geodetic_deg_m: ArrayLike,
    anchor_latitude_deg: float,
    anchor_longitude_deg: float,
    anchor_height_m: float,
) -> FloatArray:
    """Convert latitude, longitude and height rows to local NED metres."""
    geodetic = _finite_array(geodetic_deg_m, "geodetic_deg_m")
    if geodetic.ndim != 2 or geodetic.shape[1] != 3 or geodetic.shape[0] < 1:
        raise ValueError("geodetic_deg_m must have shape (n, 3)")
    ecef = geodetic_to_ecef(
        geodetic[:, 0],
        geodetic[:, 1],
        geodetic[:, 2],
    )
    return ecef_to_local_ned(
        ecef,
        anchor_latitude_deg,
        anchor_longitude_deg,
        anchor_height_m,
    )
