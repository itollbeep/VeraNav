"""Validation model for the OpenVINS visual-observation dropout sweep."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
_EXPECTED_SCENARIOS = (
    "baseline",
    "random-10",
    "random-30",
    "random-50",
    "burst-1s",
    "burst-3s",
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


def _nonnegative(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number


@dataclass(frozen=True, slots=True)
class VisualDropoutScenarioResult:
    """Validated result for one deterministic degradation scenario."""

    scenario: str
    mode: str
    sample_count: int
    total_frames: int
    degraded_frames: int
    realized_frame_drop_fraction: float
    dropped_observations: int
    position_rmse_m: float
    position_mean_m: float
    position_max_m: float
    rmse_delta_m: float
    rmse_ratio: float
    max_delta_m: float
    max_ratio: float

    def __post_init__(self) -> None:
        if self.scenario not in _EXPECTED_SCENARIOS:
            raise ValueError("unexpected visual-dropout scenario")
        if self.mode not in {
            "baseline",
            "bernoulli-frame-drop",
            "burst-frame-drop",
        }:
            raise ValueError("unexpected visual-dropout mode")

        for name in (
            "sample_count",
            "total_frames",
            "degraded_frames",
            "dropped_observations",
        ):
            value = getattr(self, name)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise ValueError(f"{name} must be a nonnegative integer")

        if self.sample_count < 100:
            raise ValueError("sample_count is unexpectedly small")
        if self.total_frames < self.degraded_frames:
            raise ValueError("degraded_frames exceeds total_frames")

        fraction = _nonnegative(
            self.realized_frame_drop_fraction,
            "realized_frame_drop_fraction",
        )
        if fraction > 1.0:
            raise ValueError(
                "realized_frame_drop_fraction must not exceed one"
            )

        for name in (
            "position_rmse_m",
            "position_mean_m",
            "position_max_m",
            "rmse_delta_m",
            "rmse_ratio",
            "max_delta_m",
            "max_ratio",
        ):
            _nonnegative(getattr(self, name), name)

        if self.position_max_m < self.position_mean_m:
            raise ValueError("position maximum must exceed the mean")

        if self.scenario == "baseline":
            if self.degraded_frames != 0:
                raise ValueError("baseline must not degrade camera frames")
            if self.dropped_observations != 0:
                raise ValueError("baseline must not drop observations")
            if self.rmse_delta_m != 0.0 or self.max_delta_m != 0.0:
                raise ValueError("baseline deltas must be zero")
            if self.rmse_ratio != 1.0 or self.max_ratio != 1.0:
                raise ValueError("baseline ratios must equal one")
        elif self.degraded_frames == 0:
            raise ValueError(
                "degradation scenario must affect camera frames"
            )


@dataclass(frozen=True, slots=True)
class OpenVinsVisualDropoutExperiment:
    """Validated committed OpenVINS visual-dropout experiment."""

    upstream_commit: str
    runner_binary_sha256: str
    experiment_config_sha256: str
    scenarios: tuple[VisualDropoutScenarioResult, ...]

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

        names = tuple(result.scenario for result in self.scenarios)
        if names != _EXPECTED_SCENARIOS:
            raise ValueError(
                "visual-dropout scenarios are missing or out of order"
            )


def load_openvins_visual_dropout_experiment(
    manifest_path: str | Path,
    results_path: str | Path,
) -> OpenVinsVisualDropoutExperiment:
    """Load and strictly validate the committed degradation sweep."""

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
        raise ValueError("unsupported visual-dropout manifest schema")
    if manifest.get("experiment") != (
        "openvins-visual-observation-dropout"
    ):
        raise ValueError("unexpected experiment identifier")
    if manifest.get("upstream_commit") != _EXPECTED_COMMIT:
        raise ValueError("manifest upstream commit mismatch")
    if manifest.get("release_tag") != "v2.7":
        raise ValueError("visual-dropout experiment must use v2.7")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official OpenVINS source must remain unchanged")
    if manifest.get("runner_source_location") != "external-only":
        raise ValueError("GPL-linked runner source must remain external")

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
        raise ValueError("unexpected trajectory schema")
    if verification.get("frame_mapping") != (
        "openvins-global-xyz-to-veranav-ned"
    ):
        raise ValueError("unexpected frame mapping")

    if results_root.get("schema_version") != 1:
        raise ValueError("unsupported visual-dropout results schema")
    if results_root.get("experiment") != (
        "openvins-visual-observation-dropout"
    ):
        raise ValueError("results experiment identifier mismatch")

    raw_results = results_root.get("scenarios")
    if not isinstance(raw_results, list):
        raise TypeError("scenarios must be a list")

    scenarios = tuple(
        VisualDropoutScenarioResult(
            scenario=str(raw["scenario"]),
            mode=str(raw["mode"]),
            sample_count=int(raw["sample_count"]),
            total_frames=int(raw["total_frames"]),
            degraded_frames=int(raw["degraded_frames"]),
            realized_frame_drop_fraction=float(
                raw["realized_frame_drop_fraction"]
            ),
            dropped_observations=int(
                raw["dropped_observations"]
            ),
            position_rmse_m=float(raw["position_rmse_m"]),
            position_mean_m=float(raw["position_mean_m"]),
            position_max_m=float(raw["position_max_m"]),
            rmse_delta_m=float(raw["rmse_delta_m"]),
            rmse_ratio=float(raw["rmse_ratio"]),
            max_delta_m=float(raw["max_delta_m"]),
            max_ratio=float(raw["max_ratio"]),
        )
        for raw in raw_results
    )

    runner = _mapping(manifest.get("runner"), "runner")

    return OpenVinsVisualDropoutExperiment(
        upstream_commit=str(manifest["upstream_commit"]),
        runner_binary_sha256=runner.get("binary_sha256"),
        experiment_config_sha256=manifest.get(
            "experiment_config_sha256"
        ),
        scenarios=scenarios,
    )


__all__ = [
    "OpenVinsVisualDropoutExperiment",
    "VisualDropoutScenarioResult",
    "load_openvins_visual_dropout_experiment",
]
