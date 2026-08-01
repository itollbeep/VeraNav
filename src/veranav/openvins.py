"""Strict loader for committed OpenVINS reproduction evidence."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping


_HEX = frozenset("0123456789abcdef")


def _require_sha256(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")

    normalized = value.strip().lower()
    if (
        len(normalized) != 64
        or any(char not in _HEX for char in normalized)
    ):
        raise ValueError(f"{name} must be a SHA256 digest")

    return normalized


def _require_commit(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("upstream.commit must be a string")

    normalized = value.strip().lower()
    if (
        len(normalized) != 40
        or any(char not in _HEX for char in normalized)
    ):
        raise ValueError(
            "upstream.commit must be a 40-character Git SHA"
        )

    return normalized


@dataclass(frozen=True)
class OpenVinsReproductionEvidence:
    """Validated OpenVINS stable-release reproduction metadata."""

    release_tag: str
    upstream_commit: str
    source_archive_sha256: str
    configuration_sha256: str
    environment_profile: str
    repeatability_marker: str

    def __post_init__(self) -> None:
        if self.release_tag != "v2.7":
            raise ValueError("OpenVINS evidence must use release v2.7")

        object.__setattr__(
            self,
            "upstream_commit",
            _require_commit(self.upstream_commit),
        )
        object.__setattr__(
            self,
            "source_archive_sha256",
            _require_sha256(
                self.source_archive_sha256,
                "source_archive_sha256",
            ),
        )
        object.__setattr__(
            self,
            "configuration_sha256",
            _require_sha256(
                self.configuration_sha256,
                "configuration_sha256",
            ),
        )

        profile = str(self.environment_profile).strip()
        if not profile:
            raise ValueError("environment_profile must not be empty")
        object.__setattr__(
            self,
            "environment_profile",
            profile,
        )

        expected = "success! they all are the same!"
        if self.repeatability_marker != expected:
            raise ValueError(
                "unexpected OpenVINS repeatability marker"
            )


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def load_openvins_evidence(
    path: str | Path,
) -> OpenVinsReproductionEvidence:
    """Load and strictly validate a committed OpenVINS manifest."""

    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = _mapping(data, "manifest")

    if root.get("schema_version") != 1:
        raise ValueError("unsupported OpenVINS manifest schema")
    if root.get("estimator") != "OpenVINS":
        raise ValueError("manifest estimator must be OpenVINS")
    if root.get("reproduction_scope") != (
        "official-v2.7-ros-free-simulator"
    ):
        raise ValueError("unexpected OpenVINS reproduction scope")

    upstream = _mapping(root.get("upstream"), "upstream")
    configuration = _mapping(
        root.get("configuration"),
        "configuration",
    )
    build = _mapping(root.get("build"), "build")
    verification = _mapping(
        root.get("verification"),
        "verification",
    )

    for name in (
        "test_sim_repeat",
        "test_sim_meas",
        "run_simulation_a",
        "run_simulation_b",
    ):
        record = _mapping(verification.get(name), name)
        if record.get("status") != "PASS":
            raise ValueError(f"{name} must have PASS status")

    if configuration.get("enable_ros") is not False:
        raise ValueError("OpenVINS evidence must be ROS-free")
    if configuration.get(
        "official_configuration_modified"
    ) is not False:
        raise ValueError(
            "official configuration must remain unchanged"
        )
    if verification.get("official_source_modified") is not False:
        raise ValueError(
            "official OpenVINS source must remain unchanged"
        )
    if build.get("host_system_packages_modified") is not False:
        raise ValueError(
            "host system packages must remain unchanged"
        )

    repeat = _mapping(
        verification.get("test_sim_repeat"),
        "test_sim_repeat",
    )

    return OpenVinsReproductionEvidence(
        release_tag=upstream.get("release_tag"),
        upstream_commit=upstream.get("commit"),
        source_archive_sha256=upstream.get(
            "source_archive_sha256"
        ),
        configuration_sha256=configuration.get("sha256"),
        environment_profile=build.get(
            "environment_profile"
        ),
        repeatability_marker=repeat.get("required_marker"),
    )
