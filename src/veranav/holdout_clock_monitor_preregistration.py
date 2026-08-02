"""Validation model for the V2-E04 holdout monitor preregistration."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_DISCOVERY = "5fedca7333116a935f09c3089f0164965663eacb"
EXPECTED_CHANNEL = "estimated_offset_peak_to_peak"
EXPECTED_THRESHOLD = 0.14729673122826897
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
class HoldoutClockMonitorPreregistration:
    upstream_commit: str
    discovery_commit: str
    config_sha256: str
    single_channel_audit_sha256: str
    temporal_overlap_audit_sha256: str
    scenario_count: int
    execution_count: int
    static_scenario_count: int
    primary_challenge_count: int
    dynamic_secondary_count: int
    monitor_channel: str
    threshold_ms: float
    persistence_s: float
    monitor_window_s: float
    warmup_s: float
    online_ground_truth_input_count: int
    v1_overall_percent: float
    v2_stage_4_percent: int
    v2_overall_percent: float

    def __post_init__(self) -> None:
        if self.upstream_commit != EXPECTED_COMMIT:
            raise ValueError("unexpected OpenVINS upstream commit")
        if self.discovery_commit != EXPECTED_DISCOVERY:
            raise ValueError("unexpected discovery commit")

        for name in (
            "config_sha256",
            "single_channel_audit_sha256",
            "temporal_overlap_audit_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name),
            )

        if self.scenario_count != 30:
            raise ValueError("unexpected scenario count")
        if self.execution_count != 60:
            raise ValueError("unexpected execution count")
        if self.static_scenario_count != 6:
            raise ValueError("unexpected static scenario count")
        if self.primary_challenge_count != 4:
            raise ValueError("unexpected primary challenge count")
        if self.dynamic_secondary_count != 20:
            raise ValueError("unexpected dynamic secondary count")
        if self.monitor_channel != EXPECTED_CHANNEL:
            raise ValueError("unexpected monitor channel")
        if abs(self.threshold_ms - EXPECTED_THRESHOLD) > 1e-15:
            raise ValueError("unexpected frozen threshold")
        if self.persistence_s != 3.0:
            raise ValueError("unexpected persistence")
        if self.monitor_window_s != 5.0:
            raise ValueError("unexpected monitor window")
        if self.warmup_s != 10.0:
            raise ValueError("unexpected warmup")
        if self.online_ground_truth_input_count != 0:
            raise ValueError("online monitor must not use ground truth")
        if self.v1_overall_percent != 100.0:
            raise ValueError("VeraNav v1 must remain complete")
        if self.v2_stage_4_percent != 0:
            raise ValueError("preregistration must not advance stage 4")
        if self.v2_overall_percent != 55.0:
            raise ValueError("preregistration must not advance v2")


def load_holdout_clock_monitor_preregistration(
    manifest_path: str | Path,
    preregistration_path: str | Path,
    scenario_plan_path: str | Path,
) -> HoldoutClockMonitorPreregistration:
    manifest_file = Path(manifest_path)
    prereg_file = Path(preregistration_path)
    plan_file = Path(scenario_plan_path)

    for path in (manifest_file, prereg_file, plan_file):
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
        "openvins-holdout-clock-monitor-validation"
    ):
        raise ValueError("unexpected experiment")
    if manifest.get("analysis_only") is not True:
        raise ValueError("preregistration must be analysis-only")
    if manifest.get("new_estimator_execution") is not False:
        raise ValueError("preregistration must not run estimator")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official source must remain unchanged")

    verification = _mapping(
        manifest.get("verification"),
        "verification",
    )
    for key in (
        "audit_hashes_verified",
        "candidate_rule_frozen",
        "generated_twice_byte_identical",
        "holdout_seeds_disjoint_from_discovery",
        "progress_unchanged",
    ):
        if verification.get(key) is not True:
            raise ValueError(f"required verification failed: {key}")

    with plan_file.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        rows = list(csv.DictReader(stream))

    if len(rows) != 30:
        raise ValueError("scenario plan row count mismatch")
    if sum(int(row["repeat_count"]) for row in rows) != 60:
        raise ValueError("execution count mismatch")
    if len({row["scenario_id"] for row in rows}) != 30:
        raise ValueError("scenario identifiers must be unique")

    label_counts: dict[str, int] = {}
    for row in rows:
        label_counts[row["label"]] = (
            label_counts.get(row["label"], 0) + 1
        )

    if label_counts != {
        "dynamic-secondary": 20,
        "primary-challenge": 4,
        "static-negative": 6,
    }:
        raise ValueError(f"unexpected label counts: {label_counts}")

    for row in rows:
        if int(row["dropout_seed"]) == 20260801:
            raise ValueError("discovery dropout seed reused")
        profile_seed = row["profile_seed"].strip()
        if profile_seed and int(profile_seed) == 20260802:
            raise ValueError("discovery profile seed reused")

    monitor = _mapping(prereg.get("candidate_monitor"), "candidate_monitor")
    discovery = _mapping(
        prereg.get("discovery_evidence"),
        "discovery_evidence",
    )
    progress = _mapping(prereg.get("progress"), "progress")
    sources = _mapping(manifest.get("source_inputs"), "source_inputs")

    return HoldoutClockMonitorPreregistration(
        upstream_commit=str(manifest["upstream_commit"]),
        discovery_commit=str(discovery["discovery_commit"]),
        config_sha256=sources["config_sha256"],
        single_channel_audit_sha256=sources[
            "single_channel_audit_sha256"
        ],
        temporal_overlap_audit_sha256=sources[
            "temporal_overlap_audit_sha256"
        ],
        scenario_count=len(rows),
        execution_count=sum(
            int(row["repeat_count"]) for row in rows
        ),
        static_scenario_count=label_counts["static-negative"],
        primary_challenge_count=label_counts["primary-challenge"],
        dynamic_secondary_count=label_counts["dynamic-secondary"],
        monitor_channel=str(monitor["channel"]),
        threshold_ms=float(monitor["threshold_ms"]),
        persistence_s=float(monitor["persistence_s"]),
        monitor_window_s=float(monitor["monitor_window_s"]),
        warmup_s=float(monitor["warmup_s"]),
        online_ground_truth_input_count=int(
            prereg["online_ground_truth_input_count"]
        ),
        v1_overall_percent=float(progress["v1_overall_percent"]),
        v2_stage_4_percent=int(progress["v2_stage_4_percent"]),
        v2_overall_percent=float(progress["v2_overall_percent"]),
    )


__all__ = [
    "HoldoutClockMonitorPreregistration",
    "load_holdout_clock_monitor_preregistration",
]
