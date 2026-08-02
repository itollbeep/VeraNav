"""Validation model for the final OpenVINS reliability synthesis."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
_EXPECTED_FAMILIES = (
    "visual_dropout",
    "visual_burst",
    "camera_time_offset_online",
    "camera_time_offset_fixed",
    "time_divergence",
    "imu_noise",
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
class ReliabilityFamilySummary:
    """Validated final summary for one experiment family."""

    family: str
    scenario_count: int
    headline_metric: str
    headline_value: float
    conclusion: str

    def __post_init__(self) -> None:
        if self.family not in _EXPECTED_FAMILIES:
            raise ValueError("unexpected reliability family")
        if (
            not isinstance(self.scenario_count, int)
            or isinstance(self.scenario_count, bool)
            or self.scenario_count < 1
        ):
            raise ValueError("scenario_count must be a positive integer")
        if not self.headline_metric.strip():
            raise ValueError("headline_metric must not be empty")
        _finite_nonnegative(self.headline_value, "headline_value")
        if not self.conclusion.strip():
            raise ValueError("conclusion must not be empty")


@dataclass(frozen=True, slots=True)
class OpenVinsReliabilitySynthesis:
    """Validated committed final synthesis."""

    upstream_commit: str
    synthesis_config_sha256: str
    camera_measurement_fingerprint: str
    imu_measurement_fingerprint: str
    input_hashes: tuple[tuple[str, str], ...]
    family_summaries: tuple[ReliabilityFamilySummary, ...]
    stage_6_percent: int
    weighted_overall_percent: float

    def __post_init__(self) -> None:
        if self.upstream_commit != _EXPECTED_COMMIT:
            raise ValueError("unexpected OpenVINS upstream commit")

        object.__setattr__(
            self,
            "synthesis_config_sha256",
            _sha256(
                self.synthesis_config_sha256,
                "synthesis_config_sha256",
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

        if len(self.input_hashes) != 12:
            raise ValueError("exactly twelve input hashes are required")

        for label, digest in self.input_hashes:
            if not label.strip():
                raise ValueError("input hash label must not be empty")
            _sha256(digest, label)

        families = tuple(
            summary.family
            for summary in self.family_summaries
        )
        if families != _EXPECTED_FAMILIES:
            raise ValueError(
                "reliability families are missing or out of order"
            )

        if self.stage_6_percent != 100:
            raise ValueError("stage 6 must be complete")
        if self.weighted_overall_percent != 100.0:
            raise ValueError("weighted project progress must be complete")


def load_openvins_reliability_synthesis(
    manifest_path: str | Path,
    results_path: str | Path,
) -> OpenVinsReliabilitySynthesis:
    """Load and strictly validate the committed synthesis."""

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
        raise ValueError("unsupported synthesis manifest schema")
    if manifest.get("experiment") != (
        "openvins-reliability-synthesis"
    ):
        raise ValueError("unexpected synthesis experiment")
    if manifest.get("upstream_commit") != _EXPECTED_COMMIT:
        raise ValueError("synthesis upstream commit mismatch")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official OpenVINS source must remain unchanged")
    if manifest.get("analysis_only") is not True:
        raise ValueError("synthesis must be analysis-only")

    verification = _mapping(
        manifest.get("verification"),
        "verification",
    )
    if verification.get("input_hashes_verified") is not True:
        raise ValueError("input hashes must be verified")
    if verification.get("generated_twice_byte_identical") is not True:
        raise ValueError("synthesis outputs must be deterministic")
    if verification.get("no_new_estimator_execution") is not True:
        raise ValueError("synthesis must not run the estimator")
    if verification.get("figures_are_deterministic_svg") is not True:
        raise ValueError("figures must be deterministic SVG")

    if results.get("schema_version") != 1:
        raise ValueError("unsupported synthesis results schema")
    if results.get("experiment") != (
        "openvins-reliability-synthesis"
    ):
        raise ValueError("results experiment mismatch")

    raw_families = results.get("family_summaries")
    if not isinstance(raw_families, list):
        raise TypeError("family_summaries must be a list")

    family_summaries = tuple(
        ReliabilityFamilySummary(
            family=str(raw["family"]),
            scenario_count=int(raw["scenario_count"]),
            headline_metric=str(raw["headline_metric"]),
            headline_value=float(raw["headline_value"]),
            conclusion=str(raw["conclusion"]),
        )
        for raw in raw_families
    )

    input_hashes_raw = _mapping(
        manifest.get("input_hashes"),
        "input_hashes",
    )
    input_hashes = tuple(
        sorted(
            (
                str(label),
                str(digest),
            )
            for label, digest in input_hashes_raw.items()
        )
    )

    measurement = _mapping(
        manifest.get("measurement_realization"),
        "measurement_realization",
    )
    progress = _mapping(
        results.get("project_progress"),
        "project_progress",
    )

    return OpenVinsReliabilitySynthesis(
        upstream_commit=str(manifest["upstream_commit"]),
        synthesis_config_sha256=manifest.get(
            "synthesis_config_sha256"
        ),
        camera_measurement_fingerprint=str(
            measurement["camera_fingerprint"]
        ),
        imu_measurement_fingerprint=str(
            measurement["imu_fingerprint"]
        ),
        input_hashes=input_hashes,
        family_summaries=family_summaries,
        stage_6_percent=int(progress["stage_6_percent"]),
        weighted_overall_percent=float(
            progress["weighted_overall_percent"]
        ),
    )


__all__ = [
    "OpenVinsReliabilitySynthesis",
    "ReliabilityFamilySummary",
    "load_openvins_reliability_synthesis",
]
