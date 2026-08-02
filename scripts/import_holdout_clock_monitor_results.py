#!/usr/bin/env python3
"""Import and evaluate V2-E04 holdout clock monitor evidence."""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import html
import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

EXPECTED_COMMIT = '93adc241390d13e99232652cf05cbe18a93c7bea'
EXPECTED_PREREG_COMMIT = 'c793d14ac3359fa4555178aeb74a4e198b9531d2'


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for name in (
        'evidence-root', 'evidence-audit', 'experiment-config',
        'preregistration', 'scenario-plan', 'official-manifest',
        'runner-source', 'runner-cmake', 'runner-binary', 'output-dir',
    ):
        parser.add_argument(f'--{name}', type=Path, required=True)
    parser.add_argument('--upstream-commit', required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise TypeError(f'{path} must contain a JSON object')
    return value


def finite(value: object, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'{label} must be finite')
    return number


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def read_positions(path: Path) -> tuple[list[float], list[tuple[float, float, float]]]:
    rows = read_csv(path)
    expected = {'timestamp_s', 'north_m', 'east_m', 'down_m'}
    if not rows or set(rows[0]) != expected:
        raise ValueError(f'unexpected trajectory columns: {path}')
    times = [finite(row['timestamp_s'], 'timestamp_s') for row in rows]
    positions = [
        (
            finite(row['north_m'], 'north_m'),
            finite(row['east_m'], 'east_m'),
            finite(row['down_m'], 'down_m'),
        )
        for row in rows
    ]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError(f'non-increasing trajectory: {path}')
    return times, positions


def read_estimated_offset_ms(path: Path) -> tuple[list[float], list[float]]:
    rows = read_csv(path)
    if not rows or 'timestamp_s' not in rows[0] or 'estimated_cam_to_imu_s' not in rows[0]:
        raise ValueError(f'unexpected calibration columns: {path}')
    times = [finite(row['timestamp_s'], 'timestamp_s') for row in rows]
    values = [1000.0 * finite(row['estimated_cam_to_imu_s'], 'estimated_cam_to_imu_s') for row in rows]
    if any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError(f'non-increasing calibration: {path}')
    return times, values


def position_errors(
    estimate_path: Path,
    reference_path: Path,
) -> tuple[list[float], list[float]]:
    est_times, estimate = read_positions(estimate_path)
    ref_times, reference = read_positions(reference_path)
    if est_times != ref_times:
        raise ValueError('estimate/reference timestamps differ')
    errors = [
        math.sqrt(
            (est[0] - ref[0]) ** 2
            + (est[1] - ref[1]) ** 2
            + (est[2] - ref[2]) ** 2
        )
        for est, ref in zip(estimate, reference)
    ]
    return est_times, errors


def rmse(values: Sequence[float]) -> float:
    if not values:
        raise ValueError('RMSE requires values')
    return math.sqrt(math.fsum(value * value for value in values) / len(values))


def causal_rolling_rmse(
    timestamps: Sequence[float],
    errors: Sequence[float],
    window_s: float,
) -> list[float]:
    squares = [value * value for value in errors]
    prefix = [0.0]
    for value in squares:
        prefix.append(prefix[-1] + value)
    output: list[float] = []
    for index, timestamp in enumerate(timestamps):
        start = bisect.bisect_left(timestamps, timestamp - window_s)
        total = prefix[index + 1] - prefix[start]
        output.append(math.sqrt(max(0.0, total / (index - start + 1))))
    return output


def causal_peak_to_peak(
    timestamps: Sequence[float],
    values: Sequence[float],
    window_s: float,
) -> list[float]:
    output: list[float] = []
    for index, timestamp in enumerate(timestamps):
        start = bisect.bisect_left(timestamps, timestamp - window_s)
        selected = values[start : index + 1]
        output.append(max(selected) - min(selected))
    return output


def first_sustained_time(
    timestamps: Sequence[float],
    active: Sequence[bool],
    persistence_s: float,
) -> float | None:
    start: float | None = None
    for timestamp, flag in zip(timestamps, active):
        if flag:
            if start is None:
                start = timestamp
            if timestamp - start >= persistence_s:
                return timestamp
        else:
            start = None
    return None


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def detection_svg(rows: Sequence[Mapping[str, Any]]) -> str:
    groups = (
        ('static-negative', 'Static controls'),
        ('primary-challenge', 'Primary challenges'),
        ('dynamic-secondary', 'Secondary dynamics'),
    )
    width, height = 1040, 620
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#1f2937}.title{font-size:25px;font-weight:700}.label{font-size:15px}.small{font-size:13px;fill:#4b5563}</style>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="55" y="45" class="title">V2-E04 holdout monitor coverage</text>',
        '<text x="55" y="72" class="small">Frozen 5 s peak-to-peak rule; no threshold recalibration</text>',
    ]
    left, plot_w = 120, 800
    for index, (label, title) in enumerate(groups):
        selected = [row for row in rows if row['label'] == label]
        detected = sum(bool(row['alert_detected']) for row in selected)
        total = len(selected)
        y = 125 + index * 140
        lines.append(f'<text x="{left}" y="{y-15}" class="label">{html.escape(title)}</text>')
        lines.append(f'<rect x="{left}" y="{y}" width="{plot_w}" height="70" fill="#e5e7eb" rx="5"/>')
        fill_w = plot_w * detected / max(total, 1)
        lines.append(f'<rect x="{left}" y="{y}" width="{fill_w:.2f}" height="70" fill="#4b5563" rx="5"/>')
        lines.append(f'<text x="{left+fill_w+12:.2f}" y="{y+44}" class="label">{detected}/{total}</text>')
    lines.append('<text x="120" y="585" class="small">Static detections are false positives; dynamic detections are coverage.</text>')
    lines.append('</svg>')
    return '\n'.join(lines) + '\n'


