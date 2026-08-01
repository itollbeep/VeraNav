"""Deterministic synthetic trajectory and sensor generation for VeraNav."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import ArrayLike, NDArray

from veranav.imu import ImuSample, STANDARD_GRAVITY_MPS2
from veranav.math import quat_exp
from veranav.measurement import GnssPositionMeasurement
from veranav.state import NominalState

FloatArray = NDArray[np.float64]
_TIME_TOLERANCE = 1.0e-10


def _finite_positive(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and strictly positive")
    return result


def _finite_nonnegative(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def _readonly_vector(value: ArrayLike, name: str) -> FloatArray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values")
    result = vector.copy()
    result.setflags(write=False)
    return result


def _integer_ratio(numerator: float, denominator: float, name: str) -> int:
    ratio = numerator / denominator
    rounded = int(round(ratio))
    if rounded < 1 or not math.isclose(
        ratio,
        rounded,
        rel_tol=0.0,
        abs_tol=_TIME_TOLERANCE,
    ):
        raise ValueError(f"{name} must be an integer multiple of imu_dt")
    return rounded


@dataclass(frozen=True, slots=True, eq=False)
class CircularTrajectoryConfig:
    """Configuration for a level constant-speed circular trajectory."""

    duration_s: float = 12.0
    imu_dt: float = 0.02
    gnss_dt: float = 0.2
    radius_m: float = 30.0
    speed_mps: float = 6.0
    accel_noise_std: float = 0.02
    gyro_noise_std: float = 0.001
    gnss_position_std_m: float = 0.8
    accel_bias_b: FloatArray = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )
    gyro_bias_b: FloatArray = field(
        default_factory=lambda: np.zeros(3, dtype=np.float64)
    )

    def __post_init__(self) -> None:
        for name in (
            "duration_s",
            "imu_dt",
            "gnss_dt",
            "radius_m",
            "speed_mps",
            "gnss_position_std_m",
        ):
            object.__setattr__(self, name, _finite_positive(getattr(self, name), name))
        for name in ("accel_noise_std", "gyro_noise_std"):
            object.__setattr__(self, name, _finite_nonnegative(getattr(self, name), name))
        object.__setattr__(
            self,
            "accel_bias_b",
            _readonly_vector(self.accel_bias_b, "accel_bias_b"),
        )
        object.__setattr__(
            self,
            "gyro_bias_b",
            _readonly_vector(self.gyro_bias_b, "gyro_bias_b"),
        )
        _integer_ratio(self.duration_s, self.imu_dt, "duration_s")
        _integer_ratio(self.gnss_dt, self.imu_dt, "gnss_dt")

    @property
    def angular_rate_rad_s(self) -> float:
        return self.speed_mps / self.radius_m

    @property
    def imu_steps(self) -> int:
        return _integer_ratio(self.duration_s, self.imu_dt, "duration_s")

    @property
    def gnss_stride(self) -> int:
        return _integer_ratio(self.gnss_dt, self.imu_dt, "gnss_dt")


@dataclass(frozen=True, slots=True, eq=False)
class SyntheticDataset:
    """Truth states, IMU samples and time-aligned GNSS measurements."""

    truth_states: tuple[NominalState, ...]
    imu_samples: tuple[ImuSample, ...]
    gnss_measurements: tuple[GnssPositionMeasurement, ...]
    gnss_step_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.truth_states) != len(self.imu_samples) + 1:
            raise ValueError("truth_states must contain one more element than imu_samples")
        if len(self.gnss_measurements) != len(self.gnss_step_indices):
            raise ValueError("GNSS measurements and step indices must have equal length")
        previous = 0
        for index, measurement in zip(
            self.gnss_step_indices,
            self.gnss_measurements,
            strict=True,
        ):
            if not isinstance(index, int) or index <= previous or index >= len(self.truth_states):
                raise ValueError("gnss_step_indices must be strictly increasing valid indices")
            if not isinstance(measurement, GnssPositionMeasurement):
                raise TypeError("all GNSS entries must be GnssPositionMeasurement objects")
            if not math.isclose(
                measurement.timestamp,
                self.truth_states[index].timestamp,
                rel_tol=0.0,
                abs_tol=_TIME_TOLERANCE,
            ):
                raise ValueError("GNSS timestamp must match its truth-state index")
            previous = index

    def gnss_by_step(self) -> dict[int, GnssPositionMeasurement]:
        return dict(zip(self.gnss_step_indices, self.gnss_measurements, strict=True))


def circular_truth_state(
    config: CircularTrajectoryConfig,
    timestamp: float,
) -> NominalState:
    """Return the analytic truth state at one trajectory timestamp."""
    if not isinstance(config, CircularTrajectoryConfig):
        raise TypeError("config must be a CircularTrajectoryConfig")
    time = float(timestamp)
    if not math.isfinite(time) or time < 0.0 or time > config.duration_s + _TIME_TOLERANCE:
        raise ValueError("timestamp must be finite and within the configured duration")

    omega = config.angular_rate_rad_s
    yaw = omega * time
    sine = math.sin(yaw)
    cosine = math.cos(yaw)
    position = np.array(
        [
            config.radius_m * sine,
            config.radius_m * (1.0 - cosine),
            0.0,
        ],
        dtype=np.float64,
    )
    velocity = np.array(
        [
            config.speed_mps * cosine,
            config.speed_mps * sine,
            0.0,
        ],
        dtype=np.float64,
    )
    return NominalState(
        timestamp=time,
        position_n=position,
        velocity_n=velocity,
        quaternion_nb=quat_exp([0.0, 0.0, yaw]),
        accel_bias_b=config.accel_bias_b,
        gyro_bias_b=config.gyro_bias_b,
    )


def generate_circular_dataset(
    config: CircularTrajectoryConfig,
    seed: int,
) -> SyntheticDataset:
    """Generate a deterministic circular truth trajectory and noisy sensors."""
    if not isinstance(config, CircularTrajectoryConfig):
        raise TypeError("config must be a CircularTrajectoryConfig")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")

    seed_sequence = np.random.SeedSequence(seed)
    imu_seed, gnss_seed = seed_sequence.spawn(2)
    imu_rng = np.random.default_rng(imu_seed)
    gnss_rng = np.random.default_rng(gnss_seed)

    truth_states = tuple(
        circular_truth_state(config, step * config.imu_dt)
        for step in range(config.imu_steps + 1)
    )

    omega = config.angular_rate_rad_s
    ideal_specific_force = np.array(
        [
            0.0,
            config.speed_mps * omega,
            -STANDARD_GRAVITY_MPS2,
        ],
        dtype=np.float64,
    )
    ideal_angular_rate = np.array([0.0, 0.0, omega], dtype=np.float64)

    imu_samples = []
    for state in truth_states[:-1]:
        force = (
            ideal_specific_force
            + config.accel_bias_b
            + imu_rng.normal(0.0, config.accel_noise_std, size=3)
        )
        rate = (
            ideal_angular_rate
            + config.gyro_bias_b
            + imu_rng.normal(0.0, config.gyro_noise_std, size=3)
        )
        imu_samples.append(
            ImuSample(
                timestamp=state.timestamp,
                specific_force_b=force,
                angular_rate_b=rate,
            )
        )

    covariance = np.eye(3, dtype=np.float64) * config.gnss_position_std_m**2
    gnss_indices = tuple(
        range(config.gnss_stride, config.imu_steps + 1, config.gnss_stride)
    )
    gnss_measurements = tuple(
        GnssPositionMeasurement(
            timestamp=truth_states[index].timestamp,
            position_n=(
                truth_states[index].position_n
                + gnss_rng.normal(0.0, config.gnss_position_std_m, size=3)
            ),
            covariance_n=covariance,
        )
        for index in gnss_indices
    )

    return SyntheticDataset(
        truth_states=truth_states,
        imu_samples=tuple(imu_samples),
        gnss_measurements=gnss_measurements,
        gnss_step_indices=gnss_indices,
    )


__all__ = [
    "CircularTrajectoryConfig",
    "SyntheticDataset",
    "circular_truth_state",
    "generate_circular_dataset",
]
