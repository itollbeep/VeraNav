"""Validation model for OpenVINS visual-outage timing sensitivity."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
_EXPECTED_SCENARIOS = (
    "baseline",
    "burst-t030-d1",
    "burst-t030-d3",
    "burst-t090-d1",
    "burst-t090-d3",
    "burst-t150-d1",
    "burst-t150-d3",
    "burst-t210-d1",
    "burst-t210-d3",
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
class VisualBurstScenarioResult:
    """Validated local and global metrics for one outage scenario."""

    scenario: str
    mode: str
    burst_start_s: float
    burst_duration_s: float
    sample_count: int
    degraded_frames: int
    dropped_observations: int
    overall_rmse_m: float
    overall_max_m: float
    pre_window_rmse_m: float
    outage_rmse_m: float
    post_window_rmse_m: float
    local_window_rmse_m: float
    baseline_local_window_rmse_m: float
    local_window_rmse_ratio: float
    local_window_peak_m: float
    baseline_local_window_peak_m: float
    local_window_peak_ratio: float
    peak_excess_error_m: float
    integrated_positive_excess_m_s: float
    recovery_time_s: float | None
    recovered_within_horizon: bool

    def __post_init__(self) -> None:
        if self.scenario not in _EXPECTED_SCENARIOS:
            raise ValueError("unexpected visual-burst scenario")
        if self.mode not in {"baseline", "burst-frame-drop"}:
            raise ValueError("unexpected visual-burst mode")

        for name in ("sample_count", "degraded_frames", "dropped_observations"):
            value = getattr(self, name)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise ValueError(f"{name} must be a nonnegative integer")

        if self.sample_count < 100:
            raise ValueError("sample_count is unexpectedly small")

        for name in (
            "burst_start_s",
            "burst_duration_s",
            "overall_rmse_m",
            "overall_max_m",
            "pre_window_rmse_m",
            "outage_rmse_m",
            "post_window_rmse_m",
            "local_window_rmse_m",
            "baseline_local_window_rmse_m",
            "local_window_rmse_ratio",
            "local_window_peak_m",
            "baseline_local_window_peak_m",
            "local_window_peak_ratio",
            "peak_excess_error_m",
            "integrated_positive_excess_m_s",
        ):
            _finite_nonnegative(getattr(self, name), name)

        if not isinstance(self.recovered_within_horizon, bool):
            raise TypeError("recovered_within_horizon must be a bool")

        if self.recovery_time_s is not None:
            _finite_nonnegative(
                self.recovery_time_s,
                "recovery_time_s",
            )
            if not self.recovered_within_horizon:
                raise ValueError(
                    "finite recovery_time_s requires recovered status"
                )
        elif self.recovered_within_horizon:
            raise ValueError(
                "recovered status requires finite recovery_time_s"
            )

        if self.scenario == "baseline":
            if self.mode != "baseline":
                raise ValueError("baseline mode mismatch")
            if self.degraded_frames != 0:
                raise ValueError("baseline must not degrade frames")
            if self.dropped_observations != 0:
                raise ValueError("baseline must not drop observations")
            if self.local_window_rmse_ratio != 1.0:
                raise ValueError("baseline local RMSE ratio must be one")
            if self.local_window_peak_ratio != 1.0:
                raise ValueError("baseline peak ratio must be one")
            if self.peak_excess_error_m != 0.0:
                raise ValueError("baseline excess error must be zero")
            if self.integrated_positive_excess_m_s != 0.0:
                raise ValueError(
                    "baseline integrated excess must be zero"
                )
        elif self.degraded_frames == 0:
            raise ValueError("outage scenario must degrade camera frames")


@dataclass(frozen=True, slots=True)
class OpenVinsVisualBurstSweep:
    """Validated committed multi-start visual-outage experiment."""

    upstream_commit: str
    runner_binary_sha256: str
    experiment_config_sha256: str
    scenario_results: tuple[VisualBurstScenarioResult, ...]

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

        names = tuple(
            result.scenario
            for result in self.scenario_results
        )
        if names != _EXPECTED_SCENARIOS:
            raise ValueError(
                "visual-burst scenarios are missing or out of order"
            )


def load_openvins_visual_burst_sweep(
    manifest_path: str | Path,
    results_path: str | Path,
) -> OpenVinsVisualBurstSweep:
    """Load and strictly validate the committed timing sweep."""

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
        raise ValueError("unsupported visual-burst manifest schema")
    if manifest.get("experiment") != (
        "openvins-visual-burst-timing-sensitivity"
    ):
        raise ValueError("unexpected visual-burst experiment")
    if manifest.get("upstream_commit") != _EXPECTED_COMMIT:
        raise ValueError("visual-burst commit mismatch")
    if manifest.get("release_tag") != "v2.7":
        raise ValueError("visual-burst experiment must use v2.7")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official OpenVINS source must remain unchanged")
    if manifest.get("runner_source_location") != "external-only":
        raise ValueError("GPL-linked runner must remain external")

    verification = _mapping(
        manifest.get("verification"),
        "verification",
    )
    if verification.get(
        "all_scenario_replays_byte_identical"
    ) is not True:
        raise ValueError("scenario replays must be byte-identical")
    if verification.get(
        "paired_reference_trajectories_byte_identical"
    ) is not True:
        raise ValueError("paired references must be byte-identical")
    if verification.get("output_schema") != (
        "veranav-position-trajectory-v1"
    ):
        raise ValueError("unexpected output schema")
    if verification.get("frame_mapping") != (
        "openvins-global-xyz-to-veranav-ned"
    ):
        raise ValueError("unexpected frame mapping")

    if results_root.get("schema_version") != 1:
        raise ValueError("unsupported visual-burst results schema")
    if results_root.get("experiment") != (
        "openvins-visual-burst-timing-sensitivity"
    ):
        raise ValueError("results experiment mismatch")

    raw_results = results_root.get("scenarios")
    if not isinstance(raw_results, list):
        raise TypeError("scenarios must be a list")

    scenario_results = tuple(
        VisualBurstScenarioResult(
            scenario=str(raw["scenario"]),
            mode=str(raw["mode"]),
            burst_start_s=float(raw["burst_start_s"]),
            burst_duration_s=float(raw["burst_duration_s"]),
            sample_count=int(raw["sample_count"]),
            degraded_frames=int(raw["degraded_frames"]),
            dropped_observations=int(
                raw["dropped_observations"]
            ),
            overall_rmse_m=float(raw["overall_rmse_m"]),
            overall_max_m=float(raw["overall_max_m"]),
            pre_window_rmse_m=float(
                raw["pre_window_rmse_m"]
            ),
            outage_rmse_m=float(raw["outage_rmse_m"]),
            post_window_rmse_m=float(
                raw["post_window_rmse_m"]
            ),
            local_window_rmse_m=float(
                raw["local_window_rmse_m"]
            ),
            baseline_local_window_rmse_m=float(
                raw["baseline_local_window_rmse_m"]
            ),
            local_window_rmse_ratio=float(
                raw["local_window_rmse_ratio"]
            ),
            local_window_peak_m=float(
                raw["local_window_peak_m"]
            ),
            baseline_local_window_peak_m=float(
                raw["baseline_local_window_peak_m"]
            ),
            local_window_peak_ratio=float(
                raw["local_window_peak_ratio"]
            ),
            peak_excess_error_m=float(
                raw["peak_excess_error_m"]
            ),
            integrated_positive_excess_m_s=float(
                raw["integrated_positive_excess_m_s"]
            ),
            recovery_time_s=(
                None
                if raw["recovery_time_s"] is None
                else float(raw["recovery_time_s"])
            ),
            recovered_within_horizon=bool(
                raw["recovered_within_horizon"]
            ),
        )
        for raw in raw_results
    )

    runner = _mapping(manifest.get("runner"), "runner")

    return OpenVinsVisualBurstSweep(
        upstream_commit=str(manifest["upstream_commit"]),
        runner_binary_sha256=runner.get("binary_sha256"),
        experiment_config_sha256=manifest.get(
            "experiment_config_sha256"
        ),
        scenario_results=scenario_results,
    )


__all__ = [
    "OpenVinsVisualBurstSweep",
    "VisualBurstScenarioResult",
    "load_openvins_visual_burst_sweep",
]