def lead_svg(rows: Sequence[Mapping[str, Any]]) -> str:
    primary = [row for row in rows if row['label'] == 'primary-challenge']
    width, height = 1160, 720
    maximum = max(
        max(float(row['alert_time_s'] or 0.0), float(row['degradation_onset_s'] or 0.0))
        for row in primary
    )
    maximum = max(10.0, maximum * 1.08)
    left, plot_w = 220, 860
    def sx(value: float) -> float:
        return left + value / maximum * plot_w
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#1f2937}.title{font-size:25px;font-weight:700}.label{font-size:13px}.small{font-size:12px;fill:#4b5563}</style>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="50" y="42" class="title">Primary challenge early-warning lead time</text>',
        '<text x="50" y="68" class="small">Circle: online alert; square: truth-only degradation onset</text>',
    ]
    for index in range(6):
        value = maximum * index / 5
        x = sx(value)
        lines.append(f'<line x1="{x:.2f}" y1="100" x2="{x:.2f}" y2="650" stroke="#e5e7eb"/>')
        lines.append(f'<text x="{x:.2f}" y="675" text-anchor="middle" class="small">{value:.1f}s</text>')
    for index, row in enumerate(primary):
        y = 145 + index * 125
        lines.append(f'<text x="{left-15}" y="{y+4}" text-anchor="end" class="label">{html.escape(str(row["scenario_id"]))}</text>')
        lines.append(f'<line x1="{left}" y1="{y}" x2="{left+plot_w}" y2="{y}" stroke="#9ca3af" stroke-width="3"/>')
        if row['alert_time_s'] is not None:
            x = sx(float(row['alert_time_s']))
            lines.append(f'<circle cx="{x:.2f}" cy="{y}" r="8" fill="#374151"/>')
        if row['degradation_onset_s'] is not None:
            x = sx(float(row['degradation_onset_s']))
            lines.append(f'<rect x="{x-7:.2f}" y="{y-7}" width="14" height="14" fill="#9ca3af"/>')
    lines.append('</svg>')
    return '\n'.join(lines) + '\n'


