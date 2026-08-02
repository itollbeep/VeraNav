"""Validation model for OpenVINS IMU-noise degradation evidence."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
_EXPECTED_SCENARIOS = (
    "baseline",
    "white-2x",
    "white-5x",
    "white-10x",
    "randomwalk-2x",
    "randomwalk-5x",
    "randomwalk-10x",
    "all-2x",
    "all-5x",
    "all-10x",
)
_HEX = frozenset("0123456789abcdef")


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _sha256(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")

    normalized = value.strip().lower()
    if (
        len(normalized) != 64
        or any(character not in _HEX for character in normalized)
    ):
        raise ValueError(f"{name} must be a SHA256 digest")

    return normalized


def _finite_nonnegative(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number


@dataclass(frozen=True, slots=True)
class ImuNoiseScenarioResult:
    """Validated performance and consistency metrics for one scenario."""

    scenario: str
    white_noise_scale: float
    random_walk_scale: float
    sample_count: int
    position_rmse_m: float
    position_mean_m: float
    position_p95_m: float
    position_max_m: float
    rmse_ratio: float
    availability_0_1m: float
    availability_0_5m: float
    availability_1m: float
    sustained_failure_onset_s: float | None
    position_nees_mean: float
    position_nees_median: float
    position_nees_p95: float
    position_nees_95_coverage: float
    covariance_trace_mean_m2: float
    gyroscope_delta_rms_radps: float
    accelerometer_delta_rms_mps2: float

    def __post_init__(self) -> None:
        if self.scenario not in _EXPECTED_SCENARIOS:
            raise ValueError("unexpected IMU-noise scenario")

        for name in (
            "white_noise_scale",
            "random_walk_scale",
            "position_rmse_m",
            "position_mean_m",
            "position_p95_m",
            "position_max_m",
            "rmse_ratio",
            "position_nees_mean",
            "position_nees_median",
            "position_nees_p95",
            "covariance_trace_mean_m2",
            "gyroscope_delta_rms_radps",
            "accelerometer_delta_rms_mps2",
        ):
            _finite_nonnegative(getattr(self, name), name)

        if self.white_noise_scale < 1.0:
            raise ValueError("white_noise_scale must be at least one")
        if self.random_walk_scale < 1.0:
            raise ValueError("random_walk_scale must be at least one")

        if (
            not isinstance(self.sample_count, int)
            or isinstance(self.sample_count, bool)
            or self.sample_count < 100
        ):
            raise ValueError(
                "sample_count must be an integer of at least 100"
            )

        for name in (
            "availability_0_1m",
            "availability_0_5m",
            "availability_1m",
            "position_nees_95_coverage",
        ):
            value = _finite_nonnegative(getattr(self, name), name)
            if value > 1.0:
                raise ValueError(f"{name} must not exceed one")

        if self.sustained_failure_onset_s is not None:
            _finite_nonnegative(
                self.sustained_failure_onset_s,
                "sustained_failure_onset_s",
            )

        if self.position_max_m < self.position_p95_m:
            raise ValueError("position maximum must exceed p95")

        if self.scenario == "baseline":
            if self.white_noise_scale != 1.0:
                raise ValueError("baseline white scale must be one")
            if self.random_walk_scale != 1.0:
                raise ValueError("baseline random-walk scale must be one")
            if self.rmse_ratio != 1.0:
                raise ValueError("baseline RMSE ratio must be one")
            if self.gyroscope_delta_rms_radps != 0.0:
                raise ValueError("baseline gyroscope delta must be zero")
            if self.accelerometer_delta_rms_mps2 != 0.0:
                raise ValueError(
                    "baseline accelerometer delta must be zero"
                )


@dataclass(frozen=True, slots=True)
class OpenVinsImuNoiseExperiment:
    """Validated committed OpenVINS IMU-noise degradation sweep."""

    upstream_commit: str
    experiment_config_sha256: str
    runner_binary_sha256: str
    camera_measurement_fingerprint: str
    nominal_imu_measurement_fingerprint: str
    scenario_results: tuple[ImuNoiseScenarioResult, ...]

    def __post_init__(self) -> None:
        if self.upstream_commit != _EXPECTED_COMMIT:
            raise ValueError("unexpected OpenVINS upstream commit")

        object.__setattr__(
            self,
            "experiment_config_sha256",
            _sha256(
                self.experiment_config_sha256,
                "experiment_config_sha256",
            ),
        )
        object.__setattr__(
            self,
            "runner_binary_sha256",
            _sha256(
                self.runner_binary_sha256,
                "runner_binary_sha256",
            ),
        )

        for name in (
            "camera_measurement_fingerprint",
            "nominal_imu_measurement_fingerprint",
        ):
            value = getattr(self, name)
            if (
                not isinstance(value, str)
                or len(value) != 16
                or any(character not in _HEX for character in value)
            ):
                raise ValueError(f"{name} must be a 64-bit hex digest")

        names = tuple(
            result.scenario
            for result in self.scenario_results
        )
        if names != _EXPECTED_SCENARIOS:
            raise ValueError(
                "IMU-noise scenarios are missing or out of order"
            )


def load_openvins_imu_noise_experiment(
    manifest_path: str | Path,
    results_path: str | Path,
) -> OpenVinsImuNoiseExperiment:
    """Load and strictly validate the committed IMU-noise sweep."""

    manifest_file = Path(manifest_path)
    results_file = Path(results_path)

    if not manifest_file.is_file():
        raise FileNotFoundError(manifest_file)
    if not results_file.is_file():
        raise FileNotFoundError(results_file)

    manifest = _mapping(
        json.loads(manifest_file.read_text(encoding="utf-8")),
        "manifest",
    )
    results_root = _mapping(
        json.loads(results_file.read_text(encoding="utf-8")),
        "results",
    )

    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported IMU-noise manifest schema")
    if manifest.get("experiment") != (
        "openvins-imu-noise-degradation"
    ):
        raise ValueError("unexpected IMU-noise experiment")
    if manifest.get("upstream_commit") != _EXPECTED_COMMIT:
        raise ValueError("IMU-noise upstream commit mismatch")
    if manifest.get("release_tag") != "v2.7":
        raise ValueError("IMU-noise experiment must use v2.7")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official OpenVINS source must remain unchanged")
    if manifest.get("runner_source_location") != "external-only":
        raise ValueError("GPL-linked runner must remain external")
    if manifest.get("estimator_uses_nominal_noise_model") is not True:
        raise ValueError("estimator must retain nominal noise model")

    verification = _mapping(
        manifest.get("verification"),
        "verification",
    )
    if verification.get(
        "all_scenario_replays_byte_identical"
    ) is not True:
        raise ValueError("scenario replays must be byte-identical")
    if verification.get(
        "reference_trajectories_byte_identical"
    ) is not True:
        raise ValueError("reference trajectories must be identical")
    if verification.get(
        "common_nominal_measurement_realization"
    ) is not True:
        raise ValueError("nominal measurement realization must match")
    if verification.get("position_covariance_positive_definite") is not True:
        raise ValueError("position covariance must be positive definite")
    if verification.get("output_schema") != (
        "veranav-position-trajectory-v1"
    ):
        raise ValueError("unexpected trajectory schema")
    if verification.get("frame_mapping") != (
        "openvins-global-xyz-to-veranav-ned"
    ):
        raise ValueError("unexpected frame mapping")

    if results_root.get("schema_version") != 1:
        raise ValueError("unsupported IMU-noise results schema")
    if results_root.get("experiment") != (
        "openvins-imu-noise-degradation"
    ):
        raise ValueError("results experiment mismatch")

    raw_results = results_root.get("scenarios")
    if not isinstance(raw_results, list):
        raise TypeError("scenarios must be a list")

    scenario_results = tuple(
        ImuNoiseScenarioResult(
            scenario=str(raw["scenario"]),
            white_noise_scale=float(raw["white_noise_scale"]),
            random_walk_scale=float(raw["random_walk_scale"]),
            sample_count=int(raw["sample_count"]),
            position_rmse_m=float(raw["position_rmse_m"]),
            position_mean_m=float(raw["position_mean_m"]),
            position_p95_m=float(raw["position_p95_m"]),
            position_max_m=float(raw["position_max_m"]),
            rmse_ratio=float(raw["rmse_ratio"]),
            availability_0_1m=float(raw["availability_0_1m"]),
            availability_0_5m=float(raw["availability_0_5m"]),
            availability_1m=float(raw["availability_1m"]),
            sustained_failure_onset_s=(
                None
                if raw["sustained_failure_onset_s"] is None
                else float(raw["sustained_failure_onset_s"])
            ),
            position_nees_mean=float(raw["position_nees_mean"]),
            position_nees_median=float(raw["position_nees_median"]),
            position_nees_p95=float(raw["position_nees_p95"]),
            position_nees_95_coverage=float(
                raw["position_nees_95_coverage"]
            ),
            covariance_trace_mean_m2=float(
                raw["covariance_trace_mean_m2"]
            ),
            gyroscope_delta_rms_radps=float(
                raw["gyroscope_delta_rms_radps"]
            ),
            accelerometer_delta_rms_mps2=float(
                raw["accelerometer_delta_rms_mps2"]
            ),
        )
        for raw in raw_results
    )

    runner = _mapping(manifest.get("runner"), "runner")
    measurements = _mapping(
        manifest.get("measurement_realization"),
        "measurement_realization",
    )

    return OpenVinsImuNoiseExperiment(
        upstream_commit=str(manifest["upstream_commit"]),
        experiment_config_sha256=manifest.get(
            "experiment_config_sha256"
        ),
        runner_binary_sha256=runner.get("binary_sha256"),
        camera_measurement_fingerprint=str(
            measurements["camera_fingerprint"]
        ),
        nominal_imu_measurement_fingerprint=str(
            measurements["nominal_imu_fingerprint"]
        ),
        scenario_results=scenario_results,
    )


__all__ = [
    "ImuNoiseScenarioResult",
    "OpenVinsImuNoiseExperiment",
    "load_openvins_imu_noise_experiment",
]
