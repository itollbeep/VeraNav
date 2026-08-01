"""Validation model for OpenVINS camera timestamp-offset experiments."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
_EXPECTED_SCENARIOS = (
    "baseline",
    "neg-50ms",
    "neg-20ms",
    "neg-10ms",
    "neg-5ms",
    "pos-5ms",
    "pos-10ms",
    "pos-20ms",
    "pos-50ms",
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


def _finite(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _nonnegative(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0.0:
        raise ValueError(f"{name} must be nonnegative")
    return number


@dataclass(frozen=True, slots=True)
class CameraTimeOffsetScenarioResult:
    """Validated metrics for one camera timestamp-offset scenario."""

    scenario: str
    injected_offset_ms: float
    sample_count: int
    true_cam_to_imu_ms: float
    target_cam_to_imu_ms: float
    initial_estimated_cam_to_imu_ms: float
    final_estimated_cam_to_imu_ms: float
    final_calibration_residual_ms: float
    tail_calibration_rmse_ms: float
    estimated_timestamp_correction_ms: float
    correction_error_ms: float
    converged_within_run: bool
    convergence_time_s: float | None
    nominal_clock_rmse_m: float
    nominal_clock_max_m: float
    nominal_clock_rmse_ratio: float
    calibration_aware_rmse_m: float
    calibration_aware_max_m: float
    calibration_aware_rmse_ratio: float
    physical_time_rmse_m: float
    physical_time_max_m: float

    def __post_init__(self) -> None:
        if self.scenario not in _EXPECTED_SCENARIOS:
            raise ValueError("unexpected camera time-offset scenario")

        for name in (
            "injected_offset_ms",
            "true_cam_to_imu_ms",
            "target_cam_to_imu_ms",
            "initial_estimated_cam_to_imu_ms",
            "final_estimated_cam_to_imu_ms",
            "final_calibration_residual_ms",
            "estimated_timestamp_correction_ms",
            "correction_error_ms",
        ):
            _finite(getattr(self, name), name)

        if (
            not isinstance(self.sample_count, int)
            or isinstance(self.sample_count, bool)
            or self.sample_count < 100
        ):
            raise ValueError(
                "sample_count must be an integer of at least 100"
            )

        for name in (
            "tail_calibration_rmse_ms",
            "nominal_clock_rmse_m",
            "nominal_clock_max_m",
            "nominal_clock_rmse_ratio",
            "calibration_aware_rmse_m",
            "calibration_aware_max_m",
            "calibration_aware_rmse_ratio",
            "physical_time_rmse_m",
            "physical_time_max_m",
        ):
            _nonnegative(getattr(self, name), name)

        if not isinstance(self.converged_within_run, bool):
            raise TypeError("converged_within_run must be a bool")

        if self.convergence_time_s is not None:
            _nonnegative(
                self.convergence_time_s,
                "convergence_time_s",
            )
            if not self.converged_within_run:
                raise ValueError(
                    "finite convergence time requires converged status"
                )
        elif self.converged_within_run:
            raise ValueError(
                "converged status requires finite convergence time"
            )

        if self.scenario == "baseline":
            if self.injected_offset_ms != 0.0:
                raise ValueError("baseline offset must be zero")
            if self.nominal_clock_rmse_ratio != 1.0:
                raise ValueError(
                    "baseline nominal RMSE ratio must be one"
                )
            if self.calibration_aware_rmse_ratio != 1.0:
                raise ValueError(
                    "baseline calibrated RMSE ratio must be one"
                )


@dataclass(frozen=True, slots=True)
class OpenVinsCameraTimeOffsetExperiment:
    """Validated committed OpenVINS timestamp-offset sweep."""

    upstream_commit: str
    runner_binary_sha256: str
    experiment_config_sha256: str
    camera_measurement_fingerprint: str
    imu_measurement_fingerprint: str
    scenario_results: tuple[CameraTimeOffsetScenarioResult, ...]

    def __post_init__(self) -> None:
        if self.upstream_commit != _EXPECTED_COMMIT:
            raise ValueError("unexpected OpenVINS upstream commit")

        object.__setattr__(
            self,
            "runner_binary_sha256",
            _sha256(
                self.runner_binary_sha256,
                "runner_binary_sha256",
            ),
        )
        object.__setattr__(
            self,
            "experiment_config_sha256",
            _sha256(
                self.experiment_config_sha256,
                "experiment_config_sha256",
            ),
        )

        for name in (
            "camera_measurement_fingerprint",
            "imu_measurement_fingerprint",
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
                "camera time-offset scenarios are missing or out of order"
            )


def load_openvins_camera_time_offset_experiment(
    manifest_path: str | Path,
    results_path: str | Path,
) -> OpenVinsCameraTimeOffsetExperiment:
    """Load and strictly validate the committed timestamp sweep."""

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
        raise ValueError("unsupported timestamp-offset manifest schema")
    if manifest.get("experiment") != (
        "openvins-camera-timestamp-offset"
    ):
        raise ValueError("unexpected timestamp-offset experiment")
    if manifest.get("upstream_commit") != _EXPECTED_COMMIT:
        raise ValueError("timestamp-offset commit mismatch")
    if manifest.get("release_tag") != "v2.7":
        raise ValueError("timestamp-offset experiment must use v2.7")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official OpenVINS source must remain unchanged")
    if manifest.get("runner_source_location") != "external-only":
        raise ValueError("GPL-linked runner must remain external")
    if manifest.get("online_time_calibration_enabled") is not True:
        raise ValueError("online time calibration must be enabled")

    verification = _mapping(
        manifest.get("verification"),
        "verification",
    )
    if verification.get(
        "all_scenario_replays_byte_identical"
    ) is not True:
        raise ValueError("scenario replays must be byte-identical")
    if verification.get(
        "physical_reference_trajectories_byte_identical"
    ) is not True:
        raise ValueError("physical references must be byte-identical")
    if verification.get(
        "common_measurement_realization"
    ) is not True:
        raise ValueError("measurement realization must be common")
    if verification.get("output_schema") != (
        "veranav-position-trajectory-v1"
    ):
        raise ValueError("unexpected trajectory schema")
    if verification.get("frame_mapping") != (
        "openvins-global-xyz-to-veranav-ned"
    ):
        raise ValueError("unexpected frame mapping")

    if results_root.get("schema_version") != 1:
        raise ValueError("unsupported timestamp-offset results schema")
    if results_root.get("experiment") != (
        "openvins-camera-timestamp-offset"
    ):
        raise ValueError("results experiment mismatch")

    raw_results = results_root.get("scenarios")
    if not isinstance(raw_results, list):
        raise TypeError("scenarios must be a list")

    scenario_results = tuple(
        CameraTimeOffsetScenarioResult(
            scenario=str(raw["scenario"]),
            injected_offset_ms=float(raw["injected_offset_ms"]),
            sample_count=int(raw["sample_count"]),
            true_cam_to_imu_ms=float(raw["true_cam_to_imu_ms"]),
            target_cam_to_imu_ms=float(raw["target_cam_to_imu_ms"]),
            initial_estimated_cam_to_imu_ms=float(
                raw["initial_estimated_cam_to_imu_ms"]
            ),
            final_estimated_cam_to_imu_ms=float(
                raw["final_estimated_cam_to_imu_ms"]
            ),
            final_calibration_residual_ms=float(
                raw["final_calibration_residual_ms"]
            ),
            tail_calibration_rmse_ms=float(
                raw["tail_calibration_rmse_ms"]
            ),
            estimated_timestamp_correction_ms=float(
                raw["estimated_timestamp_correction_ms"]
            ),
            correction_error_ms=float(
                raw["correction_error_ms"]
            ),
            converged_within_run=bool(
                raw["converged_within_run"]
            ),
            convergence_time_s=(
                None
                if raw["convergence_time_s"] is None
                else float(raw["convergence_time_s"])
            ),
            nominal_clock_rmse_m=float(
                raw["nominal_clock_rmse_m"]
            ),
            nominal_clock_max_m=float(
                raw["nominal_clock_max_m"]
            ),
            nominal_clock_rmse_ratio=float(
                raw["nominal_clock_rmse_ratio"]
            ),
            calibration_aware_rmse_m=float(
                raw["calibration_aware_rmse_m"]
            ),
            calibration_aware_max_m=float(
                raw["calibration_aware_max_m"]
            ),
            calibration_aware_rmse_ratio=float(
                raw["calibration_aware_rmse_ratio"]
            ),
            physical_time_rmse_m=float(
                raw["physical_time_rmse_m"]
            ),
            physical_time_max_m=float(
                raw["physical_time_max_m"]
            ),
        )
        for raw in raw_results
    )

    runner = _mapping(manifest.get("runner"), "runner")
    measurements = _mapping(
        manifest.get("measurement_realization"),
        "measurement_realization",
    )

    return OpenVinsCameraTimeOffsetExperiment(
        upstream_commit=str(manifest["upstream_commit"]),
        runner_binary_sha256=runner.get("binary_sha256"),
        experiment_config_sha256=manifest.get(
            "experiment_config_sha256"
        ),
        camera_measurement_fingerprint=str(
            measurements["camera_fingerprint"]
        ),
        imu_measurement_fingerprint=str(
            measurements["imu_fingerprint"]
        ),
        scenario_results=scenario_results,
    )


__all__ = [
    "CameraTimeOffsetScenarioResult",
    "OpenVinsCameraTimeOffsetExperiment",
    "load_openvins_camera_time_offset_experiment",
]
