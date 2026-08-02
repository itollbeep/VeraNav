"""Validation for OpenVINS fixed-time divergence diagnostics."""

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


def _finite_nonnegative(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number


@dataclass(frozen=True, slots=True)
class ErrorTraceDiagnostics:
    """Validated summary of one position-error trace."""

    rmse_m: float
    mean_m: float
    median_m: float
    p90_m: float
    p95_m: float
    p99_m: float
    max_m: float
    max_time_s: float
    final_error_m: float
    sustained_failure_onset_s: float | None
    recovery_time_s: float | None
    recovered_after_failure: bool
    post_onset_fraction_above_1m: float
    top_1_percent_squared_error_share: float
    top_5_percent_squared_error_share: float
    broad_trajectory_failure: bool
    catastrophic_divergence: bool

    def __post_init__(self) -> None:
        for name in (
            "rmse_m",
            "mean_m",
            "median_m",
            "p90_m",
            "p95_m",
            "p99_m",
            "max_m",
            "max_time_s",
            "final_error_m",
            "post_onset_fraction_above_1m",
            "top_1_percent_squared_error_share",
            "top_5_percent_squared_error_share",
        ):
            _finite_nonnegative(getattr(self, name), name)

        for name in (
            "post_onset_fraction_above_1m",
            "top_1_percent_squared_error_share",
            "top_5_percent_squared_error_share",
        ):
            if getattr(self, name) > 1.0:
                raise ValueError(f"{name} must not exceed one")

        if self.sustained_failure_onset_s is not None:
            _finite_nonnegative(
                self.sustained_failure_onset_s,
                "sustained_failure_onset_s",
            )

        if self.recovery_time_s is not None:
            _finite_nonnegative(
                self.recovery_time_s,
                "recovery_time_s",
            )
            if not self.recovered_after_failure:
                raise ValueError(
                    "finite recovery time requires recovered status"
                )
        elif self.recovered_after_failure:
            raise ValueError(
                "recovered status requires finite recovery time"
            )

        if self.max_m < self.p99_m:
            raise ValueError("maximum error must exceed p99")
        if self.p99_m < self.p95_m or self.p95_m < self.p90_m:
            raise ValueError("error quantiles are not monotonic")
        if self.p90_m < self.median_m:
            raise ValueError("error quantiles are not monotonic")


@dataclass(frozen=True, slots=True)
class TimeDivergenceScenario:
    """Validated paired fixed and online divergence result."""

    scenario: str
    injected_offset_ms: float
    sample_count: int
    duration_s: float
    fixed: ErrorTraceDiagnostics
    online: ErrorTraceDiagnostics

    def __post_init__(self) -> None:
        if self.scenario not in _EXPECTED_SCENARIOS:
            raise ValueError("unexpected divergence scenario")
        if (
            not isinstance(self.sample_count, int)
            or isinstance(self.sample_count, bool)
            or self.sample_count < 100
        ):
            raise ValueError(
                "sample_count must be an integer of at least 100"
            )
        _finite_nonnegative(self.duration_s, "duration_s")

        if self.scenario == "baseline":
            if self.injected_offset_ms != 0.0:
                raise ValueError("baseline offset must be zero")
        elif self.injected_offset_ms == 0.0:
            raise ValueError("nonbaseline offset must be nonzero")


@dataclass(frozen=True, slots=True)
class OpenVinsTimeDivergenceDiagnostics:
    """Validated committed divergence-diagnostic experiment."""

    upstream_commit: str
    analysis_config_sha256: str
    fixed_results_sha256: str
    online_results_sha256: str
    camera_measurement_fingerprint: str
    imu_measurement_fingerprint: str
    scenarios: tuple[TimeDivergenceScenario, ...]

    def __post_init__(self) -> None:
        if self.upstream_commit != _EXPECTED_COMMIT:
            raise ValueError("unexpected OpenVINS upstream commit")

        for name in (
            "analysis_config_sha256",
            "fixed_results_sha256",
            "online_results_sha256",
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

        names = tuple(result.scenario for result in self.scenarios)
        if names != _EXPECTED_SCENARIOS:
            raise ValueError(
                "divergence scenarios are missing or out of order"
            )


def _trace(value: object, name: str) -> ErrorTraceDiagnostics:
    raw = _mapping(value, name)
    return ErrorTraceDiagnostics(
        rmse_m=float(raw["rmse_m"]),
        mean_m=float(raw["mean_m"]),
        median_m=float(raw["median_m"]),
        p90_m=float(raw["p90_m"]),
        p95_m=float(raw["p95_m"]),
        p99_m=float(raw["p99_m"]),
        max_m=float(raw["max_m"]),
        max_time_s=float(raw["max_time_s"]),
        final_error_m=float(raw["final_error_m"]),
        sustained_failure_onset_s=(
            None
            if raw["sustained_failure_onset_s"] is None
            else float(raw["sustained_failure_onset_s"])
        ),
        recovery_time_s=(
            None
            if raw["recovery_time_s"] is None
            else float(raw["recovery_time_s"])
        ),
        recovered_after_failure=bool(
            raw["recovered_after_failure"]
        ),
        post_onset_fraction_above_1m=float(
            raw["post_onset_fraction_above_1m"]
        ),
        top_1_percent_squared_error_share=float(
            raw["top_1_percent_squared_error_share"]
        ),
        top_5_percent_squared_error_share=float(
            raw["top_5_percent_squared_error_share"]
        ),
        broad_trajectory_failure=bool(
            raw["broad_trajectory_failure"]
        ),
        catastrophic_divergence=bool(
            raw["catastrophic_divergence"]
        ),
    )


def load_openvins_time_divergence_diagnostics(
    manifest_path: str | Path,
    results_path: str | Path,
) -> OpenVinsTimeDivergenceDiagnostics:
    """Load and strictly validate committed divergence diagnostics."""

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
        raise ValueError("unsupported divergence manifest schema")
    if manifest.get("experiment") != (
        "openvins-fixed-time-divergence-diagnostics"
    ):
        raise ValueError("unexpected divergence experiment")
    if manifest.get("upstream_commit") != _EXPECTED_COMMIT:
        raise ValueError("divergence upstream commit mismatch")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official OpenVINS source must remain unchanged")
    if manifest.get("analysis_only") is not True:
        raise ValueError("divergence diagnostics must be analysis-only")

    verification = _mapping(
        manifest.get("verification"),
        "verification",
    )
    if verification.get("input_artifact_hashes_verified") is not True:
        raise ValueError("input artifact hashes must be verified")
    if verification.get(
        "fixed_online_physical_references_byte_identical"
    ) is not True:
        raise ValueError("paired physical references must match")
    if verification.get(
        "paired_measurement_realization"
    ) is not True:
        raise ValueError("measurement realization must be paired")
    if verification.get("no_new_estimator_execution") is not True:
        raise ValueError("diagnostic must not rerun estimator")

    if results_root.get("schema_version") != 1:
        raise ValueError("unsupported divergence results schema")
    if results_root.get("experiment") != (
        "openvins-fixed-time-divergence-diagnostics"
    ):
        raise ValueError("results experiment mismatch")

    raw_scenarios = results_root.get("scenarios")
    if not isinstance(raw_scenarios, list):
        raise TypeError("scenarios must be a list")

    scenarios = tuple(
        TimeDivergenceScenario(
            scenario=str(raw["scenario"]),
            injected_offset_ms=float(raw["injected_offset_ms"]),
            sample_count=int(raw["sample_count"]),
            duration_s=float(raw["duration_s"]),
            fixed=_trace(raw["fixed"], "fixed"),
            online=_trace(raw["online"], "online"),
        )
        for raw in raw_scenarios
    )

    inputs = _mapping(manifest.get("inputs"), "inputs")
    measurements = _mapping(
        manifest.get("measurement_realization"),
        "measurement_realization",
    )

    return OpenVinsTimeDivergenceDiagnostics(
        upstream_commit=str(manifest["upstream_commit"]),
        analysis_config_sha256=manifest.get(
            "analysis_config_sha256"
        ),
        fixed_results_sha256=inputs.get("fixed_results_sha256"),
        online_results_sha256=inputs.get("online_results_sha256"),
        camera_measurement_fingerprint=str(
            measurements["camera_fingerprint"]
        ),
        imu_measurement_fingerprint=str(
            measurements["imu_fingerprint"]
        ),
        scenarios=scenarios,
    )


__all__ = [
    "ErrorTraceDiagnostics",
    "OpenVinsTimeDivergenceDiagnostics",
    "TimeDivergenceScenario",
    "load_openvins_time_divergence_diagnostics",
]
