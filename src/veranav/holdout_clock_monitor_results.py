"""Validation model for V2-E04 holdout monitor results."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

EXPECTED_PREREG = 'c793d14ac3359fa4555178aeb74a4e198b9531d2'
EXPECTED_UPSTREAM = '93adc241390d13e99232652cf05cbe18a93c7bea'
ALLOWED_STATUS = {'holdout_monitor_supported', 'holdout_monitor_not_supported'}
HEX = frozenset('0123456789abcdef')


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f'{name} must be a mapping')
    return value


def _sha256(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f'{name} must be a string')
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(character not in HEX for character in normalized):
        raise ValueError(f'{name} must be a SHA256 digest')
    return normalized


@dataclass(frozen=True, slots=True)
class HoldoutClockMonitorResults:
    status: str
    preregistration_commit: str
    scenario_count: int
    static_false_positive_count: int
    primary_challenge_degradation_eligible_count: int
    primary_challenge_detected_count: int
    primary_challenge_positive_lead_count: int
    dynamic_detected_count: int
    results_sha256: str
    v1_overall_percent: float
    v2_stage_4_percent: int
    v2_overall_percent: float

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_STATUS:
            raise ValueError('unexpected holdout status')
        if self.preregistration_commit != EXPECTED_PREREG:
            raise ValueError('unexpected preregistration commit')
        if self.scenario_count != 30:
            raise ValueError('unexpected scenario count')
        if not 0 <= self.static_false_positive_count <= 6:
            raise ValueError('invalid static false-positive count')
        if not 0 <= self.primary_challenge_degradation_eligible_count <= 4:
            raise ValueError('invalid primary eligibility count')
        if not 0 <= self.primary_challenge_detected_count <= 4:
            raise ValueError('invalid primary detection count')
        if not 0 <= self.primary_challenge_positive_lead_count <= 4:
            raise ValueError('invalid primary lead count')
        if not 0 <= self.dynamic_detected_count <= 24:
            raise ValueError('invalid dynamic detection count')
        object.__setattr__(self, 'results_sha256', _sha256(self.results_sha256, 'results_sha256'))
        if self.v1_overall_percent != 100.0:
            raise ValueError('VeraNav v1 must remain complete')
        if self.status == 'holdout_monitor_supported':
            if self.v2_stage_4_percent != 40 or self.v2_overall_percent != 65.0:
                raise ValueError('supported progress mismatch')
        else:
            if self.v2_stage_4_percent != 0 or self.v2_overall_percent != 55.0:
                raise ValueError('non-supported progress mismatch')


def load_holdout_clock_monitor_results(
    results_path: str | Path,
    manifest_path: str | Path,
    scenario_results_path: str | Path,
    evidence_audit_path: str | Path,
) -> HoldoutClockMonitorResults:
    paths = [Path(results_path), Path(manifest_path), Path(scenario_results_path), Path(evidence_audit_path)]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    results = _mapping(json.loads(paths[0].read_text(encoding='utf-8')), 'results')
    manifest = _mapping(json.loads(paths[1].read_text(encoding='utf-8')), 'manifest')
    audit = _mapping(json.loads(paths[3].read_text(encoding='utf-8')), 'audit')
    if results.get('schema_version') != 1 or manifest.get('schema_version') != 1:
        raise ValueError('unsupported schema')
    if results.get('experiment') != 'openvins-holdout-clock-monitor-validation':
        raise ValueError('unexpected experiment')
    if manifest.get('upstream_commit') != EXPECTED_UPSTREAM:
        raise ValueError('unexpected upstream commit')
    if manifest.get('official_source_modified') is not False:
        raise ValueError('official source must remain unchanged')
    if manifest.get('preregistration_modified') is not False:
        raise ValueError('preregistration must remain unchanged')
    if manifest.get('online_ground_truth_input_count') != 0:
        raise ValueError('online monitor must not use ground truth')
    verification = _mapping(manifest.get('verification'), 'verification')
    for key in (
        'candidate_rule_frozen_before_execution',
        'deterministic_replay_verified',
        'holdout_seeds_disjoint_from_discovery',
        'importer_deterministic',
        'monitor_input_boundary_verified',
    ):
        if verification.get(key) is not True:
            raise ValueError(f'required verification failed: {key}')
    if verification.get('threshold_recalibration_performed') is not False:
        raise ValueError('threshold recalibration was performed')
    with paths[2].open('r', encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 30:
        raise ValueError('scenario result row count mismatch')
    if audit.get('scenario_count') != 30 or audit.get('execution_count') != 60:
        raise ValueError('evidence audit count mismatch')
    progress = _mapping(results.get('progress'), 'progress')
    sources = _mapping(manifest.get('source_inputs'), 'source_inputs')
    return HoldoutClockMonitorResults(
        status=str(results['holdout_status']),
        preregistration_commit=str(results['preregistration_commit']),
        scenario_count=int(results['scenario_count']),
        static_false_positive_count=int(results['static_false_positive_count']),
        primary_challenge_degradation_eligible_count=int(results['primary_challenge_degradation_eligible_count']),
        primary_challenge_detected_count=int(results['primary_challenge_detected_count']),
        primary_challenge_positive_lead_count=int(results['primary_challenge_positive_lead_count']),
        dynamic_detected_count=int(results['dynamic_detected_count']),
        results_sha256=sources['results_sha256'],
        v1_overall_percent=float(progress['v1_overall_percent']),
        v2_stage_4_percent=int(progress['v2_stage_4_percent']),
        v2_overall_percent=float(progress['v2_overall_percent']),
    )


__all__ = ['HoldoutClockMonitorResults', 'load_holdout_clock_monitor_results']
