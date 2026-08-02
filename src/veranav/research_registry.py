"""Validation model for the VeraNav v2 research registry."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
_EXPECTED_CLAIM_IDS = (
    "V1-C01",
    "V1-C02",
    "V1-C03",
    "V1-C04",
    "V1-C05",
    "V1-C06",
    "V1-C07",
    "V1-C08",
)
_EXPECTED_HYPOTHESIS_IDS = (
    "V2-H01",
    "V2-H02",
    "V2-H03",
    "V2-H04",
    "V2-H05",
    "V2-H06",
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


def _finite_score(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 5.0:
        raise ValueError(f"{name} must be between zero and five")
    return number


@dataclass(frozen=True, slots=True)
class VerifiedResearchClaim:
    """One evidence-bound claim retained for future paper development."""

    claim_id: str
    title: str
    status: str
    evidence_level: str
    statement: str
    scope: str
    evidence_paths: tuple[str, ...]
    falsification_next_step: str

    def __post_init__(self) -> None:
        if self.claim_id not in _EXPECTED_CLAIM_IDS:
            raise ValueError("unexpected verified claim identifier")
        if self.status != "verified_single_trajectory":
            raise ValueError("verified claim has unexpected status")
        if self.evidence_level not in {
            "trace_level",
            "paired_experiment",
            "cross_experiment",
        }:
            raise ValueError("unexpected evidence level")
        for name in (
            "title",
            "statement",
            "scope",
            "falsification_next_step",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        if not self.evidence_paths:
            raise ValueError("verified claim requires evidence paths")
        if not all(path.strip() for path in self.evidence_paths):
            raise ValueError("evidence paths must not be empty")


@dataclass(frozen=True, slots=True)
class CandidateResearchHypothesis:
    """One preregistered VeraNav v2 research hypothesis."""

    hypothesis_id: str
    title: str
    status: str
    hypothesis: str
    experiment_id: str
    novelty_potential: float
    expected_information_gain: float
    practical_relevance: float
    implementation_feasibility: float
    priority_score: float
    success_criterion: str
    disconfirming_result: str

    def __post_init__(self) -> None:
        if self.hypothesis_id not in _EXPECTED_HYPOTHESIS_IDS:
            raise ValueError("unexpected hypothesis identifier")
        if self.status != "candidate_hypothesis":
            raise ValueError("candidate hypothesis has unexpected status")
        for name in (
            "title",
            "hypothesis",
            "experiment_id",
            "success_criterion",
            "disconfirming_result",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")

        for name in (
            "novelty_potential",
            "expected_information_gain",
            "practical_relevance",
            "implementation_feasibility",
            "priority_score",
        ):
            _finite_score(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class VeraNavResearchRegistry:
    """Validated research registry and v2 preregistration."""

    upstream_commit: str
    registry_config_sha256: str
    synthesis_manifest_sha256: str
    synthesis_results_sha256: str
    camera_measurement_fingerprint: str
    imu_measurement_fingerprint: str
    verified_claims: tuple[VerifiedResearchClaim, ...]
    candidate_hypotheses: tuple[CandidateResearchHypothesis, ...]
    v1_overall_percent: float
    v2_overall_percent: float

    def __post_init__(self) -> None:
        if self.upstream_commit != _EXPECTED_COMMIT:
            raise ValueError("unexpected OpenVINS upstream commit")

        for name in (
            "registry_config_sha256",
            "synthesis_manifest_sha256",
            "synthesis_results_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name),
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

        claim_ids = tuple(claim.claim_id for claim in self.verified_claims)
        if claim_ids != _EXPECTED_CLAIM_IDS:
            raise ValueError("verified claims are missing or out of order")

        hypothesis_ids = tuple(
            hypothesis.hypothesis_id
            for hypothesis in self.candidate_hypotheses
        )
        if hypothesis_ids != _EXPECTED_HYPOTHESIS_IDS:
            raise ValueError(
                "candidate hypotheses are missing or out of order"
            )

        if self.v1_overall_percent != 100.0:
            raise ValueError("VeraNav v1 must remain complete")
        if self.v2_overall_percent != 10.0:
            raise ValueError(
                "registry completion must initialize v2 at ten percent"
            )


def _claim(raw: Mapping[str, Any]) -> VerifiedResearchClaim:
    return VerifiedResearchClaim(
        claim_id=str(raw["claim_id"]),
        title=str(raw["title"]),
        status=str(raw["status"]),
        evidence_level=str(raw["evidence_level"]),
        statement=str(raw["statement"]),
        scope=str(raw["scope"]),
        evidence_paths=tuple(str(value) for value in raw["evidence_paths"]),
        falsification_next_step=str(raw["falsification_next_step"]),
    )


def _hypothesis(
    raw: Mapping[str, Any],
) -> CandidateResearchHypothesis:
    return CandidateResearchHypothesis(
        hypothesis_id=str(raw["hypothesis_id"]),
        title=str(raw["title"]),
        status=str(raw["status"]),
        hypothesis=str(raw["hypothesis"]),
        experiment_id=str(raw["experiment_id"]),
        novelty_potential=float(raw["novelty_potential"]),
        expected_information_gain=float(
            raw["expected_information_gain"]
        ),
        practical_relevance=float(raw["practical_relevance"]),
        implementation_feasibility=float(
            raw["implementation_feasibility"]
        ),
        priority_score=float(raw["priority_score"]),
        success_criterion=str(raw["success_criterion"]),
        disconfirming_result=str(raw["disconfirming_result"]),
    )


def load_research_registry(
    manifest_path: str | Path,
    verified_claims_path: str | Path,
    candidate_hypotheses_path: str | Path,
) -> VeraNavResearchRegistry:
    """Load and strictly validate the committed registry."""

    manifest_file = Path(manifest_path)
    claims_file = Path(verified_claims_path)
    hypotheses_file = Path(candidate_hypotheses_path)

    for path in (manifest_file, claims_file, hypotheses_file):
        if not path.is_file():
            raise FileNotFoundError(path)

    manifest = _mapping(
        json.loads(manifest_file.read_text(encoding="utf-8")),
        "manifest",
    )
    claims_root = _mapping(
        json.loads(claims_file.read_text(encoding="utf-8")),
        "verified_claims",
    )
    hypotheses_root = _mapping(
        json.loads(hypotheses_file.read_text(encoding="utf-8")),
        "candidate_hypotheses",
    )

    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported registry manifest schema")
    if manifest.get("experiment") != "veranav-v2-research-registry":
        raise ValueError("unexpected registry experiment")
    if manifest.get("upstream_commit") != _EXPECTED_COMMIT:
        raise ValueError("registry upstream commit mismatch")
    if manifest.get("official_source_modified") is not False:
        raise ValueError("official OpenVINS source must remain unchanged")
    if manifest.get("analysis_only") is not True:
        raise ValueError("registry must be analysis-only")

    verification = _mapping(
        manifest.get("verification"),
        "verification",
    )
    if verification.get("source_synthesis_hashes_verified") is not True:
        raise ValueError("source synthesis hashes must be verified")
    if verification.get("generated_twice_byte_identical") is not True:
        raise ValueError("registry generation must be deterministic")
    if verification.get("no_new_estimator_execution") is not True:
        raise ValueError("registry must not run the estimator")
    if verification.get("claim_boundaries_recorded") is not True:
        raise ValueError("claim boundaries must be recorded")

    if claims_root.get("schema_version") != 1:
        raise ValueError("unsupported verified-claim schema")
    if hypotheses_root.get("schema_version") != 1:
        raise ValueError("unsupported hypothesis schema")

    claims_raw = claims_root.get("claims")
    hypotheses_raw = hypotheses_root.get("hypotheses")
    if not isinstance(claims_raw, list):
        raise TypeError("claims must be a list")
    if not isinstance(hypotheses_raw, list):
        raise TypeError("hypotheses must be a list")

    source_inputs = _mapping(
        manifest.get("source_inputs"),
        "source_inputs",
    )
    measurement = _mapping(
        manifest.get("measurement_realization"),
        "measurement_realization",
    )
    progress = _mapping(
        manifest.get("project_progress"),
        "project_progress",
    )

    return VeraNavResearchRegistry(
        upstream_commit=str(manifest["upstream_commit"]),
        registry_config_sha256=manifest.get(
            "registry_config_sha256"
        ),
        synthesis_manifest_sha256=source_inputs.get(
            "synthesis_manifest_sha256"
        ),
        synthesis_results_sha256=source_inputs.get(
            "synthesis_results_sha256"
        ),
        camera_measurement_fingerprint=str(
            measurement["camera_fingerprint"]
        ),
        imu_measurement_fingerprint=str(
            measurement["imu_fingerprint"]
        ),
        verified_claims=tuple(_claim(raw) for raw in claims_raw),
        candidate_hypotheses=tuple(
            _hypothesis(raw) for raw in hypotheses_raw
        ),
        v1_overall_percent=float(progress["v1_overall_percent"]),
        v2_overall_percent=float(progress["v2_overall_percent"]),
    )


__all__ = [
    "CandidateResearchHypothesis",
    "VeraNavResearchRegistry",
    "VerifiedResearchClaim",
    "load_research_registry",
]
