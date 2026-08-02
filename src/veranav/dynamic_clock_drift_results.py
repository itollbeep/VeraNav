"""Validation model for committed V2-E02 dynamic clock drift results."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

EXPECTED_COMMIT = '93adc241390d13e99232652cf05cbe18a93c7bea'
ALLOWED_STATUSES = {
    'pilot_supported',
    'pilot_partial_support',
    'pilot_not_supported',
}
HEX = frozenset('0123456789abcdef')


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f'{name} must be a mapping')
    return value


def _sha256(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f'{name} must be a string')
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(ch not in HEX for ch in normalized):
        raise ValueError(f'{name} must be a SHA256 digest')
    return normalized


@dataclass(frozen=True, slots=True)
class DynamicClockDriftResults:
    upstream_commit: str
    pilot_status: str
    scenario_count: int
    estimator_execution_count: int
    dynamic_cell_count: int
    profile_summary_count: int
    supported_dynamic_cell_count: int
    early_warning_gap_count: int
    results_sha256: str
    evidence_audit_sha256: str
    v1_overall_percent: float
    v2_stage_3_percent: int
    v2_overall_percent: float

    def __post_init__(self) -> None:
        if self.upstream_commit != EXPECTED_COMMIT:
            raise ValueError('unexpected OpenVINS upstream commit')
        if self.pilot_status not in ALLOWED_STATUSES:
            raise ValueError('unexpected dynamic-drift pilot status')
        if self.scenario_count != 30:
            raise ValueError('unexpected scenario count')
        if self.estimator_execution_count != 60:
            raise ValueError('unexpected execution count')
        if self.dynamic_cell_count != 24:
            raise ValueError('unexpected dynamic cell count')
        if self.profile_summary_count != 8:
            raise ValueError('unexpected profile summary count')
        if not 0 <= self.supported_dynamic_cell_count <= 24:
            raise ValueError('invalid supported dynamic cell count')
        if not 0 <= self.early_warning_gap_count <= self.supported_dynamic_cell_count:
            raise ValueError('invalid early-warning gap count')
        object.__setattr__(self, 'results_sha256', _sha256(self.results_sha256, 'results_sha256'))
        object.__setattr__(self, 'evidence_audit_sha256', _sha256(self.evidence_audit_sha256, 'evidence_audit_sha256'))
        if self.v1_overall_percent != 100.0:
            raise ValueError('VeraNav v1 must remain complete')
        if self.v2_stage_3_percent != 100:
            raise ValueError('completed pilot must finish stage 3')
        if self.v2_overall_percent != 55.0:
            raise ValueError('unexpected VeraNav v2 overall progress')


def load_dynamic_clock_drift_results(
    manifest_path: str | Path,
    results_path: str | Path,
    evidence_audit_path: str | Path,
) -> DynamicClockDriftResults:
    manifest_file = Path(manifest_path)
    results_file = Path(results_path)
    audit_file = Path(evidence_audit_path)
    for path in (manifest_file, results_file, audit_file):
        if not path.is_file():
            raise FileNotFoundError(path)
    manifest = _mapping(json.loads(manifest_file.read_text(encoding='utf-8')), 'manifest')
    results = _mapping(json.loads(results_file.read_text(encoding='utf-8')), 'results')
    audit = _mapping(json.loads(audit_file.read_text(encoding='utf-8')), 'audit')
    if manifest.get('schema_version') != 1 or results.get('schema_version') != 1:
        raise ValueError('unsupported result schema')
    if manifest.get('experiment') != 'openvins-dynamic-clock-drift-pilot':
        raise ValueError('unexpected experiment')
    if manifest.get('official_source_modified') is not False:
        raise ValueError('official source must remain unchanged')
    if manifest.get('preregistration_modified') is not False:
        raise ValueError('preregistration must remain unchanged')
    verification = _mapping(manifest.get('verification'), 'verification')
    for key in (
        'deterministic_replay_verified',
        'evidence_audit_verified',
        'importer_deterministic',
        'preregistration_preceded_execution',
    ):
        if verification.get(key) is not True:
            raise ValueError(f'required verification failed: {key}')
    source_inputs = _mapping(manifest.get('source_inputs'), 'source_inputs')
    actual_results_sha256 = hashlib.sha256(results_file.read_bytes()).hexdigest()
    if manifest.get('results_sha256') != actual_results_sha256:
        raise ValueError('results hash mismatch')
    if source_inputs.get('evidence_audit_sha256') != hashlib.sha256(
        audit_file.read_bytes()
    ).hexdigest():
        raise ValueError('evidence audit hash mismatch')
    return DynamicClockDriftResults(
        upstream_commit=str(manifest['upstream_commit']),
        pilot_status=str(results['pilot_status']),
        scenario_count=int(results['scenario_count']),
        estimator_execution_count=int(results['estimator_execution_count']),
        dynamic_cell_count=int(results['dynamic_cell_count']),
        profile_summary_count=int(results['profile_summary_count']),
        supported_dynamic_cell_count=int(results['supported_dynamic_cell_count']),
        early_warning_gap_count=int(results['early_warning_gap_count']),
        results_sha256=str(manifest['results_sha256']),
        evidence_audit_sha256=str(source_inputs['evidence_audit_sha256']),
        v1_overall_percent=float(results['progress']['v1_overall_percent']),
        v2_stage_3_percent=int(results['progress']['v2_stage_3_percent']),
        v2_overall_percent=float(results['progress']['v2_overall_percent']),
    )


__all__ = ['DynamicClockDriftResults', 'load_dynamic_clock_drift_results']
