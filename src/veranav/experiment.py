"""End-to-end synthetic ESKF experiment execution for VeraNav."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import ArrayLike, NDArray

from veranav.consistency import normalized_estimation_error_squared
from veranav.covariance import ProcessNoise
from veranav.degradation import GnssDegradation, apply_gnss_degradation
from veranav.eskf import propagate_eskf
from veranav.linearization import ERROR_STATE_SIZE
from veranav.metrics import RunMetrics, summarize_run
from veranav.simulation import CircularTrajectoryConfig, generate_circular_dataset
from veranav.state import NominalState
from veranav.update import gnss_position_update, inject_error

FloatArray = NDArray[np.float64]


def _finite_positive(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and strictly positive")
    return result


def _readonly_covariance(value: ArrayLike) -> FloatArray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.shape != (ERROR_STATE_SIZE, ERROR_STATE_SIZE):
        raise ValueError(
            f"initial_covariance must have shape ({ERROR_STATE_SIZE}, {ERROR_STATE_SIZE})"
        )
    if not np.all(np.isfinite(matrix)):
        raise ValueError("initial_covariance must contain only finite values")
    if not np.allclose(matrix, matrix.T, rtol=0.0, atol=1.0e-10):
        raise ValueError("initial_covariance must be symmetric")
    symmetric = 0.5 * (matrix + matrix.T)
    if float(np.min(np.linalg.eigvalsh(symmetric))) <= 0.0:
        raise ValueError("initial_covariance must be positive definite")
    result = symmetric.copy()
    result.setflags(write=False)
    return result


def default_initial_covariance() -> FloatArray:
    standard_deviations = np.array(
        [
            1.0,
            1.0,
            1.0,
            0.3,
            0.3,
            0.3,
            0.03,
            0.03,
            0.03,
            0.05,
            0.05,
            0.05,
            0.005,
            0.005,
            0.005,
        ],
        dtype=np.float64,
    )
    covariance = np.diag(standard_deviations * standard_deviations)
    covariance.setflags(write=False)
    return covariance


@dataclass(frozen=True, slots=True, eq=False)
class ExperimentConfig:
    """Configuration for one deterministic synthetic ESKF run."""

    trajectory: CircularTrajectoryConfig = field(default_factory=CircularTrajectoryConfig)
    degradation: GnssDegradation = field(default_factory=GnssDegradation)
    process_noise: ProcessNoise = field(
        default_factory=lambda: ProcessNoise(0.02, 0.001, 0.0005, 0.00005)
    )
    initial_covariance: FloatArray = field(default_factory=default_initial_covariance)
    initial_error_scale: float = 0.5

    def __post_init__(self) -> None:
        if not isinstance(self.trajectory, CircularTrajectoryConfig):
            raise TypeError("trajectory must be a CircularTrajectoryConfig")
        if not isinstance(self.degradation, GnssDegradation):
            raise TypeError("degradation must be a GnssDegradation")
        if not isinstance(self.process_noise, ProcessNoise):
            raise TypeError("process_noise must be a ProcessNoise")
        object.__setattr__(
            self,
            "initial_covariance",
            _readonly_covariance(self.initial_covariance),
        )
        scale = float(self.initial_error_scale)
        if not math.isfinite(scale) or scale < 0.0:
            raise ValueError("initial_error_scale must be finite and nonnegative")
        object.__setattr__(self, "initial_error_scale", scale)


@dataclass(frozen=True, slots=True, eq=False)
class ExperimentResult:
    """Immutable outputs from one synthetic ESKF experiment."""

    seed: int
    estimates: tuple[NominalState, ...]
    truth_states: tuple[NominalState, ...]
    final_covariance: FloatArray
    nis_values: tuple[float, ...]
    nees_values: tuple[float, ...]
    metrics: RunMetrics

    def __post_init__(self) -> None:
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be a nonnegative integer")
        if len(self.estimates) != len(self.truth_states) or len(self.estimates) < 2:
            raise ValueError("estimates and truth_states must have equal length >= 2")
        if len(self.nees_values) != len(self.estimates) - 1:
            raise ValueError("nees_values must contain one value per propagated sample")
        if not isinstance(self.metrics, RunMetrics):
            raise TypeError("metrics must be a RunMetrics")
        covariance = _readonly_covariance(self.final_covariance)
        object.__setattr__(self, "final_covariance", covariance)
        for sequence_name in ("nis_values", "nees_values"):
            values = tuple(float(value) for value in getattr(self, sequence_name))
            if any(not math.isfinite(value) or value < 0.0 for value in values):
                raise ValueError(f"{sequence_name} must contain finite nonnegative values")
            object.__setattr__(self, sequence_name, values)


def _initial_estimate(
    truth: NominalState,
    covariance: FloatArray,
    scale: float,
    rng: np.random.Generator,
) -> NominalState:
    if scale == 0.0:
        return truth.copy()
    standard_deviations = np.sqrt(np.diag(covariance))
    correction = rng.normal(0.0, standard_deviations * scale)
    return inject_error(truth, correction)


def run_synthetic_experiment(
    config: ExperimentConfig,
    seed: int,
) -> ExperimentResult:
    """Run one synthetic ESKF experiment with optional GNSS degradation."""
    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")

    sequence = np.random.SeedSequence(seed)
    dataset_seed, initialization_seed = sequence.spawn(2)
    dataset_seed_value = int(dataset_seed.generate_state(1, dtype=np.uint32)[0])
    dataset = generate_circular_dataset(config.trajectory, dataset_seed_value)
    initialization_rng = np.random.default_rng(initialization_seed)

    covariance = np.asarray(config.initial_covariance, dtype=np.float64).copy()
    estimate = _initial_estimate(
        dataset.truth_states[0],
        config.initial_covariance,
        config.initial_error_scale,
        initialization_rng,
    )
    estimates = [estimate]
    position_errors = []
    nis_values = []
    nees_values = []
    gnss_by_step = dataset.gnss_by_step()

    for step, sample in enumerate(dataset.imu_samples, start=1):
        propagation = propagate_eskf(
            estimate,
            covariance,
            sample,
            config.process_noise,
            config.trajectory.imu_dt,
        )
        estimate = propagation.state
        covariance = np.asarray(propagation.covariance, dtype=np.float64).copy()

        measurement = gnss_by_step.get(step)
        if measurement is not None:
            degraded = apply_gnss_degradation(measurement, config.degradation)
            if degraded is not None:
                update = gnss_position_update(estimate, covariance, degraded)
                estimate = update.state
                covariance = np.asarray(update.covariance, dtype=np.float64).copy()
                nis_values.append(update.nis)

        truth = dataset.truth_states[step]
        position_errors.append(estimate.position_n - truth.position_n)
        nees_values.append(
            normalized_estimation_error_squared(estimate, truth, covariance)
        )
        estimates.append(estimate)

    metrics = summarize_run(
        np.asarray(position_errors, dtype=np.float64),
        nis_values,
        nees_values,
    )
    return ExperimentResult(
        seed=seed,
        estimates=tuple(estimates),
        truth_states=dataset.truth_states,
        final_covariance=covariance,
        nis_values=tuple(nis_values),
        nees_values=tuple(nees_values),
        metrics=metrics,
    )


__all__ = [
    "ExperimentConfig",
    "ExperimentResult",
    "default_initial_covariance",
    "run_synthetic_experiment",
]
