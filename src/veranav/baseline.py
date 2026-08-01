"""Metadata descriptors for external estimator baselines."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_ALLOWED_STATUSES = {"planned", "checkout-ready", "integrated"}


@dataclass(frozen=True, slots=True, eq=False)
class BaselineDescriptor:
    """Non-executable metadata for one external estimator baseline."""

    schema_version: int
    name: str
    estimator_family: str
    repository_url: str
    license_id: str
    integration_status: str
    revision_policy: str
    output_schema: str
    candidate_revision: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        for name in (
            "name",
            "estimator_family",
            "repository_url",
            "license_id",
            "integration_status",
            "revision_policy",
            "output_schema",
        ):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} must not be empty")
            object.__setattr__(self, name, value)
        if not self.repository_url.startswith("https://github.com/"):
            raise ValueError("repository_url must be an HTTPS GitHub URL")
        if self.integration_status not in _ALLOWED_STATUSES:
            raise ValueError(
                "integration_status must be planned, checkout-ready, or integrated"
            )
        if self.output_schema != "veranav-position-trajectory-v1":
            raise ValueError("output_schema must be veranav-position-trajectory-v1")
        if self.candidate_revision is not None:
            candidate = str(self.candidate_revision).strip()
            if not candidate:
                raise ValueError("candidate_revision must be nonempty when provided")
            object.__setattr__(self, "candidate_revision", candidate)


def load_baseline_descriptor(path: str | Path) -> BaselineDescriptor:
    """Load a baseline descriptor from JSON with an exact key set."""
    input_path = Path(path)
    if not input_path.is_file():
        raise ValueError(f"baseline descriptor does not exist: {input_path}")
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("baseline descriptor must be a JSON object")
    expected = {
        "schema_version",
        "name",
        "estimator_family",
        "repository_url",
        "license_id",
        "integration_status",
        "revision_policy",
        "output_schema",
        "candidate_revision",
    }
    if set(payload) != expected:
        raise ValueError("baseline descriptor keys do not match schema version 1")
    return BaselineDescriptor(**payload)


__all__ = ["BaselineDescriptor", "load_baseline_descriptor"]
