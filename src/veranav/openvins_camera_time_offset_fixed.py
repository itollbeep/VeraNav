"""Validation for fixed versus online OpenVINS time calibration."""

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
class FixedTimeCalibrationScenarioResult:
    """Validated paired result for one signed timestamp offset."""

    scenario: str
    injected_offset_ms: float
    sample_count: int
    fixed_final_calibration_residual_ms: float
    fixed_nominal_rmse_m: float
    fixed_nominal_max_m: float
    fixed_physical_rmse_m: float
    fixed_physical_max_m: float
    fixed_rmse_ratio_to_fixed_baseline: float
    online_nominal_rmse_m: float
    online_calibration_aware_rmse_m: float
    online_final_calibration_residual_ms: float
    online_convergence_time_s: float | None
    online_calibration_rmse_reduction_m: float
    online_calibration_rmse_reduction_fraction: float
    online_to_fixed_rmse_ratio: float
    parameter_residual_reduction_fraction: float | None

    def __post_init__(self) -> None:
        if self.scenario not in _EXPECTED_SCENARIOS:
            raise ValueError("unexpected fixed-calibration scenario")

        for name in (
            "injected_offset_ms",
            "fixed_final_calibration_residual_ms",
            "online_final_calibration_residual_ms",
            "online_calibration_rmse_reduction_m",
            "online_calibration_rmse_reduction_fraction",
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
            "fixed_nominal_rmse_m",
            "fixed_nominal_max_m",
            "fixed_physical_rmse_m",
            "fixed_physical_max_m",
            "fixed_rmse_ratio_to_fixed_baseline",
            "online_nominal_rmse_m",
            "online_calibration_aware_rmse_m",
            "online_to_fixed_rmse_ratio",
        ):
            _nonnegative(getattr(self, name), name)

        if self.online_convergence_time_s is not None:
            _nonnegative(
                self.online_convergence_time_s,
                "online_convergence_time_s",
            )

        if self.parameter_residual_reduction_fraction is not None:
            _finite(
                self.parameter_residual_reduction_fraction,
                "parameter_residual_reduction_fraction",
            )

        if self.scenario == "baseline":
            if self.injected_offset_ms != 0.0:
                raise ValueError("baseline offset must be zero")
            if self.fixed_rmse_ratio_to_fixed_baseline != 1.0:
                raise ValueError(
                    "baseline fixed RMSE ratio must be one"
                )


@dataclass(frozen=True, slots=True)
class OpenVinsFixedTimeCalibrationComparison:
    """Validated committed fixed-versus-online comparison."""

    upstream_commit: str
    official_config_sha256: str
    fixed_config_sha256: str
    online_experiment_manifest_sha256: str
    runner_binary_sha256: str
    camera_measurement_fingerprint: str
    imu_measurement_fingerprint: str
    scenario_results: tuple[FixedTimeCalibrationScenarioResult, ...]

    def __post_init__(self) -> None:
        if self.upstream_commit != _EXPECTED_COMMIT:
            raise ValueError("unexpected OpenVINS upstream commit")

        for name in (
            "official_config_sha256",
            "fixed_config_sha256",
            "online_experiment_manifest_sha256",
            "runner_binary_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name),
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
                "fixed-calibration scenarios are missing or out of order"
            )


