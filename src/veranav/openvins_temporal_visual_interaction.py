"""Validation model for OpenVINS temporal-visual interaction evidence."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_SCENARIOS = (
    "neg20-drop00", "neg20-drop10", "neg20-drop30", "neg20-drop50",
    "zero-drop00", "zero-drop10", "zero-drop30", "zero-drop50",
    "pos20-drop00", "pos20-drop10", "pos20-drop30", "pos20-drop50",
)
EXPECTED_INTERACTIONS = (
    "neg20-drop10", "neg20-drop30", "neg20-drop50",
    "pos20-drop10", "pos20-drop30", "pos20-drop50",
)
_HEX = frozenset("0123456789abcdef")


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _finite_nonnegative(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number


def _sha256(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(ch not in _HEX for ch in normalized):
        raise ValueError(f"{name} must be a SHA256 digest")
    return normalized


@dataclass(frozen=True, slots=True)
class TemporalVisualScenarioResult:
    scenario: str
    offset_ms: float
    requested_dropout_fraction: float
    realized_dropout_fraction: float
    position_rmse_m: float
    local_max_rmse_m: float
    final_abs_residual_ms: float
    one_metre_availability: float
    convergence_time_s: float | None

    def __post_init__(self) -> None:
        if self.scenario not in EXPECTED_SCENARIOS:
            raise ValueError("unexpected interaction scenario")
        if self.offset_ms not in {-20.0, 0.0, 20.0}:
            raise ValueError("unexpected temporal offset")
        if self.requested_dropout_fraction not in {0.0, 0.1, 0.3, 0.5}:
            raise ValueError("unexpected dropout fraction")
        for name in (
            "realized_dropout_fraction",
            "position_rmse_m",
            "local_max_rmse_m",
            "final_abs_residual_ms",
            "one_metre_availability",
        ):
            _finite_nonnegative(getattr(self, name), name)
        if self.realized_dropout_fraction > 1.0:
            raise ValueError("realized dropout must not exceed one")
        if self.one_metre_availability > 1.0:
            raise ValueError("availability must not exceed one")
        if self.convergence_time_s is not None:
            _finite_nonnegative(self.convergence_time_s, "convergence_time_s")


@dataclass(frozen=True, slots=True)
class TemporalVisualInteractionResult:
    scenario: str
    rmse_interaction_ratio: float
    local_rmse_interaction_ratio: float
    supported_metric_count: int
    criterion_supported: bool

    def __post_init__(self) -> None:
        if self.scenario not in EXPECTED_INTERACTIONS:
            raise ValueError("unexpected joint scenario")
        _finite_nonnegative(self.rmse_interaction_ratio, "rmse_interaction_ratio")
        _finite_nonnegative(
            self.local_rmse_interaction_ratio,
            "local_rmse_interaction_ratio",
        )
        if (
            not isinstance(self.supported_metric_count, int)
            or isinstance(self.supported_metric_count, bool)
            or not 0 <= self.supported_metric_count <= 5
        ):
            raise ValueError("invalid supported metric count")
        if self.criterion_supported != (self.supported_metric_count >= 2):
            raise ValueError("interaction criterion flag mismatch")


@dataclass(frozen=True, slots=True)
class OpenVinsTemporalVisualInteraction:
    upstream_commit: str
    experiment_config_sha256: str
    runner_binary_sha256: str
    camera_measurement_fingerprint: str
    imu_measurement_fingerprint: str
    interaction_status: str
    scenario_results: tuple[TemporalVisualScenarioResult, ...]
    interaction_results: tuple[TemporalVisualInteractionResult, ...]
    v1_overall_percent: float
    v2_overall_percent: float

    def __post_init__(self) -> None:
        if self.upstream_commit != EXPECTED_COMMIT:
            raise ValueError("unexpected OpenVINS upstream commit")
        object.__setattr__(
            self,
            "experiment_config_sha256",
            _sha256(self.experiment_config_sha256, "experiment_config_sha256"),
        )
        object.__setattr__(
            self,
            "runner_binary_sha256",
            _sha256(self.runner_binary_sha256, "runner_binary_sha256"),
        )
        for name in (
            "camera_measurement_fingerprint",
            "imu_measurement_fingerprint",
        ):
            value = getattr(self, name)
            if (
                not isinstance(value, str)
                or len(value) != 16
                or any(ch not in _HEX for ch in value)
            ):
                raise ValueError(f"{name} must be a 64-bit hex digest")
        if self.interaction_status not in {
            "pilot_supported",
            "pilot_weak_support",
            "pilot_not_supported",
        }:
            raise ValueError("unexpected interaction status")
        if tuple(x.scenario for x in self.scenario_results) != EXPECTED_SCENARIOS:
            raise ValueError("scenario results are missing or out of order")
        if (
            tuple(x.scenario for x in self.interaction_results)
            != EXPECTED_INTERACTIONS
        ):
            raise ValueError("interaction results are missing or out of order")
        if self.v1_overall_percent != 100.0:
            raise ValueError("VeraNav v1 must remain complete")
        if self.v2_overall_percent != 20.0:
            raise ValueError("unexpected VeraNav v2 progress")


def load_temporal_visual_interaction(
    manifest_path: str | Path,
    results_path: str | Path,
) -> OpenVinsTemporalVisualInteraction:
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
    results = _mapping(
        json.loads(results_file.read_text(encoding="utf-8")),
        "results",
    )
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported interaction manifest schema")
    if manifest.get("experiment") != (
        "openvins-temporal-calibration-visual-degradation-interaction"
    ):
        raise ValueError("unexpected interaction experiment")
    if manifest.get("upstream_commit") != EXPECTED_COMMIT:
        raise ValueError("interaction upstream commit mismatch")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official OpenVINS source must remain unchanged")

    verification = _mapping(manifest.get("verification"), "verification")
    for key in (
        "deterministic_replay_verified",
        "dropout_masks_equal_across_offsets",
        "dropout_masks_nested",
        "physical_references_byte_identical",
        "raw_measurement_fingerprints_identical",
        "single_factor_anchors_reproduced",
    ):
        if verification.get(key) is not True:
            raise ValueError(f"required verification failed: {key}")

    raw_scenarios = results.get("scenarios")
    raw_interactions = results.get("interactions")
    if not isinstance(raw_scenarios, list):
        raise TypeError("scenarios must be a list")
    if not isinstance(raw_interactions, list):
        raise TypeError("interactions must be a list")

    scenario_results = tuple(
        TemporalVisualScenarioResult(
            scenario=str(raw["scenario"]),
            offset_ms=float(raw["offset_ms"]),
            requested_dropout_fraction=float(raw["requested_dropout_fraction"]),
            realized_dropout_fraction=float(raw["realized_dropout_fraction"]),
            position_rmse_m=float(raw["position_rmse_m"]),
            local_max_rmse_m=float(raw["local_max_rmse_m"]),
            final_abs_residual_ms=float(raw["final_abs_residual_ms"]),
            one_metre_availability=float(raw["one_metre_availability"]),
            convergence_time_s=(
                None
                if raw["convergence_time_s"] is None
                else float(raw["convergence_time_s"])
            ),
        )
        for raw in raw_scenarios
    )
    interaction_results = tuple(
        TemporalVisualInteractionResult(
            scenario=str(raw["scenario"]),
            rmse_interaction_ratio=float(raw["rmse_interaction_ratio"]),
            local_rmse_interaction_ratio=float(
                raw["local_rmse_interaction_ratio"]
            ),
            supported_metric_count=int(raw["supported_metric_count"]),
            criterion_supported=bool(raw["criterion_supported"]),
        )
        for raw in raw_interactions
    )
    runner = _mapping(manifest.get("runner"), "runner")
    measurement = _mapping(
        manifest.get("measurement_realization"),
        "measurement_realization",
    )
    progress = _mapping(results.get("project_progress"), "project_progress")
    return OpenVinsTemporalVisualInteraction(
        upstream_commit=str(manifest["upstream_commit"]),
        experiment_config_sha256=manifest.get("experiment_config_sha256"),
        runner_binary_sha256=runner.get("binary_sha256"),
        camera_measurement_fingerprint=str(
            measurement["camera_fingerprint"]
        ),
        imu_measurement_fingerprint=str(measurement["imu_fingerprint"]),
        interaction_status=str(results["interaction_status"]),
        scenario_results=scenario_results,
        interaction_results=interaction_results,
        v1_overall_percent=float(progress["v1_overall_percent"]),
        v2_overall_percent=float(progress["v2_overall_percent"]),
    )


__all__ = [
    "OpenVinsTemporalVisualInteraction",
    "TemporalVisualInteractionResult",
    "TemporalVisualScenarioResult",
    "load_temporal_visual_interaction",
]
