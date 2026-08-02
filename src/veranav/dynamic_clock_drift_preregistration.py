"""Validation model for the V2-E02 dynamic clock drift preregistration."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_PARENT = "92ba1942801f1c8dcfbb0fe71225712e334e70d5"
EXPECTED_PROFILES = (
    "linear-positive",
    "linear-negative",
    "sinusoidal-slow",
    "piecewise-random-walk",
)
EXPECTED_SPANS = (5.0, 10.0, 20.0)
EXPECTED_STATIC = (-10.0, 0.0, 10.0)
EXPECTED_DROPOUTS = (0.0, 0.1)
HEX = frozenset("0123456789abcdef")


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
        or any(character not in HEX for character in normalized)
    ):
        raise ValueError(f"{name} must be a SHA256 digest")
    return normalized


@dataclass(frozen=True, slots=True)
class DynamicClockDriftPreregistration:
    upstream_commit: str
    parent_commit: str
    config_sha256: str
    audit_text_sha256: str
    audit_json_sha256: str
    scenario_count: int
    estimator_execution_count: int
    dynamic_profiles: tuple[str, ...]
    drift_spans_ms: tuple[float, ...]
    static_controls_ms: tuple[float, ...]
    visual_dropout_fractions: tuple[float, ...]
    repeat_count_per_scenario: int
    v1_overall_percent: float
    v2_overall_percent: float
    v2_stage_3_percent: int

    def __post_init__(self) -> None:
        if self.upstream_commit != EXPECTED_COMMIT:
            raise ValueError("unexpected OpenVINS upstream commit")
        if self.parent_commit != EXPECTED_PARENT:
            raise ValueError("unexpected parent evidence commit")

        for name in (
            "config_sha256",
            "audit_text_sha256",
            "audit_json_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name),
            )

        if self.scenario_count != 30:
            raise ValueError("unexpected dynamic-drift scenario count")
        if self.estimator_execution_count != 60:
            raise ValueError("unexpected estimator execution count")
        if self.dynamic_profiles != EXPECTED_PROFILES:
            raise ValueError("unexpected dynamic profile set")
        if self.drift_spans_ms != EXPECTED_SPANS:
            raise ValueError("unexpected drift spans")
        if self.static_controls_ms != EXPECTED_STATIC:
            raise ValueError("unexpected static controls")
        if self.visual_dropout_fractions != EXPECTED_DROPOUTS:
            raise ValueError("unexpected visual conditions")
        if self.repeat_count_per_scenario != 2:
            raise ValueError("unexpected repeat count")
        if self.v1_overall_percent != 100.0:
            raise ValueError("VeraNav v1 must remain complete")
        if self.v2_overall_percent != 35.0:
            raise ValueError(
                "preregistration must not advance v2 progress"
            )
        if self.v2_stage_3_percent != 0:
            raise ValueError(
                "preregistration must not advance stage 3"
            )


def load_dynamic_clock_drift_preregistration(
    manifest_path: str | Path,
    preregistration_path: str | Path,
    scenario_plan_path: str | Path,
) -> DynamicClockDriftPreregistration:
    manifest_file = Path(manifest_path)
    prereg_file = Path(preregistration_path)
    scenarios_file = Path(scenario_plan_path)

    for path in (
        manifest_file,
        prereg_file,
        scenarios_file,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    manifest = _mapping(
        json.loads(manifest_file.read_text(encoding="utf-8")),
        "manifest",
    )
    prereg = _mapping(
        json.loads(prereg_file.read_text(encoding="utf-8")),
        "preregistration",
    )

    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema")
    if prereg.get("schema_version") != 1:
        raise ValueError("unsupported preregistration schema")
    if manifest.get("experiment") != (
        "openvins-dynamic-clock-drift-pilot"
    ):
        raise ValueError("unexpected experiment")
    if manifest.get("analysis_only") is not True:
        raise ValueError("preregistration must be analysis-only")
    if manifest.get("new_estimator_execution") is not False:
        raise ValueError("preregistration must not execute estimator")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official source must remain unchanged")

    verification = _mapping(
        manifest.get("verification"),
        "verification",
    )
    for key in (
        "audit_hashes_verified",
        "generated_twice_byte_identical",
        "parent_evidence_verified",
        "progress_unchanged",
    ):
        if verification.get(key) is not True:
            raise ValueError(f"required verification failed: {key}")

    with scenarios_file.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        scenarios = list(csv.DictReader(stream))

    if len(scenarios) != 30:
        raise ValueError("scenario-plan row count mismatch")
    if sum(int(row["repeat_count"]) for row in scenarios) != 60:
        raise ValueError("scenario-plan execution total mismatch")

    design = _mapping(prereg.get("design"), "design")
    parent = _mapping(
        prereg.get("parent_evidence"),
        "parent_evidence",
    )
    progress = _mapping(prereg.get("progress"), "progress")
    sources = _mapping(manifest.get("source_inputs"), "source_inputs")

    return DynamicClockDriftPreregistration(
        upstream_commit=str(manifest["upstream_commit"]),
        parent_commit=str(parent["commit"]),
        config_sha256=sources.get("config_sha256"),
        audit_text_sha256=sources.get("audit_text_sha256"),
        audit_json_sha256=sources.get("audit_json_sha256"),
        scenario_count=int(design["scenario_count"]),
        estimator_execution_count=int(
            design["estimator_execution_count"]
        ),
        dynamic_profiles=tuple(design["dynamic_profiles"]),
        drift_spans_ms=tuple(
            float(value)
            for value in design["drift_spans_ms"]
        ),
        static_controls_ms=tuple(
            float(value)
            for value in design["static_controls_ms"]
        ),
        visual_dropout_fractions=tuple(
            float(value)
            for value in design["visual_dropout_fractions"]
        ),
        repeat_count_per_scenario=int(
            design["repeat_count_per_scenario"]
        ),
        v1_overall_percent=float(progress["v1_overall_percent"]),
        v2_overall_percent=float(progress["v2_overall_percent"]),
        v2_stage_3_percent=int(progress["v2_stage_3_percent"]),
    )


__all__ = [
    "DynamicClockDriftPreregistration",
    "load_dynamic_clock_drift_preregistration",
]
