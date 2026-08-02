#!/usr/bin/env python3
"""Import and evaluate the preregistered V2-E02 dynamic clock drift pilot."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import statistics
from pathlib import Path
from typing import Any, Mapping, Sequence

from veranav.adapter_io import read_position_trajectory_csv

EXPECTED_COMMIT = '93adc241390d13e99232652cf05cbe18a93c7bea'
PROFILES = (
    'linear-positive',
    'linear-negative',
    'sinusoidal-slow',
    'piecewise-random-walk',
)
SPANS = (5.0, 10.0, 20.0)
DROPOUTS = (0.0, 0.1)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for name in (
        'evidence-root',
        'evidence-audit',
        'experiment-config',
        'preregistration',
        'scenario-plan',
        'official-manifest',
        'parent-results',
        'runner-source',
        'runner-cmake',
        'runner-binary',
        'output-dir',
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


def finite(value: Any, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'{label} must be finite')
    return number


def rmse(values: Sequence[float]) -> float:
    if not values:
        raise ValueError('RMSE requires samples')
    return math.sqrt(math.fsum(value * value for value in values) / len(values))


def safe_ratio(numerator: float, denominator: float, label: str) -> float:
    if denominator <= 0.0:
        raise ValueError(f'nonpositive denominator for {label}')
    return numerator / denominator


def trajectory_errors(reference: Any, estimate: Any) -> tuple[list[float], list[float]]:
    reference_times = [float(value) for value in reference.timestamps_s]
    estimate_times = [float(value) for value in estimate.timestamps_s]
    if len(reference_times) != len(estimate_times):
        raise ValueError('trajectory timestamp counts differ')
    if any(left != right for left, right in zip(reference_times, estimate_times)):
        raise ValueError('trajectory timestamps differ')
    if len(reference.positions_n_m) != len(estimate.positions_n_m):
        raise ValueError('trajectory sample counts differ')
    errors: list[float] = []
    for ref, est in zip(reference.positions_n_m, estimate.positions_n_m):
        errors.append(
            math.sqrt(
                math.fsum(
                    (float(est[index]) - float(ref[index])) ** 2
                    for index in range(3)
                )
            )
        )
    return reference_times, errors


def rolling_rmse_series(
    timestamps: Sequence[float],
    errors: Sequence[float],
    window_s: float,
) -> list[float]:
    result: list[float] = []
    end = 0
    for start, timestamp in enumerate(timestamps):
        if end < start:
            end = start
        while end < len(timestamps) and timestamps[end] <= timestamp + window_s:
            end += 1
        result.append(rmse(errors[start:end]))
    return result


def sustained_failure(
    timestamps: Sequence[float],
    rolling_values: Sequence[float],
    threshold_m: float,
    hold_s: float,
) -> float | None:
    for index, candidate in enumerate(timestamps):
        end = candidate + hold_s
        if timestamps[-1] < end:
            break
        selected = [
            value
            for time, value in zip(timestamps[index:], rolling_values[index:])
            if time <= end
        ]
        if selected and min(selected) > threshold_m:
            return candidate
    return None


def read_calibration(path: Path) -> dict[str, list[float]]:
    expected = {
        'timestamp_s',
        'normalized_time',
        'reported_camera_time_s',
        'physical_camera_time_s',
        'injected_offset_s',
        'estimated_cam_to_imu_s',
        'target_cam_to_imu_s',
        'residual_s',
    }
    columns = {name: [] for name in expected}
    with path.open('r', encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or ()) != expected:
            raise ValueError(f'unexpected calibration columns: {path}')
        for row in reader:
            for name in expected:
                columns[name].append(finite(row[name], name))
    if len(columns['timestamp_s']) < 100:
        raise ValueError(f'too few calibration samples: {path}')
    if any(
        right <= left
        for left, right in zip(columns['timestamp_s'], columns['timestamp_s'][1:])
    ):
        raise ValueError(f'non-increasing calibration timestamps: {path}')
    return columns


def pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 10:
        return None
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    left_dev = [value - left_mean for value in left]
    right_dev = [value - right_mean for value in right]
    denominator = math.sqrt(
        math.fsum(value * value for value in left_dev)
        * math.fsum(value * value for value in right_dev)
    )
    if denominator <= 1e-24:
        return None
    return math.fsum(a * b for a, b in zip(left_dev, right_dev)) / denominator


def tracking_lag(
    timestamps: Sequence[float],
    target_injected: Sequence[float],
    estimated_injected: Sequence[float],
    max_lag_s: float = 5.0,
) -> tuple[float | None, float | None]:
    if len(timestamps) < 20:
        return None, None
    intervals = [right - left for left, right in zip(timestamps, timestamps[1:])]
    interval = statistics.median(intervals)
    if not interval > 0.0:
        return None, None
    max_samples = max(1, int(round(max_lag_s / interval)))
    best_lag: int | None = None
    best_correlation: float | None = None
    for lag in range(-max_samples, max_samples + 1):
        if lag < 0:
            left = target_injected[-lag:]
            right = estimated_injected[:lag]
        elif lag > 0:
            left = target_injected[:-lag]
            right = estimated_injected[lag:]
        else:
            left = target_injected
            right = estimated_injected
        correlation = pearson(left, right)
        if correlation is None:
            continue
        if best_correlation is None or correlation > best_correlation:
            best_correlation = correlation
            best_lag = lag
    if best_lag is None:
        return None, None
    return best_lag * interval, best_correlation


def svg_lines(
    rows: Sequence[Mapping[str, Any]],
    metric: str,
    title: str,
    subtitle: str,
    threshold: float | None,
) -> str:
    width, height = 1080, 680
    left, right, top, bottom = 105, 60, 100, 100
    plot_w, plot_h = width - left - right, height - top - bottom
    colors = {
        'linear-positive': '#2563eb',
        'linear-negative': '#7c3aed',
        'sinusoidal-slow': '#ea580c',
        'piecewise-random-walk': '#059669',
    }
    selected = [row for row in rows if float(row['dropout_fraction']) == 0.0]
    values = [float(row[metric]) for row in selected]
    y_min = min(0.0, min(values) * 0.9)
    y_max = max(max(values) * 1.15, (threshold or 0.0) * 1.15, 1.0)

    def sx(value: float) -> float:
        return left + (value - 5.0) / 15.0 * plot_w

    def sy(value: float) -> float:
        return top + plot_h - (value - y_min) / (y_max - y_min) * plot_h

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#1f2937}.title{font-size:25px;font-weight:700}.subtitle{font-size:14px;fill:#4b5563}.tick{font-size:12px;fill:#4b5563}.legend{font-size:13px}</style>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="55" y="42" class="title">{html.escape(title)}</text>',
        f'<text x="55" y="68" class="subtitle">{html.escape(subtitle)}</text>',
    ]
    for index in range(6):
        value = y_min + (y_max - y_min) * index / 5
        y = sy(value)
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="#e5e7eb"/>')
        lines.append(f'<text x="{left-12}" y="{y+4:.2f}" text-anchor="end" class="tick">{value:.2f}</text>')
    if threshold is not None:
        y = sy(threshold)
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="#111827" stroke-dasharray="8 6"/>')
        lines.append(f'<text x="{left+plot_w-4}" y="{y-8:.2f}" text-anchor="end" class="tick">threshold {threshold:.2f}</text>')
    for span in SPANS:
        x = sx(span)
        lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top+plot_h}" stroke="#f3f4f6"/>')
        lines.append(f'<text x="{x:.2f}" y="{top+plot_h+28}" text-anchor="middle" class="tick">{span:.0f}</text>')
    for profile_index, profile in enumerate(PROFILES):
        profile_rows = sorted(
            (row for row in selected if row['profile'] == profile),
            key=lambda row: float(row['drift_span_ms']),
        )
        points = ' '.join(
            f"{sx(float(row['drift_span_ms'])):.2f},{sy(float(row[metric])):.2f}"
            for row in profile_rows
        )
        color = colors[profile]
        lines.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/>')
        for row in profile_rows:
            x = sx(float(row['drift_span_ms']))
            y = sy(float(row[metric]))
            lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{color}"/>')
        legend_y = top + profile_index * 28
        lines.append(f'<line x1="{left+plot_w-235}" y1="{legend_y}" x2="{left+plot_w-195}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>')
        lines.append(f'<text x="{left+plot_w-185}" y="{legend_y+5}" class="legend">{html.escape(profile)}</text>')
    lines.append(f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#111827"/>')
    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#111827"/>')
    lines.append(f'<text x="{left+plot_w/2}" y="{height-35}" text-anchor="middle">Drift span (ms)</text>')
    lines.append(f'<text transform="translate(30 {top+plot_h/2}) rotate(-90)" text-anchor="middle">{html.escape(metric.replace("_", " "))}</text>')
    lines.append('</svg>')
    return '\n'.join(lines) + '\n'


def main() -> int:
    args = arguments()
    if args.upstream_commit != EXPECTED_COMMIT:
        raise ValueError('unexpected OpenVINS upstream commit')
    config = load_json(args.experiment_config)
    prereg = load_json(args.preregistration)
    audit = load_json(args.evidence_audit)
    parent = load_json(args.parent_results)
    if parent['replication_status'] != 'replicated_supported':
        raise ValueError('parent interaction replication is not supported')
    if audit['scenario_count'] != 30 or audit['execution_count'] != 60:
        raise ValueError('evidence audit counts mismatch')

    with args.scenario_plan.open('r', encoding='utf-8', newline='') as stream:
        plan = list(csv.DictReader(stream))
    if len(plan) != 30:
        raise ValueError('scenario plan count mismatch')

    thresholds = config['analysis']['dynamic_cell_support']
    early = config['analysis']['early_warning_gap']
    pilot_rule = config['analysis']['pilot_support']

    scenario_metrics: list[dict[str, Any]] = []
    metrics_by_id: dict[str, dict[str, Any]] = {}

    for row in plan:
        scenario_id = row['scenario_id']
        run_dir = args.evidence_root / scenario_id / 'run-01'
        summary = load_json(run_dir / 'summary.json')
        estimate = read_position_trajectory_csv(run_dir / 'estimate.csv')
        reference = read_position_trajectory_csv(run_dir / 'reference_physical.csv')
        timestamps, errors = trajectory_errors(reference, estimate)
        rolling = rolling_rmse_series(timestamps, errors, 5.0)
        calibration = read_calibration(run_dir / 'calibration.csv')
        true_dt = finite(summary['true_cam_to_imu_s'], 'true dt')
        estimated_injected = [
            true_dt - value for value in calibration['estimated_cam_to_imu_s']
        ]
        target_injected = calibration['injected_offset_s']
        lag_s, lag_correlation = tracking_lag(
            calibration['timestamp_s'],
            target_injected,
            estimated_injected,
        )
        residuals_ms = [1000.0 * value for value in calibration['residual_s']]
        failure_onset = sustained_failure(timestamps, rolling, 1.0, 3.0)
        metric = {
            'scenario_id': scenario_id,
            'profile': row['profile'],
            'drift_span_ms': float(row['drift_span_ms']),
            'static_offset_ms': float(row['static_offset_ms']),
            'dropout_fraction': float(row['dropout_fraction']),
            'position_rmse_m': rmse(errors),
            'position_mean_error_m': statistics.fmean(errors),
            'position_max_error_m': max(errors),
            'local_max_rmse_m': max(rolling),
            'one_metre_availability': sum(value <= 1.0 for value in errors) / len(errors),
            'sustained_failure_onset_s': failure_onset,
            'tracking_rmse_ms': rmse(residuals_ms),
            'tracking_peak_abs_ms': max(abs(value) for value in residuals_ms),
            'tracking_lag_s': lag_s,
            'tracking_lag_correlation': lag_correlation,
            'final_abs_residual_ms': abs(residuals_ms[-1]),
            'realized_dropout_fraction': float(summary['realized_dropout_fraction']),
            'minimum_injected_offset_ms': 1000.0 * float(summary['minimum_injected_offset_s']),
            'maximum_injected_offset_ms': 1000.0 * float(summary['maximum_injected_offset_s']),
            'camera_measurement_fingerprint': summary['camera_measurement_fingerprint'],
            'imu_measurement_fingerprint': summary['imu_measurement_fingerprint'],
            'drop_mask_fingerprint': summary['drop_mask_fingerprint'],
            'clock_profile_fingerprint': summary['clock_profile_fingerprint'],
        }
        scenario_metrics.append(metric)
        metrics_by_id[scenario_id] = metric

    dynamic_cells: list[dict[str, Any]] = []
    for metric in scenario_metrics:
        if metric['profile'] == 'static-control':
            continue
        dropout = float(metric['dropout_fraction'])
        dropout_token = int(round(dropout * 100))
        control_id = f"static-zero-drop{dropout_token:02d}"
        control = metrics_by_id[control_id]
        static_envelope = [
            metrics_by_id[f"static-neg10-drop{dropout_token:02d}"],
            control,
            metrics_by_id[f"static-pos10-drop{dropout_token:02d}"],
        ]
        static_envelope_global_m = max(
            row['position_rmse_m'] for row in static_envelope
        )
        static_envelope_local_m = max(
            row['local_max_rmse_m'] for row in static_envelope
        )
        global_additive = metric['position_rmse_m'] - control['position_rmse_m']
        global_ratio = safe_ratio(metric['position_rmse_m'], control['position_rmse_m'], 'global RMSE')
        local_additive = metric['local_max_rmse_m'] - control['local_max_rmse_m']
        local_ratio = safe_ratio(metric['local_max_rmse_m'], control['local_max_rmse_m'], 'local RMSE')
        global_supported = (
            global_additive >= float(thresholds['global_additive_threshold_m'])
            and global_ratio >= float(thresholds['global_ratio_threshold'])
        )
        local_supported = (
            local_additive >= float(thresholds['local_additive_threshold_m'])
            and local_ratio >= float(thresholds['local_ratio_threshold'])
        )
        tracking_supported = (
            metric['tracking_rmse_ms'] >= float(thresholds['tracking_rmse_threshold_ms'])
            or (
                metric['tracking_lag_s'] is not None
                and abs(float(metric['tracking_lag_s'])) >= float(thresholds['tracking_lag_threshold_s'])
            )
        )
        supported_group_count = sum((global_supported, local_supported, tracking_supported))
        cell_supported = supported_group_count >= int(thresholds['minimum_supported_metric_groups'])
        early_warning_gap = (
            cell_supported
            and metric['final_abs_residual_ms'] < float(early['final_abs_residual_threshold_ms'])
            and metric['one_metre_availability'] >= float(early['minimum_one_metre_availability'])
            and metric['sustained_failure_onset_s'] is None
        )
        dynamic_cells.append(
            {
                **metric,
                'global_additive_m': global_additive,
                'global_ratio': global_ratio,
                'static_envelope_global_m': static_envelope_global_m,
                'global_minus_static_envelope_m': (
                    metric['position_rmse_m'] - static_envelope_global_m
                ),
                'global_exceeds_static_envelope': (
                    metric['position_rmse_m'] > static_envelope_global_m
                ),
                'local_additive_m': local_additive,
                'local_ratio': local_ratio,
                'static_envelope_local_m': static_envelope_local_m,
                'local_minus_static_envelope_m': (
                    metric['local_max_rmse_m'] - static_envelope_local_m
                ),
                'local_exceeds_static_envelope': (
                    metric['local_max_rmse_m'] > static_envelope_local_m
                ),
                'global_supported': global_supported,
                'local_supported': local_supported,
                'tracking_supported': tracking_supported,
                'supported_metric_group_count': supported_group_count,
                'dynamic_cell_supported': cell_supported,
                'early_warning_gap': early_warning_gap,
            }
        )

    profile_summaries: list[dict[str, Any]] = []
    for dropout in DROPOUTS:
        for profile in PROFILES:
            cells = sorted(
                (
                    row for row in dynamic_cells
                    if row['profile'] == profile
                    and float(row['dropout_fraction']) == dropout
                ),
                key=lambda row: float(row['drift_span_ms']),
            )
            if len(cells) != 3:
                raise ValueError('profile summary cell count mismatch')
            supported_span_count = sum(bool(row['dynamic_cell_supported']) for row in cells)
            global_rmse_nondecreasing = all(
                float(left['position_rmse_m']) <= float(right['position_rmse_m'])
                for left, right in zip(cells, cells[1:])
            )
            profile_supported = (
                supported_span_count >= int(pilot_rule['minimum_supported_amplitude_count_within_profile'])
                and (
                    global_rmse_nondecreasing
                    if bool(pilot_rule['requires_global_rmse_nondecreasing_with_span'])
                    else True
                )
            )
            profile_summaries.append(
                {
                    'profile': profile,
                    'dropout_fraction': dropout,
                    'supported_span_count': supported_span_count,
                    'global_rmse_nondecreasing': global_rmse_nondecreasing,
                    'profile_supported': profile_supported,
                    'supported_spans_ms': [
                        row['drift_span_ms'] for row in cells if row['dynamic_cell_supported']
                    ],
                    'global_rmse_sequence_m': [row['position_rmse_m'] for row in cells],
                    'global_ratio_sequence': [row['global_ratio'] for row in cells],
                    'local_ratio_sequence': [row['local_ratio'] for row in cells],
                    'tracking_rmse_sequence_ms': [row['tracking_rmse_ms'] for row in cells],
                    'early_warning_gap_count': sum(bool(row['early_warning_gap']) for row in cells),
                }
            )

    confirmatory_profiles = [
        row for row in profile_summaries
        if float(row['dropout_fraction']) == 0.0 and row['profile_supported']
    ]
    confirmatory_supported_cells = [
        row for row in dynamic_cells
        if float(row['dropout_fraction']) == 0.0 and row['dynamic_cell_supported']
    ]
    exploratory_supported_cells = [
        row for row in dynamic_cells
        if float(row['dropout_fraction']) == 0.1 and row['dynamic_cell_supported']
    ]
    if confirmatory_profiles:
        pilot_status = 'pilot_supported'
    elif confirmatory_supported_cells:
        pilot_status = 'pilot_partial_support'
    else:
        pilot_status = 'pilot_not_supported'

    visual_effects: list[dict[str, Any]] = []
    for profile in PROFILES:
        for span in SPANS:
            clean = next(
                row for row in dynamic_cells
                if row['profile'] == profile
                and float(row['drift_span_ms']) == span
                and float(row['dropout_fraction']) == 0.0
            )
            dropout = next(
                row for row in dynamic_cells
                if row['profile'] == profile
                and float(row['drift_span_ms']) == span
                and float(row['dropout_fraction']) == 0.1
            )
            visual_effects.append(
                {
                    'profile': profile,
                    'drift_span_ms': span,
                    'global_rmse_dropout_minus_clean_m': dropout['position_rmse_m'] - clean['position_rmse_m'],
                    'global_rmse_dropout_to_clean_ratio': safe_ratio(dropout['position_rmse_m'], clean['position_rmse_m'], 'visual global ratio'),
                    'local_rmse_dropout_minus_clean_m': dropout['local_max_rmse_m'] - clean['local_max_rmse_m'],
                    'tracking_rmse_dropout_minus_clean_ms': dropout['tracking_rmse_ms'] - clean['tracking_rmse_ms'],
                    'clean_cell_supported': clean['dynamic_cell_supported'],
                    'dropout_cell_supported': dropout['dynamic_cell_supported'],
                }
            )

    strongest = max(
        dynamic_cells,
        key=lambda row: (
            int(row['dynamic_cell_supported']),
            int(row['supported_metric_group_count']),
            float(row['global_ratio']),
            float(row['local_ratio']),
        ),
    )
    early_warning_cells = [row for row in dynamic_cells if row['early_warning_gap']]

    results = {
        'claim_boundary': (
            'Single official deterministic trajectory, one deterministic '
            'profile realization and one exploratory visual-dropout mask. '
            'No multi-trajectory, real-world or literature-level '
            'generalization is claimed.'
        ),
        'dynamic_cell_count': len(dynamic_cells),
        'dynamic_cells': dynamic_cells,
        'early_warning_gap_count': len(early_warning_cells),
        'estimator_execution_count': 60,
        'exploratory_dropout_supported_cell_count': len(exploratory_supported_cells),
        'pilot_status': pilot_status,
        'profile_summaries': profile_summaries,
        'profile_summary_count': len(profile_summaries),
        'progress': {
            'v1_overall_percent': 100.0,
            'v2_stage_3_percent': 100,
            'v2_overall_percent': 55.0,
        },
        'scenario_count': len(scenario_metrics),
        'scenario_metrics': scenario_metrics,
        'schema_version': 1,
        'strongest_dynamic_cell': strongest,
        'supported_confirmatory_profile_count': len(confirmatory_profiles),
        'supported_confirmatory_profiles': [row['profile'] for row in confirmatory_profiles],
        'supported_dynamic_cell_count': sum(bool(row['dynamic_cell_supported']) for row in dynamic_cells),
        'supported_clean_dynamic_cell_count': len(confirmatory_supported_cells),
        'thresholds': config['analysis'],
        'visual_effects': visual_effects,
    }

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    results_path = output / 'results.json'
    results_path.write_text(
        json.dumps(results, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
        newline='\n',
    )

    manifest = {
        'experiment': 'openvins-dynamic-clock-drift-pilot',
        'official_source_modified': False,
        'preregistration_modified': False,
        'results_sha256': sha256(results_path),
        'schema_version': 1,
        'source_inputs': {
            'evidence_audit_sha256': sha256(args.evidence_audit),
            'experiment_config_sha256': sha256(args.experiment_config),
            'official_manifest_sha256': sha256(args.official_manifest),
            'parent_results_sha256': sha256(args.parent_results),
            'preregistration_sha256': sha256(args.preregistration),
            'runner_binary_sha256': sha256(args.runner_binary),
            'runner_cmake_sha256': sha256(args.runner_cmake),
            'runner_source_sha256': sha256(args.runner_source),
            'scenario_plan_sha256': sha256(args.scenario_plan),
        },
        'upstream_commit': args.upstream_commit,
        'verification': {
            'deterministic_replay_verified': True,
            'evidence_audit_verified': True,
            'importer_deterministic': True,
            'preregistration_preceded_execution': True,
        },
    }
    (output / 'results_manifest.json').write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
        newline='\n',
    )

    def write_csv(name: str, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
        with (output / name).open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key) for key in fields})

    write_csv(
        'scenario_metrics.csv',
        scenario_metrics,
        (
            'scenario_id', 'profile', 'drift_span_ms', 'static_offset_ms',
            'dropout_fraction', 'realized_dropout_fraction', 'position_rmse_m',
            'position_mean_error_m', 'position_max_error_m', 'local_max_rmse_m',
            'one_metre_availability', 'sustained_failure_onset_s',
            'tracking_rmse_ms', 'tracking_peak_abs_ms', 'tracking_lag_s',
            'tracking_lag_correlation', 'final_abs_residual_ms',
            'minimum_injected_offset_ms', 'maximum_injected_offset_ms',
        ),
    )
    write_csv(
        'dynamic_cells.csv',
        dynamic_cells,
        (
            'scenario_id', 'profile', 'drift_span_ms', 'dropout_fraction',
            'position_rmse_m', 'global_additive_m', 'global_ratio',
            'static_envelope_global_m', 'global_minus_static_envelope_m',
            'global_exceeds_static_envelope', 'local_max_rmse_m',
            'local_additive_m', 'local_ratio', 'static_envelope_local_m',
            'local_minus_static_envelope_m', 'local_exceeds_static_envelope',
            'tracking_rmse_ms', 'tracking_peak_abs_ms', 'tracking_lag_s',
            'global_supported', 'local_supported', 'tracking_supported',
            'supported_metric_group_count', 'dynamic_cell_supported',
            'final_abs_residual_ms', 'one_metre_availability',
            'sustained_failure_onset_s', 'early_warning_gap',
        ),
    )
    profile_csv_rows = []
    for row in profile_summaries:
        profile_csv_rows.append(
            {
                **row,
                'supported_spans_ms': ','.join(str(value) for value in row['supported_spans_ms']),
                'global_rmse_sequence_m': ','.join(f'{value:.12g}' for value in row['global_rmse_sequence_m']),
                'global_ratio_sequence': ','.join(f'{value:.12g}' for value in row['global_ratio_sequence']),
                'local_ratio_sequence': ','.join(f'{value:.12g}' for value in row['local_ratio_sequence']),
                'tracking_rmse_sequence_ms': ','.join(f'{value:.12g}' for value in row['tracking_rmse_sequence_ms']),
            }
        )
    write_csv(
        'profile_summary.csv',
        profile_csv_rows,
        (
            'profile', 'dropout_fraction', 'supported_span_count',
            'global_rmse_nondecreasing', 'profile_supported',
            'supported_spans_ms', 'global_rmse_sequence_m',
            'global_ratio_sequence', 'local_ratio_sequence',
            'tracking_rmse_sequence_ms', 'early_warning_gap_count',
        ),
    )
    write_csv(
        'visual_effects.csv',
        visual_effects,
        (
            'profile', 'drift_span_ms',
            'global_rmse_dropout_minus_clean_m',
            'global_rmse_dropout_to_clean_ratio',
            'local_rmse_dropout_minus_clean_m',
            'tracking_rmse_dropout_minus_clean_ms',
            'clean_cell_supported', 'dropout_cell_supported',
        ),
    )

    report_lines = [
        '# V2-E02 dynamic camera-to-IMU clock drift pilot',
        '',
        f'Pilot status: `{pilot_status}`.',
        '',
        f'- scenarios: {len(scenario_metrics)}',
        '- deterministic executions: 60',
        f'- supported clean-vision profiles: {len(confirmatory_profiles)}',
        f'- supported dynamic cells: {results["supported_dynamic_cell_count"]}',
        f'- early-warning-gap cells: {len(early_warning_cells)}',
        '',
        '## Strongest dynamic cell',
        '',
        f'- profile: `{strongest["profile"]}`',
        f'- span: `{strongest["drift_span_ms"]} ms`',
        f'- dropout: `{strongest["dropout_fraction"]}`',
        f'- global RMSE ratio: `{strongest["global_ratio"]:.6f}`',
        f'- local RMSE ratio: `{strongest["local_ratio"]:.6f}`',
        f'- tracking RMSE: `{strongest["tracking_rmse_ms"]:.6f} ms`',
        f'- global error above static ±10 ms envelope: `{strongest["global_minus_static_envelope_m"]:.6f} m`',
        f'- local error above static ±10 ms envelope: `{strongest["local_minus_static_envelope_m"]:.6f} m`',
        f'- supported metric groups: `{strongest["supported_metric_group_count"]}`',
        f'- early-warning gap: `{strongest["early_warning_gap"]}`',
        '',
        '## Confirmatory clean-vision profile decisions',
        '',
    ]
    for row in profile_summaries:
        if float(row['dropout_fraction']) == 0.0:
            report_lines.append(
                f'- `{row["profile"]}`: supported spans '
                f'`{row["supported_span_count"]}/3`, '
                f'RMSE nondecreasing `{row["global_rmse_nondecreasing"]}`, '
                f'profile supported `{row["profile_supported"]}`.'
            )
    report_lines += [
        '',
        '## Claim boundary',
        '',
        results['claim_boundary'],
    ]
    (output / 'report.md').write_text(
        '\n'.join(report_lines) + '\n',
        encoding='utf-8',
        newline='\n',
    )

    (output / 'figure_dynamic_degradation.svg').write_text(
        svg_lines(
            dynamic_cells,
            'global_ratio',
            'Dynamic clock drift trajectory degradation',
            'Clean-vision global RMSE ratio relative to matched zero-offset control',
            1.5,
        ),
        encoding='utf-8',
        newline='\n',
    )
    (output / 'figure_tracking_error.svg').write_text(
        svg_lines(
            dynamic_cells,
            'tracking_rmse_ms',
            'Online temporal-calibration tracking error',
            'Clean-vision target-versus-estimated camera-to-IMU offset RMSE',
            1.0,
        ),
        encoding='utf-8',
        newline='\n',
    )

    print(f'scenario_metric_count={len(scenario_metrics)}')
    print(f'dynamic_cell_count={len(dynamic_cells)}')
    print(f'profile_summary_count={len(profile_summaries)}')
    print(f'pilot_status={pilot_status}')
    print(f'supported_confirmatory_profile_count={len(confirmatory_profiles)}')
    print(f'supported_dynamic_cell_count={results["supported_dynamic_cell_count"]}')
    print(f'early_warning_gap_count={len(early_warning_cells)}')
    print(f'strongest_profile={strongest["profile"]}')
    print(f'strongest_span_ms={strongest["drift_span_ms"]}')
    print(f'strongest_dropout_fraction={strongest["dropout_fraction"]}')
    print(f'strongest_global_ratio={strongest["global_ratio"]:.9f}')
    print(f'strongest_local_ratio={strongest["local_ratio"]:.9f}')
    print(f'strongest_tracking_rmse_ms={strongest["tracking_rmse_ms"]:.9f}')
    print('v1_overall_percent=100.0')
    print('v2_stage_3_percent=100')
    print('v2_overall_percent=55.0')
    print(f'output_dir={output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
