"""Validation helpers for OpenVINS common-trajectory adapter records."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_HEX = frozenset("0123456789abcdef")
_EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"


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


def _metric(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number


@dataclass(frozen=True, slots=True, eq=False)
class OpenVinsSimulationRecord:
    """Validated position-level OpenVINS simulation integration result."""

    upstream_commit: str
    sample_count: int
    start_time_s: float
    end_time_s: float
    position_rmse_m: float
    position_mean_m: float
    position_max_m: float
    estimate_sha256: str
    reference_sha256: str
    adapter_binary_sha256: str

    def __post_init__(self) -> None:
        if self.upstream_commit != _EXPECTED_COMMIT:
            raise ValueError("unexpected OpenVINS upstream commit")
        if (
            not isinstance(self.sample_count, int)
            or isinstance(self.sample_count, bool)
            or self.sample_count < 2
        ):
            raise ValueError("sample_count must be an integer of at least two")

        start = float(self.start_time_s)
        end = float(self.end_time_s)
        if (
            not math.isfinite(start)
            or not math.isfinite(end)
            or end <= start
        ):
            raise ValueError("record timestamps must define a finite interval")

        rmse = _metric(self.position_rmse_m, "position_rmse_m")
        mean = _metric(self.position_mean_m, "position_mean_m")
        maximum = _metric(self.position_max_m, "position_max_m")
        if maximum < mean:
            raise ValueError("position_max_m must not be smaller than mean")

        object.__setattr__(self, "start_time_s", start)
        object.__setattr__(self, "end_time_s", end)
        object.__setattr__(self, "position_rmse_m", rmse)
        object.__setattr__(self, "position_mean_m", mean)
        object.__setattr__(self, "position_max_m", maximum)
        object.__setattr__(
            self,
            "estimate_sha256",
            _sha256(self.estimate_sha256, "estimate_sha256"),
        )
        object.__setattr__(
            self,
            "reference_sha256",
            _sha256(self.reference_sha256, "reference_sha256"),
        )
        object.__setattr__(
            self,
            "adapter_binary_sha256",
            _sha256(
                self.adapter_binary_sha256,
                "adapter_binary_sha256",
            ),
        )


def load_openvins_simulation_record(
    manifest_path: str | Path,
    metrics_path: str | Path,
) -> OpenVinsSimulationRecord:
    """Load and validate one committed OpenVINS adapter record."""

    manifest_file = Path(manifest_path)
    metrics_file = Path(metrics_path)

    if not manifest_file.is_file():
        raise FileNotFoundError(manifest_file)
    if not metrics_file.is_file():
        raise FileNotFoundError(metrics_file)

    manifest = _mapping(
        json.loads(manifest_file.read_text(encoding="utf-8")),
        "manifest",
    )
    metrics_root = _mapping(
        json.loads(metrics_file.read_text(encoding="utf-8")),
        "metrics file",
    )

    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported OpenVINS adapter manifest schema")
    if manifest.get("estimator") != "OpenVINS":
        raise ValueError("manifest estimator must be OpenVINS")
    if manifest.get("integration_scope") != (
        "v2.7-ros-free-simulation-position-adapter"
    ):
        raise ValueError("unexpected OpenVINS integration scope")
    if manifest.get("release_tag") != "v2.7":
        raise ValueError("OpenVINS adapter record must use v2.7")
    if manifest.get("upstream_commit") != _EXPECTED_COMMIT:
        raise ValueError("OpenVINS adapter commit mismatch")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official OpenVINS source must remain unchanged")
    if manifest.get("adapter_source_location") != "external-only":
        raise ValueError("GPL-linked adapter source must remain external")

    verification = _mapping(
        manifest.get("verification"),
        "verification",
    )
    for name in ("run_a", "run_b"):
        record = _mapping(verification.get(name), name)
        if record.get("status") != "PASS":
            raise ValueError(f"{name} must have PASS status")
    if verification.get("trajectory_outputs_byte_identical") is not True:
        raise ValueError("OpenVINS adapter outputs must be deterministic")
    if verification.get("output_schema") != (
        "veranav-position-trajectory-v1"
    ):
        raise ValueError("unexpected OpenVINS adapter output schema")
    if verification.get("frame_mapping") != (
        "openvins-global-xyz-to-veranav-ned"
    ):
        raise ValueError("unexpected OpenVINS frame mapping")

    outputs = _mapping(manifest.get("outputs"), "outputs")
    build = _mapping(manifest.get("adapter_build"), "adapter_build")

    if metrics_root.get("schema_version") != 1:
        raise ValueError("unsupported OpenVINS metrics schema")
    if metrics_root.get("estimator") != "OpenVINS":
        raise ValueError("metrics estimator must be OpenVINS")

    values = _mapping(metrics_root.get("metrics"), "metrics")

    return OpenVinsSimulationRecord(
        upstream_commit=manifest["upstream_commit"],
        sample_count=values.get("sample_count"),
        start_time_s=values.get("start_time_s"),
        end_time_s=values.get("end_time_s"),
        position_rmse_m=values.get("position_rmse_m"),
        position_mean_m=values.get("position_mean_m"),
        position_max_m=values.get("position_max_m"),
        estimate_sha256=outputs.get("estimate_sha256"),
        reference_sha256=outputs.get("reference_sha256"),
        adapter_binary_sha256=build.get("binary_sha256"),
    )


__all__ = [
    "OpenVinsSimulationRecord",
    "load_openvins_simulation_record",
]
