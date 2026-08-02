"""Validation model for the V2-E03 internal clock monitor preregistration."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_PARENT = "52da5a0f8014e35911befd4db7c4fae7f762c061"
EXPECTED_POSITIVES = (
    "sinusoidalslow-span05-drop00",
    "sinusoidalslow-span05-drop10",
)
EXPECTED_CHANNELS = (
    "estimated_offset_velocity_rms",
    "estimated_offset_acceleration_rms",
    "estimated_offset_peak_to_peak",
)
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
class InternalClockMonitorPreregistration:
    upstream_commit: str
    parent_commit: str
    config_sha256: str
    audit_text_sha256: str
    audit_json_sha256: str
    scenario_count: int
    static_negative_count: int
    early_warning_positive_count: int
    dynamic_secondary_count: int
    channels: tuple[str, ...]
    warmup_s: float
    monitor_window_s: float
    alert_channel_count: int
    alert_persistence_s: float
    v1_overall_percent: float
    v2_overall_percent: float
    v2_stage_4_percent: int

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
            raise ValueError("unexpected scenario count")
        if self.static_negative_count != 6:
            raise ValueError("unexpected static negative count")
        if self.early_warning_positive_count != 2:
            raise ValueError("unexpected early-warning positive count")
        if self.dynamic_secondary_count != 22:
            raise ValueError("unexpected dynamic secondary count")
        if self.channels != EXPECTED_CHANNELS:
            raise ValueError("unexpected monitor channels")
        if self.warmup_s != 10.0:
            raise ValueError("unexpected warmup")
        if self.monitor_window_s != 5.0:
            raise ValueError("unexpected monitor window")
        if self.alert_channel_count != 2:
            raise ValueError("unexpected alert channel count")
        if self.alert_persistence_s != 1.0:
            raise ValueError("unexpected alert persistence")
        if self.v1_overall_percent != 100.0:
            raise ValueError("VeraNav v1 must remain complete")
        if self.v2_overall_percent != 55.0:
            raise ValueError("preregistration must not advance v2")
        if self.v2_stage_4_percent != 0:
            raise ValueError("preregistration must not advance stage 4")


def load_internal_clock_monitor_preregistration(
    manifest_path: str | Path,
    preregistration_path: str | Path,
    scenario_labels_path: str | Path,
) -> InternalClockMonitorPreregistration:
    manifest_file = Path(manifest_path)
    prereg_file = Path(preregistration_path)
    labels_file = Path(scenario_labels_path)

    for path in (manifest_file, prereg_file, labels_file):
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
        "openvins-internal-clock-monitor-pilot"
    ):
        raise ValueError("unexpected experiment")
    if manifest.get("analysis_only") is not True:
        raise ValueError("monitor preregistration must be analysis-only")
    if manifest.get("new_estimator_execution") is not False:
        raise ValueError("monitor preregistration must not run estimator")
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

    with labels_file.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        labels = list(csv.DictReader(stream))

    if len(labels) != 30:
        raise ValueError("scenario label row count mismatch")

    counts: dict[str, int] = {}
    for row in labels:
        counts[row["label"]] = counts.get(row["label"], 0) + 1

    if counts != {
        "dynamic-secondary": 22,
        "early-warning-positive": 2,
        "static-negative": 6,
    }:
        raise ValueError(f"unexpected label counts: {counts}")

    positive_ids = tuple(
        sorted(
            row["scenario_id"]
            for row in labels
            if row["label"] == "early-warning-positive"
        )
    )
    if positive_ids != EXPECTED_POSITIVES:
        raise ValueError("unexpected early-warning positive scenarios")

    monitor = _mapping(prereg.get("monitor"), "monitor")
    parent = _mapping(
        prereg.get("parent_evidence"),
        "parent_evidence",
    )
    progress = _mapping(prereg.get("progress"), "progress")
    sources = _mapping(manifest.get("source_inputs"), "source_inputs")

    return InternalClockMonitorPreregistration(
        upstream_commit=str(manifest["upstream_commit"]),
        parent_commit=str(parent["commit"]),
        config_sha256=sources.get("config_sha256"),
        audit_text_sha256=sources.get("audit_text_sha256"),
        audit_json_sha256=sources.get("audit_json_sha256"),
        scenario_count=len(labels),
        static_negative_count=counts["static-negative"],
        early_warning_positive_count=counts[
            "early-warning-positive"
        ],
        dynamic_secondary_count=counts["dynamic-secondary"],
        channels=tuple(monitor["channels"]),
        warmup_s=float(monitor["warmup_s"]),
        monitor_window_s=float(monitor["monitor_window_s"]),
        alert_channel_count=int(monitor["alert_channel_count"]),
        alert_persistence_s=float(
            monitor["alert_persistence_s"]
        ),
        v1_overall_percent=float(progress["v1_overall_percent"]),
        v2_overall_percent=float(progress["v2_overall_percent"]),
        v2_stage_4_percent=int(progress["v2_stage_4_percent"]),
    )


__all__ = [
    "InternalClockMonitorPreregistration",
    "load_internal_clock_monitor_preregistration",
]