def load_openvins_fixed_time_calibration_comparison(
    manifest_path: str | Path,
    results_path: str | Path,
) -> OpenVinsFixedTimeCalibrationComparison:
    """Load and strictly validate the committed paired experiment."""

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
        raise ValueError("unsupported fixed-calibration manifest schema")
    if manifest.get("experiment") != (
        "openvins-camera-timestamp-offset-fixed-calibration"
    ):
        raise ValueError("unexpected fixed-calibration experiment")
    if manifest.get("upstream_commit") != _EXPECTED_COMMIT:
        raise ValueError("fixed-calibration commit mismatch")
    if manifest.get("release_tag") != "v2.7":
        raise ValueError("fixed-calibration experiment must use v2.7")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official OpenVINS source must remain unchanged")
    if manifest.get("online_time_calibration_enabled") is not False:
        raise ValueError("fixed experiment must disable time calibration")
    if manifest.get("runner_source_location") != "external-only":
        raise ValueError("GPL-linked runner must remain external")
    if manifest.get("configuration_change") != (
        "calib_cam_timeoffset:true-to-false"
    ):
        raise ValueError("unexpected derived configuration change")

    verification = _mapping(
        manifest.get("verification"),
        "verification",
    )
    if verification.get(
        "all_scenario_replays_byte_identical"
    ) is not True:
        raise ValueError("scenario replays must be byte-identical")
    if verification.get(
        "paired_online_fixed_measurement_realization"
    ) is not True:
        raise ValueError("online/fixed measurement pairing must hold")
    if verification.get(
        "online_fixed_physical_references_byte_identical"
    ) is not True:
        raise ValueError("online/fixed physical references must match")
    if verification.get(
        "fixed_calibrated_and_nominal_references_byte_identical"
    ) is not True:
        raise ValueError(
            "fixed calibrated and nominal references must match"
        )
    if verification.get("output_schema") != (
        "veranav-position-trajectory-v1"
    ):
        raise ValueError("unexpected trajectory schema")
    if verification.get("frame_mapping") != (
        "openvins-global-xyz-to-veranav-ned"
    ):
        raise ValueError("unexpected frame mapping")

    if results_root.get("schema_version") != 1:
        raise ValueError("unsupported fixed-calibration results schema")
    if results_root.get("experiment") != (
        "openvins-camera-timestamp-offset-fixed-calibration"
    ):
        raise ValueError("results experiment mismatch")

    raw_results = results_root.get("scenarios")
    if not isinstance(raw_results, list):
        raise TypeError("scenarios must be a list")

    scenario_results = tuple(
        FixedTimeCalibrationScenarioResult(
            scenario=str(raw["scenario"]),
            injected_offset_ms=float(raw["injected_offset_ms"]),
            sample_count=int(raw["sample_count"]),
            fixed_final_calibration_residual_ms=float(
                raw["fixed_final_calibration_residual_ms"]
            ),
            fixed_nominal_rmse_m=float(
                raw["fixed_nominal_rmse_m"]
            ),
            fixed_nominal_max_m=float(
                raw["fixed_nominal_max_m"]
            ),
            fixed_physical_rmse_m=float(
                raw["fixed_physical_rmse_m"]
            ),
            fixed_physical_max_m=float(
                raw["fixed_physical_max_m"]
            ),
            fixed_rmse_ratio_to_fixed_baseline=float(
                raw["fixed_rmse_ratio_to_fixed_baseline"]
            ),
            online_nominal_rmse_m=float(
                raw["online_nominal_rmse_m"]
            ),
            online_calibration_aware_rmse_m=float(
                raw["online_calibration_aware_rmse_m"]
            ),
            online_final_calibration_residual_ms=float(
                raw["online_final_calibration_residual_ms"]
            ),
            online_convergence_time_s=(
                None
                if raw["online_convergence_time_s"] is None
                else float(raw["online_convergence_time_s"])
            ),
            online_calibration_rmse_reduction_m=float(
                raw["online_calibration_rmse_reduction_m"]
            ),
            online_calibration_rmse_reduction_fraction=float(
                raw["online_calibration_rmse_reduction_fraction"]
            ),
            online_to_fixed_rmse_ratio=float(
                raw["online_to_fixed_rmse_ratio"]
            ),
            parameter_residual_reduction_fraction=(
                None
                if raw[
                    "parameter_residual_reduction_fraction"
                ] is None
                else float(
                    raw[
                        "parameter_residual_reduction_fraction"
                    ]
                )
            ),
        )
        for raw in raw_results
    )

    configs = _mapping(manifest.get("configurations"), "configurations")
    runner = _mapping(manifest.get("runner"), "runner")
    measurements = _mapping(
        manifest.get("measurement_realization"),
        "measurement_realization",
    )

    return OpenVinsFixedTimeCalibrationComparison(
        upstream_commit=str(manifest["upstream_commit"]),
        official_config_sha256=configs.get(
            "official_config_sha256"
        ),
        fixed_config_sha256=configs.get(
            "fixed_config_sha256"
        ),
        online_experiment_manifest_sha256=manifest.get(
            "online_experiment_manifest_sha256"
        ),
        runner_binary_sha256=runner.get("binary_sha256"),
        camera_measurement_fingerprint=str(
            measurements["camera_fingerprint"]
        ),
        imu_measurement_fingerprint=str(
            measurements["imu_fingerprint"]
        ),
        scenario_results=scenario_results,
    )


__all__ = [
    "FixedTimeCalibrationScenarioResult",
    "OpenVinsFixedTimeCalibrationComparison",
    "load_openvins_fixed_time_calibration_comparison",
]
