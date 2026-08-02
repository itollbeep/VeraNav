"""Validation model for V2-E03 internal clock monitor results."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


EXPECTED_PARENT = "52da5a0f8014e35911befd4db7c4fae7f762c061"
EXPECTED_PREREG = "6a9573b7b8406d092f0ee48b6cf7655b63290497"
ALLOWED_STATUS = {
    "monitor_supported",
    "monitor_partial",
    "monitor_not_supported",
}
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
class InternalClockMonitorResults:
    status: str
    parent_commit: str
    preregistration_commit: str
    scenario_count: int
    static_false_positive_count: int
    early_warning_positive_detected_count: int
    early_warning_positive_positive_lead_count: int
    dynamic_secondary_detected_count: int
    threshold_count: int
    online_ground_truth_input_count: int
    new_estimator_execution: bool
    results_sha256: str
    v1_overall_percent: float
    v2_stage_4_percent: int
    v2_overall_percent: float

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_STATUS:
            raise ValueError("unexpected monitor status")
        if self.parent_commit != EXPECTED_PARENT:
            raise ValueError("unexpected parent commit")
        if self.preregistration_commit != EXPECTED_PREREG:
            raise ValueError("unexpected preregistration commit")
        if self.scenario_count != 30:
            raise ValueError("unexpected scenario count")
        if not 0 <= self.static_false_positive_count <= 6:
            raise ValueError("invalid static false-positive count")
        if not 0 <= self.early_warning_positive_detected_count <= 2:
            raise ValueError("invalid early-warning detection count")
        if not 0 <= self.early_warning_positive_positive_lead_count <= 2:
            raise ValueError("invalid positive-lead count")
        if not 0 <= self.dynamic_secondary_detected_count <= 22:
            raise ValueError("invalid secondary detection count")
        if self.threshold_count != 3:
            raise ValueError("unexpected threshold count")
        if self.online_ground_truth_input_count != 0:
            raise ValueError("online monitor must not use ground truth")
        if self.new_estimator_execution:
            raise ValueError("monitor analysis must not rerun estimator")
        object.__setattr__(
            self,
            "results_sha256",
            _sha256(self.results_sha256, "results_sha256"),
        )
        if self.v1_overall_percent != 100.0:
            raise ValueError("VeraNav v1 must remain complete")
        expected_success = self.status == "monitor_supported"
        if expected_success:
            if self.v2_stage_4_percent != 40:
                raise ValueError("supported monitor must advance stage 4 to 40%")
            if self.v2_overall_percent != 65.0:
                raise ValueError("supported monitor must advance v2 to 65%")
        else:
            if self.v2_stage_4_percent != 0:
                raise ValueError("non-supported monitor must keep stage 4 at 0%")
            if self.v2_overall_percent != 55.0:
                raise ValueError("non-supported monitor must keep v2 at 55%")


def load_internal_clock_monitor_results(
    results_path: str | Path,
    manifest_path: str | Path,
    scenario_results_path: str | Path,
    thresholds_path: str | Path,
) -> InternalClockMonitorResults:
    results_file = Path(results_path)
    manifest_file = Path(manifest_path)
    scenarios_file = Path(scenario_results_path)
    thresholds_file = Path(thresholds_path)

    for path in (
        results_file,
        manifest_file,
        scenarios_file,
        thresholds_file,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    results = _mapping(
        json.loads(results_file.read_text(encoding="utf-8")),
        "results",
    )
    manifest = _mapping(
        json.loads(manifest_file.read_text(encoding="utf-8")),
        "manifest",
    )

    if results.get("schema_version") != 1:
        raise ValueError("unsupported results schema")
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema")
    if results.get("experiment") != "openvins-internal-clock-monitor-pilot":
        raise ValueError("unexpected experiment")
    if manifest.get("experiment") != "openvins-internal-clock-monitor-pilot":
        raise ValueError("unexpected manifest experiment")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official source must remain unchanged")
    if manifest.get("preregistration_modified") is not False:
        raise ValueError("preregistration must remain unchanged")
    if manifest.get("parent_evidence_modified") is not False:
        raise ValueError("parent evidence must remain unchanged")
    if manifest.get("new_estimator_execution") is not False:
        raise ValueError("monitor analysis must not execute estimator")
    if manifest.get("online_ground_truth_input_count") != 0:
        raise ValueError("online ground-truth input count must be zero")

    verification = _mapping(manifest.get("verification"), "verification")
    for key in (
        "deterministic_evidence_verified",
        "importer_deterministic",
        "monitor_input_boundary_verified",
        "preregistration_preceded_analysis",
        "static_only_threshold_calibration_verified",
    ):
        if verification.get(key) is not True:
            raise ValueError(f"required verification failed: {key}")

    with scenarios_file.open("r", encoding="utf-8", newline="") as stream:
        scenario_rows = list(csv.DictReader(stream))
    with thresholds_file.open("r", encoding="utf-8", newline="") as stream:
        threshold_rows = list(csv.DictReader(stream))

    if len(scenario_rows) != 30:
        raise ValueError("scenario result row count mismatch")
    if len(threshold_rows) != 3:
        raise ValueError("threshold row count mismatch")

    progress = _mapping(results.get("progress"), "progress")
    source_inputs = _mapping(manifest.get("source_inputs"), "source_inputs")

    return InternalClockMonitorResults(
        status=str(results["monitor_status"]),
        parent_commit=str(results["parent_commit"]),
        preregistration_commit=str(results["preregistration_commit"]),
        scenario_count=int(results["scenario_count"]),
        static_false_positive_count=int(
            results["static_false_positive_count"]
        ),
        early_warning_positive_detected_count=int(
            results["early_warning_positive_detected_count"]
        ),
        early_warning_positive_positive_lead_count=int(
            results["early_warning_positive_positive_lead_count"]
        ),
        dynamic_secondary_detected_count=int(
            results["dynamic_secondary_detected_count"]
        ),
        threshold_count=len(threshold_rows),
        online_ground_truth_input_count=int(
            manifest["online_ground_truth_input_count"]
        ),
        new_estimator_execution=bool(
            manifest["new_estimator_execution"]
        ),
        results_sha256=source_inputs["results_sha256"],
        v1_overall_percent=float(progress["v1_overall_percent"]),
        v2_stage_4_percent=int(progress["v2_stage_4_percent"]),
        v2_overall_percent=float(progress["v2_overall_percent"]),
    )


__all__ = [
    "InternalClockMonitorResults",
    "load_internal_clock_monitor_results",
]