def main() -> int:
    args = arguments()
    if args.upstream_commit != EXPECTED_COMMIT:
        raise ValueError('unexpected OpenVINS upstream commit')
    config = load_json(args.experiment_config)
    prereg = load_json(args.preregistration)
    audit = load_json(args.evidence_audit)
    official = load_json(args.official_manifest)
    if audit['scenario_count'] != 30 or audit['execution_count'] != 60:
        raise ValueError('evidence audit count mismatch')
    if official['upstream']['commit'] != EXPECTED_COMMIT:
        raise ValueError('official manifest commit mismatch')
    if prereg['experiment'] != 'openvins-holdout-clock-monitor-validation':
        raise ValueError('unexpected preregistration experiment')

    plan = read_csv(args.scenario_plan)
    if len(plan) != 30:
        raise ValueError('scenario plan count mismatch')

    monitor = config['candidate_monitor']
    threshold_ms = float(monitor['threshold_ms'])
    monitor_window_s = float(monitor['monitor_window_s'])
    persistence_s = float(monitor['persistence_s'])
    warmup_s = float(monitor['warmup_s'])
    if monitor['threshold_recalibration_allowed'] is not False:
        raise ValueError('threshold recalibration must remain prohibited')
    degradation = config['degradation_reference']
    success = config['success_criteria']

    scenario_data: dict[str, dict[str, Any]] = {}
    for row in plan:
        scenario_id = row['scenario_id']
        run_dir = args.evidence_root / scenario_id / 'run-01'
        summary = load_json(run_dir / 'summary.json')
        timestamps, errors = position_errors(
            run_dir / 'estimate.csv', run_dir / 'reference_physical.csv'
        )
        rolling = causal_rolling_rmse(
            timestamps, errors, float(degradation['rolling_window_s'])
        )
        calib_times, estimated_ms = read_estimated_offset_ms(
            run_dir / 'calibration.csv'
        )
        feature = causal_peak_to_peak(calib_times, estimated_ms, monitor_window_s)
        alert = first_sustained_time(
            calib_times,
            [time >= warmup_s and value > threshold_ms for time, value in zip(calib_times, feature)],
            persistence_s,
        )
        scenario_data[scenario_id] = {
            'summary': summary,
            'timestamps': timestamps,
            'errors': errors,
            'rolling': rolling,
            'alert': alert,
            'feature_max_postwarmup_ms': max(
                value for time, value in zip(calib_times, feature) if time >= warmup_s
            ),
        }

    static_envelopes: dict[float, tuple[list[float], list[float]]] = {}
    for dropout in (0.0, 0.1):
        static_ids = [
            row['scenario_id'] for row in plan
            if row['label'] == 'static-negative'
            and float(row['dropout_fraction']) == dropout
        ]
        if len(static_ids) != 3:
            raise ValueError('expected three static controls per dropout')
        times = scenario_data[static_ids[0]]['timestamps']
        if any(scenario_data[item]['timestamps'] != times for item in static_ids[1:]):
            raise ValueError('static timelines differ')
        envelope = [
            max(scenario_data[item]['rolling'][index] for item in static_ids)
            for index in range(len(times))
        ]
        static_envelopes[dropout] = (times, envelope)

    rows: list[dict[str, Any]] = []
    for plan_row in plan:
        scenario_id = plan_row['scenario_id']
        data = scenario_data[scenario_id]
        dropout = float(plan_row['dropout_fraction'])
        degradation_onset: float | None = None
        if plan_row['label'] != 'static-negative':
            times, envelope = static_envelopes[dropout]
            if data['timestamps'] != times:
                raise ValueError('dynamic/static timeline mismatch')
            active = [
                value > baseline + float(
                    degradation['local_rmse_margin_above_matched_static_envelope_m']
                )
                for value, baseline in zip(data['rolling'], envelope)
            ]
            degradation_onset = first_sustained_time(
                times, active, float(degradation['hold_s'])
            )
        alert = data['alert']
        lead = (
            degradation_onset - alert
            if alert is not None and degradation_onset is not None
            else None
        )
        errors = data['errors']
        rows.append(
            {
                'scenario_id': scenario_id,
                'label': plan_row['label'],
                'profile': plan_row['profile'],
                'drift_span_ms': float(plan_row['drift_span_ms']),
                'static_offset_ms': float(plan_row['static_offset_ms']),
                'sinusoidal_phase_cycles': (
                    float(plan_row['sinusoidal_phase_cycles'])
                    if plan_row['sinusoidal_phase_cycles'].strip()
                    else None
                ),
                'profile_seed': (
                    int(plan_row['profile_seed'])
                    if plan_row['profile_seed'].strip()
                    else None
                ),
                'dropout_fraction': dropout,
                'alert_detected': alert is not None,
                'alert_time_s': alert,
                'degradation_eligible': degradation_onset is not None,
                'degradation_onset_s': degradation_onset,
                'lead_time_s': lead,
                'positive_lead_time': lead is not None and lead > 0.0,
                'feature_max_postwarmup_ms': data['feature_max_postwarmup_ms'],
                'position_rmse_m': rmse(errors),
                'position_mean_error_m': statistics.fmean(errors),
                'position_max_error_m': max(errors),
                'local_max_rmse_m': max(data['rolling']),
                'one_metre_availability': sum(value <= 1.0 for value in errors) / len(errors),
                'realized_dropout_fraction': float(data['summary']['realized_dropout_fraction']),
                'clock_profile_fingerprint': data['summary']['clock_profile_fingerprint'],
                'drop_mask_fingerprint': data['summary']['drop_mask_fingerprint'],
            }
        )

    static_rows = [row for row in rows if row['label'] == 'static-negative']
    primary_rows = [row for row in rows if row['label'] == 'primary-challenge']
    dynamic_rows = [row for row in rows if row['label'] != 'static-negative']
    secondary_rows = [row for row in rows if row['label'] == 'dynamic-secondary']

    static_fp = sum(row['alert_detected'] for row in static_rows)
    primary_eligible = sum(row['degradation_eligible'] for row in primary_rows)
    primary_detected = sum(row['alert_detected'] for row in primary_rows)
    primary_positive_lead = sum(row['positive_lead_time'] for row in primary_rows)
    dynamic_detected = sum(row['alert_detected'] for row in dynamic_rows)
    secondary_detected = sum(row['alert_detected'] for row in secondary_rows)

    supported = (
        static_fp == int(success['static_false_positive_scenario_count'])
        and primary_eligible >= int(success['primary_challenge_degradation_eligible_count_minimum'])
        and primary_detected == int(success['primary_challenge_detection_count'])
        and primary_positive_lead == int(success['primary_challenge_positive_lead_count'])
        and dynamic_detected >= int(success['dynamic_detection_count_minimum'])
    )
    status = 'holdout_monitor_supported' if supported else 'holdout_monitor_not_supported'
    stage4 = 40 if supported else 0
    overall = 65.0 if supported else 55.0

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    write_csv(
        output / 'scenario_results.csv',
        tuple(rows[0].keys()),
        rows,
    )

    results = {
        'dynamic_detected_count': dynamic_detected,
        'dynamic_scenario_count': len(dynamic_rows),
        'dynamic_secondary_detected_count': secondary_detected,
        'experiment': 'openvins-holdout-clock-monitor-validation',
        'holdout_status': status,
        'monitor': {
            'channel': monitor['channel'],
            'monitor_window_s': monitor_window_s,
            'persistence_s': persistence_s,
            'threshold_ms': threshold_ms,
            'warmup_s': warmup_s,
        },
        'preregistration_commit': EXPECTED_PREREG_COMMIT,
        'primary_challenge_count': len(primary_rows),
        'primary_challenge_degradation_eligible_count': primary_eligible,
        'primary_challenge_detected_count': primary_detected,
        'primary_challenge_positive_lead_count': primary_positive_lead,
        'primary_challenges': primary_rows,
        'progress': {
            'v1_overall_percent': 100.0,
            'v2_stage_4_percent': stage4,
            'v2_overall_percent': overall,
        },
        'scenario_count': len(rows),
        'schema_version': 1,
        'static_false_positive_count': static_fp,
        'static_scenario_count': len(static_rows),
        'success_criteria': success,
    }
    results_path = output / 'results.json'
    results_path.write_text(
        json.dumps(results, indent=2, sort_keys=True) + '\n',
        encoding='utf-8', newline='\n'
    )

    manifest = {
        'experiment': 'openvins-holdout-clock-monitor-validation',
        'new_estimator_execution': True,
        'official_source_modified': False,
        'online_ground_truth_input_count': 0,
        'preregistration_modified': False,
        'scenario_count': 30,
        'schema_version': 1,
        'source_inputs': {
            'evidence_audit_sha256': sha256(args.evidence_audit),
            'experiment_config_sha256': sha256(args.experiment_config),
            'official_manifest_sha256': sha256(args.official_manifest),
            'preregistration_sha256': sha256(args.preregistration),
            'results_sha256': sha256(results_path),
            'runner_binary_sha256': sha256(args.runner_binary),
            'runner_cmake_sha256': sha256(args.runner_cmake),
            'runner_source_sha256': sha256(args.runner_source),
            'scenario_plan_sha256': sha256(args.scenario_plan),
        },
        'upstream_commit': EXPECTED_COMMIT,
        'verification': {
            'candidate_rule_frozen_before_execution': True,
            'deterministic_replay_verified': True,
            'holdout_seeds_disjoint_from_discovery': True,
            'importer_deterministic': True,
            'monitor_input_boundary_verified': True,
            'threshold_recalibration_performed': False,
        },
    }
    (output / 'results_manifest.json').write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + '\n',
        encoding='utf-8', newline='\n'
    )
    (output / 'figure_detection_summary.svg').write_text(
        detection_svg(rows), encoding='utf-8', newline='\n'
    )
    (output / 'figure_primary_lead_time.svg').write_text(
        lead_svg(rows), encoding='utf-8', newline='\n'
    )

    report = [
        '# V2-E04 holdout clock monitor validation', '',
        f'- status: `{status}`',
        f'- static false positives: `{static_fp}/6`',
        f'- primary challenges degradation eligible: `{primary_eligible}/4`',
        f'- primary challenges detected: `{primary_detected}/4`',
        f'- primary positive lead: `{primary_positive_lead}/4`',
        f'- dynamic coverage: `{dynamic_detected}/24`',
        '', '## Frozen monitor', '',
        f'- channel: `{monitor["channel"]}`',
        f'- threshold: `{threshold_ms} ms`',
        f'- persistence: `{persistence_s} s`',
        f'- causal window: `{monitor_window_s} s`',
        '', '## Primary challenges', '',
    ]
    for row in primary_rows:
        report.append(
            f'- `{row["scenario_id"]}`: alert `{row["alert_time_s"]}`, '
            f'degradation `{row["degradation_onset_s"]}`, lead `{row["lead_time_s"]}`'
        )
    report.extend([
        '', '## Claim boundary', '',
        'This is perturbation-holdout validation on one official trajectory. '
        'It does not establish multi-trajectory or real-world deployment performance.',
    ])
    (output / 'report.md').write_text(
        '\n'.join(report) + '\n', encoding='utf-8', newline='\n'
    )

    print(f'holdout_status={status}')
    print(f'static_false_positive_count={static_fp}')
    print(f'primary_challenge_degradation_eligible_count={primary_eligible}')
    print(f'primary_challenge_detected_count={primary_detected}')
    print(f'primary_challenge_positive_lead_count={primary_positive_lead}')
    print(f'dynamic_detected_count={dynamic_detected}')
    print(f'dynamic_secondary_detected_count={secondary_detected}')
    for row in primary_rows:
        print(
            f"primary_challenge={row['scenario_id']}|alert={row['alert_time_s']}|"
            f"degradation={row['degradation_onset_s']}|lead={row['lead_time_s']}"
        )
    print(f'v2_stage_4_percent={stage4}')
    print(f'v2_overall_percent={overall:.1f}')
    print(f'output_dir={output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
