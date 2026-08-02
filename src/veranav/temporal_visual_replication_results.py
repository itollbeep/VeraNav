"""Validation model for V2-E01b five-seed replication results."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
OFFSETS = (-20.0, -10.0, 10.0, 20.0)
DROPOUTS = (0.05, 0.10, 0.15, 0.20)
SEEDS = (20260801, 20260802, 20260803, 20260804, 20260805)
HEX = frozenset("0123456789abcdef")


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _sha256(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(character not in HEX for character in normalized):
        raise ValueError(f"{name} must be a SHA256 digest")
    return normalized


def _finite(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


@dataclass(frozen=True, slots=True)
class ReplicationCellSummary:
    offset_ms: float
    dropout_fraction: float
    seed_support_count: int
    replicated_supported: bool
    global_additive_mean_m: float
    global_additive_ci95_lower_m: float
    global_ratio_mean: float
    local_additive_mean_m: float
    local_additive_ci95_lower_m: float
    local_ratio_mean: float

    def __post_init__(self) -> None:
        if self.offset_ms not in OFFSETS:
            raise ValueError("unexpected offset")
        if self.dropout_fraction not in DROPOUTS:
            raise ValueError("unexpected dropout fraction")
        if not isinstance(self.seed_support_count, int) or isinstance(self.seed_support_count, bool):
            raise TypeError("seed support count must be an integer")
        if not 0 <= self.seed_support_count <= 5:
            raise ValueError("seed support count is outside [0,5]")
        for name in (
            "global_additive_mean_m",
            "global_additive_ci95_lower_m",
            "global_ratio_mean",
            "local_additive_mean_m",
            "local_additive_ci95_lower_m",
            "local_ratio_mean",
        ):
            _finite(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class TemporalVisualReplicationResults:
    upstream_commit: str
    preregistration_sha256: str
    evidence_audit_sha256: str
    replication_status: str
    physical_scenario_count: int
    estimator_execution_count: int
    seed_interaction_count: int
    cell_summaries: tuple[ReplicationCellSummary, ...]
    supported_cell_count: int
    v1_overall_percent: float
    v2_overall_percent: float

    def __post_init__(self) -> None:
        if self.upstream_commit != EXPECTED_COMMIT:
            raise ValueError("unexpected OpenVINS upstream commit")
        object.__setattr__(
            self,
            "preregistration_sha256",
            _sha256(self.preregistration_sha256, "preregistration_sha256"),
        )
        object.__setattr__(
            self,
            "evidence_audit_sha256",
            _sha256(self.evidence_audit_sha256, "evidence_audit_sha256"),
        )
        if self.replication_status not in {
            "replicated_supported",
            "partial_replication",
            "replication_not_supported",
        }:
            raise ValueError("unexpected replication status")
        if self.physical_scenario_count != 105:
            raise ValueError("unexpected physical scenario count")
        if self.estimator_execution_count != 134:
            raise ValueError("unexpected estimator execution count")
        if self.seed_interaction_count != 80:
            raise ValueError("unexpected seed interaction count")
        expected_cells = tuple((offset, dropout) for offset in OFFSETS for dropout in DROPOUTS)
        actual_cells = tuple((cell.offset_ms, cell.dropout_fraction) for cell in self.cell_summaries)
        if actual_cells != expected_cells:
            raise ValueError("cell summaries are missing or out of order")
        if self.supported_cell_count != sum(cell.replicated_supported for cell in self.cell_summaries):
            raise ValueError("supported cell count mismatch")
        if self.v1_overall_percent != 100.0:
            raise ValueError("VeraNav v1 must remain complete")
        if self.v2_overall_percent != 35.0:
            raise ValueError("unexpected VeraNav v2 progress")


def load_temporal_visual_replication_results(
    manifest_path: str | Path,
    results_path: str | Path,
    evidence_audit_path: str | Path,
) -> TemporalVisualReplicationResults:
    manifest_file = Path(manifest_path)
    results_file = Path(results_path)
    audit_file = Path(evidence_audit_path)
    for path in (manifest_file, results_file, audit_file):
        if not path.is_file():
            raise FileNotFoundError(path)

    manifest = _mapping(json.loads(manifest_file.read_text(encoding="utf-8")), "manifest")
    results = _mapping(json.loads(results_file.read_text(encoding="utf-8")), "results")
    audit = _mapping(json.loads(audit_file.read_text(encoding="utf-8")), "evidence_audit")

    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported result manifest schema")
    if results.get("schema_version") != 1:
        raise ValueError("unsupported result schema")
    if manifest.get("experiment") != "openvins-temporal-visual-interaction-replication":
        raise ValueError("unexpected experiment")
    if manifest.get("upstream_commit") != EXPECTED_COMMIT:
        raise ValueError("result manifest commit mismatch")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official OpenVINS source must remain unchanged")
    verification = _mapping(manifest.get("verification"), "verification")
    for key in (
        "five_seed_masks_distinct",
        "masks_equal_across_offsets",
        "masks_nested_within_seed",
        "physical_references_byte_identical",
        "preregistration_preceded_execution",
        "raw_measurement_fingerprints_identical",
        "resume_safe_execution_complete",
    ):
        if verification.get(key) is not True:
            raise ValueError(f"required verification failed: {key}")

    if audit.get("physical_scenario_count") != 105 or audit.get("execution_count") != 134:
        raise ValueError("evidence audit count mismatch")
    if audit.get("five_seed_masks_distinct") is not True:
        raise ValueError("evidence audit seed diversity failed")

    raw_cells = results.get("cell_summaries")
    raw_seed_rows = results.get("seed_interactions")
    if not isinstance(raw_cells, list) or not isinstance(raw_seed_rows, list):
        raise TypeError("result tables must be lists")
    if len(raw_seed_rows) != 80:
        raise ValueError("unexpected seed interaction row count")
    expected_seed_order = tuple(
        (seed, offset, dropout)
        for seed in SEEDS
        for offset in OFFSETS
        for dropout in DROPOUTS
    )
    actual_seed_order = tuple(
        (int(row["seed"]), float(row["offset_ms"]), float(row["dropout_fraction"]))
        for row in raw_seed_rows
    )
    if actual_seed_order != expected_seed_order:
        raise ValueError("seed interactions are missing or out of order")

    cells = tuple(
        ReplicationCellSummary(
            offset_ms=float(row["offset_ms"]),
            dropout_fraction=float(row["dropout_fraction"]),
            seed_support_count=int(row["seed_support_count"]),
            replicated_supported=bool(row["replicated_supported"]),
            global_additive_mean_m=float(row["global_additive_mean_m"]),
            global_additive_ci95_lower_m=float(row["global_additive_ci95_lower_m"]),
            global_ratio_mean=float(row["global_ratio_mean"]),
            local_additive_mean_m=float(row["local_additive_mean_m"]),
            local_additive_ci95_lower_m=float(row["local_additive_ci95_lower_m"]),
            local_ratio_mean=float(row["local_ratio_mean"]),
        )
        for row in raw_cells
    )
    progress = _mapping(results.get("project_progress"), "project_progress")

    return TemporalVisualReplicationResults(
        upstream_commit=str(manifest["upstream_commit"]),
        preregistration_sha256=manifest.get("preregistration_sha256"),
        evidence_audit_sha256=manifest.get("evidence_audit_sha256"),
        replication_status=str(results["replication_status"]),
        physical_scenario_count=int(audit["physical_scenario_count"]),
        estimator_execution_count=int(audit["execution_count"]),
        seed_interaction_count=len(raw_seed_rows),
        cell_summaries=cells,
        supported_cell_count=int(results["supported_cell_count"]),
        v1_overall_percent=float(progress["v1_overall_percent"]),
        v2_overall_percent=float(progress["v2_overall_percent"]),
    )


__all__ = [
    "ReplicationCellSummary",
    "TemporalVisualReplicationResults",
    "load_temporal_visual_replication_results",
]
