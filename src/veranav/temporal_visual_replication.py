"""Validation model for the V2-E01b replication preregistration."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_PARENT = "70c27e0957bd03eaa0a8a87f35d394d9b046241b"
EXPECTED_SEEDS = (
    20260801,
    20260802,
    20260803,
    20260804,
    20260805,
)
EXPECTED_OFFSETS = (-20.0, -10.0, 0.0, 10.0, 20.0)
EXPECTED_DROPOUTS = (0.0, 0.05, 0.1, 0.15, 0.2)
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
class TemporalVisualReplicationPreregistration:
    upstream_commit: str
    parent_commit: str
    config_sha256: str
    audit_text_sha256: str
    audit_json_sha256: str
    analytical_cell_count: int
    physical_scenario_count: int
    estimator_execution_count: int
    offsets_ms: tuple[float, ...]
    dropout_fractions: tuple[float, ...]
    seeds: tuple[int, ...]
    minimum_seed_support_count: int
    supported_flags: tuple[str, ...]
    v1_overall_percent: float
    v2_overall_percent: float

    def __post_init__(self) -> None:
        if self.upstream_commit != EXPECTED_COMMIT:
            raise ValueError("unexpected OpenVINS upstream commit")
        if self.parent_commit != EXPECTED_PARENT:
            raise ValueError("unexpected parent experiment commit")

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

        if self.analytical_cell_count != 125:
            raise ValueError("unexpected analytical cell count")
        if self.physical_scenario_count != 105:
            raise ValueError("unexpected physical scenario count")
        if self.estimator_execution_count != 134:
            raise ValueError("unexpected estimator execution count")
        if self.offsets_ms != EXPECTED_OFFSETS:
            raise ValueError("unexpected offset grid")
        if self.dropout_fractions != EXPECTED_DROPOUTS:
            raise ValueError("unexpected dropout grid")
        if self.seeds != EXPECTED_SEEDS:
            raise ValueError("unexpected seed set")
        if self.minimum_seed_support_count != 4:
            raise ValueError("unexpected seed support criterion")
        if self.supported_flags != (
            "local_rmse_supported",
            "rmse_supported",
        ):
            raise ValueError("unexpected parent supported flags")
        if self.v1_overall_percent != 100.0:
            raise ValueError("VeraNav v1 must remain complete")
        if self.v2_overall_percent != 20.0:
            raise ValueError(
                "preregistration must not advance v2 progress"
            )


def load_temporal_visual_replication_preregistration(
    manifest_path: str | Path,
    preregistration_path: str | Path,
    analysis_cells_path: str | Path,
    execution_plan_path: str | Path,
) -> TemporalVisualReplicationPreregistration:
    manifest_file = Path(manifest_path)
    prereg_file = Path(preregistration_path)
    cells_file = Path(analysis_cells_path)
    execution_file = Path(execution_plan_path)

    for path in (
        manifest_file,
        prereg_file,
        cells_file,
        execution_file,
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
        "openvins-temporal-visual-interaction-replication"
    ):
        raise ValueError("unexpected experiment")
    if manifest.get("analysis_only") is not True:
        raise ValueError("preregistration must be analysis-only")
    if manifest.get("new_estimator_execution") is not False:
        raise ValueError("preregistration must not run the estimator")
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

    with cells_file.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        cells = list(csv.DictReader(stream))
    with execution_file.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        executions = list(csv.DictReader(stream))

    if len(cells) != 125:
        raise ValueError("analysis-cell CSV row count mismatch")
    if len(executions) != 105:
        raise ValueError("execution-plan CSV row count mismatch")
    if sum(int(row["repeat_count"]) for row in executions) != 134:
        raise ValueError("execution-plan repeat total mismatch")

    design = _mapping(prereg.get("design"), "design")
    criteria = _mapping(
        prereg.get("replicated_support_criterion"),
        "replicated_support_criterion",
    )
    parent = _mapping(prereg.get("parent_result"), "parent_result")
    progress = _mapping(prereg.get("progress"), "progress")
    sources = _mapping(manifest.get("source_inputs"), "source_inputs")

    return TemporalVisualReplicationPreregistration(
        upstream_commit=str(manifest["upstream_commit"]),
        parent_commit=str(parent["commit"]),
        config_sha256=sources.get("config_sha256"),
        audit_text_sha256=sources.get("audit_text_sha256"),
        audit_json_sha256=sources.get("audit_json_sha256"),
        analytical_cell_count=int(design["analytical_cell_count"]),
        physical_scenario_count=int(
            design["physical_scenario_count"]
        ),
        estimator_execution_count=int(
            design["estimator_execution_count"]
        ),
        offsets_ms=tuple(float(value) for value in design["offsets_ms"]),
        dropout_fractions=tuple(
            float(value)
            for value in design["dropout_fractions"]
        ),
        seeds=tuple(int(value) for value in design["seeds"]),
        minimum_seed_support_count=int(
            criteria["minimum_seed_support_count"]
        ),
        supported_flags=tuple(parent["supported_flags"]),
        v1_overall_percent=float(progress["v1_overall_percent"]),
        v2_overall_percent=float(progress["v2_overall_percent"]),
    )


__all__ = [
    "TemporalVisualReplicationPreregistration",
    "load_temporal_visual_replication_preregistration",
]
