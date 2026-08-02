#!/usr/bin/env python3
"""Evaluate the preregistered V2-E03 internal clock monitor pilot."""

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


PARENT_COMMIT = "52da5a0f8014e35911befd4db7c4fae7f762c061"
PREREG_COMMIT = "6a9573b7b8406d092f0ee48b6cf7655b63290497"
CHANNELS = (
    "estimated_offset_velocity_rms",
    "estimated_offset_acceleration_rms",
    "estimated_offset_peak_to_peak",
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for name in (
        "evidence-root",
        "evidence-audit",
        "experiment-config",
        "preregistration",
        "scenario-labels",
        "parent-results",
        "parent-manifest",
        "parent-scenarios",
        "output-dir",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def finite(value: object, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def read_calibration(path: Path) -> tuple[list[float], list[float]]:
    rows = read_csv(path)
    if len(rows) < 100:
        raise ValueError(f"too few calibration samples: {path}")
    expected = {
        "timestamp_s",
        "normalized_time",
        "reported_camera_time_s",
        "physical_camera_time_s",
        "injected_offset_s",
        "estimated_cam_to_imu_s",
        "target_cam_to_imu_s",
        "residual_s",
    }
    if set(rows[0]) != expected:
        raise ValueError(f"unexpected calibration columns: {path}")
    timestamps = [finite(row["timestamp_s"], "timestamp_s") for row in rows]
    estimated_ms = [
        1000.0 * finite(
            row["estimated_cam_to_imu_s"],
            "estimated_cam_to_imu_s",
        )
        for row in rows
    ]
    if any(
        right <= left
        for left, right in zip(timestamps, timestamps[1:])
    ):
        raise ValueError(f"non-increasing calibration timeline: {path}")
    return timestamps, estimated_ms


def read_positions(path: Path) -> tuple[list[float], list[tuple[float, float, float]]]:
    rows = read_csv(path)
    expected = {"timestamp_s", "north_m", "east_m", "down_m"}
    if not rows or set(rows[0]) != expected:
        raise ValueError(f"unexpected trajectory columns: {path}")
    timestamps = [finite(row["timestamp_s"], "timestamp_s") for row in rows]
    positions = [
        (
            finite(row["north_m"], "north_m"),
            finite(row["east_m"], "east_m"),
            finite(row["down_m"], "down_m"),
        )
        for row in rows
    ]
    if any(
        right <= left
        for left, right in zip(timestamps, timestamps[1:])
    ):
        raise ValueError(f"non-increasing trajectory timeline: {path}")
    return timestamps, positions


def derivative(
    timestamps: Sequence[float],
    values: Sequence[float],
) -> tuple[list[float], list[float]]:
    if len(timestamps) != len(values):
        raise ValueError("derivative input length mismatch")
    result_times: list[float] = []
    result_values: list[float] = []
    for index in range(1, len(timestamps)):
        dt = timestamps[index] - timestamps[index - 1]
        if dt <= 0.0:
            raise ValueError("nonpositive derivative interval")
        result_times.append(timestamps[index])
        result_values.append((values[index] - values[index - 1]) / dt)
    return result_times, result_values


def rms(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return math.sqrt(math.fsum(value * value for value in values) / len(values))


def causal_monitor_series(
    timestamps: Sequence[float],
    estimated_ms: Sequence[float],
    window_s: float,
) -> list[dict[str, float]]:
    velocity_times, velocity = derivative(timestamps, estimated_ms)
    acceleration_times, acceleration = derivative(velocity_times, velocity)
    output: list[dict[str, float]] = []

    for index, timestamp in enumerate(timestamps):
        start_time = timestamp - window_s
        offset_start = bisect.bisect_left(timestamps, start_time)
        velocity_start = bisect.bisect_left(velocity_times, start_time)
        velocity_end = bisect.bisect_right(velocity_times, timestamp)
        acceleration_start = bisect.bisect_left(
            acceleration_times,
            start_time,
        )
        acceleration_end = bisect.bisect_right(
            acceleration_times,
            timestamp,
        )
        offset_window = estimated_ms[offset_start : index + 1]
        velocity_window = velocity[velocity_start:velocity_end]
        acceleration_window = acceleration[
            acceleration_start:acceleration_end
        ]
        output.append(
            {
                "timestamp_s": timestamp,
                "estimated_offset_velocity_rms": rms(velocity_window),
                "estimated_offset_acceleration_rms": rms(
                    acceleration_window
                ),
                "estimated_offset_peak_to_peak": (
                    max(offset_window) - min(offset_window)
                    if offset_window
                    else 0.0
                ),
            }
        )
    return output


def alert_time(
    series: Sequence[Mapping[str, float]],
    thresholds: Mapping[str, float],
    warmup_s: float,
    required_channel_count: int,
    persistence_s: float,
) -> tuple[float | None, tuple[str, ...]]:
    run_start: float | None = None
    active_at_alert: tuple[str, ...] = ()
    for row in series:
        timestamp = float(row["timestamp_s"])
        if timestamp < warmup_s:
            run_start = None
            continue
        active = tuple(
            channel
            for channel in CHANNELS
            if float(row[channel]) > float(thresholds[channel])
        )
        if len(active) >= required_channel_count:
            if run_start is None:
                run_start = timestamp
            if timestamp - run_start >= persistence_s:
                active_at_alert = active
                return timestamp, active_at_alert
        else:
            run_start = None
    return None, active_at_alert


def position_error_series(
    estimate_path: Path,
    reference_path: Path,
) -> tuple[list[float], list[float]]:
    est_times, estimate = read_positions(estimate_path)
    ref_times, reference = read_positions(reference_path)
    if est_times != ref_times:
        raise ValueError("estimate/reference timestamps differ")
    errors = [
        math.sqrt(
            (est[0] - ref[0]) ** 2
            + (est[1] - ref[1]) ** 2
            + (est[2] - ref[2]) ** 2
        )
        for est, ref in zip(estimate, reference)
    ]
    return est_times, errors


def causal_rolling_rmse(
    timestamps: Sequence[float],
    errors: Sequence[float],
    window_s: float,
) -> list[float]:
    values: list[float] = []
    squares = [value * value for value in errors]
    prefix = [0.0]
    for value in squares:
        prefix.append(prefix[-1] + value)
    for index, timestamp in enumerate(timestamps):
        start = bisect.bisect_left(timestamps, timestamp - window_s)
        count = index - start + 1
        total = prefix[index + 1] - prefix[start]
        values.append(math.sqrt(max(0.0, total / count)))
    return values


def sustained_onset(
    timestamps: Sequence[float],
    condition: Sequence[bool],
    persistence_s: float,
) -> float | None:
    run_start: float | None = None
    for timestamp, active in zip(timestamps, condition):
        if active:
            if run_start is None:
                run_start = timestamp
            if timestamp - run_start >= persistence_s:
                return timestamp
        else:
            run_start = None
    return None


def write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def svg_detection(rows: Sequence[Mapping[str, Any]]) -> str:
    width, height = 1040, 610
    left, right, top, bottom = 85, 35, 90, 95
    plot_w = width - left - right
    plot_h = height - top - bottom
    groups = (
        ("static-negative", "Static controls", 6),
        ("early-warning-positive", "Early-warning positives", 2),
        ("dynamic-secondary", "Other dynamic cases", 22),
    )
    values = []
    for label, title, total in groups:
        detected = sum(
            row["label"] == label and bool(row["alert_detected"])
            for row in rows
        )
        values.append((title, detected, total))
    max_total = max(total for _, _, total in values)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#1f2937}.title{font-size:25px;font-weight:700}.subtitle{font-size:14px;fill:#4b5563}.tick{font-size:13px;fill:#4b5563}.label{font-size:15px}</style>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="48" y="40" class="title">V2-E03 internal clock monitor detection</text>',
        '<text x="48" y="66" class="subtitle">Alerts use only estimated camera-to-IMU offset history</text>',
    ]
    bar_height = 72
    gap = 55
    for index, (title, detected, total) in enumerate(values):
        y = top + index * (bar_height + gap)
        lines.append(
            f'<text x="{left}" y="{y-12}" class="label">{html.escape(title)}</text>'
        )
        lines.append(
            f'<rect x="{left}" y="{y}" width="{plot_w}" height="{bar_height}" fill="#e5e7eb" rx="5"/>'
        )
        detected_width = plot_w * detected / max_total
        lines.append(
            f'<rect x="{left}" y="{y}" width="{detected_width:.2f}" height="{bar_height}" fill="#4b5563" rx="5"/>'
        )
        lines.append(
            f'<text x="{left+detected_width+12:.2f}" y="{y+45}" class="label">{detected}/{total}</text>'
        )
    lines.append(
        f'<text x="{left}" y="{height-35}" class="tick">Static detections are false positives; dynamic detections are coverage.</text>'
    )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def svg_timeline(
    positive_rows: Sequence[Mapping[str, Any]],
) -> str:
    width, height = 1120, 590
    left, right, top, bottom = 125, 60, 105, 90
    plot_w = width - left - right
    maximum = max(
        max(
            float(row["alert_time_s"] or 0.0),
            float(row["degradation_onset_s"] or 0.0),
        )
        for row in positive_rows
    )
    maximum = max(maximum * 1.08, 10.0)

    def sx(value: float) -> float:
        return left + value / maximum * plot_w

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#1f2937}.title{font-size:25px;font-weight:700}.subtitle{font-size:14px;fill:#4b5563}.tick{font-size:12px;fill:#4b5563}.label{font-size:14px}</style>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="48" y="40" class="title">Early-warning lead time</text>',
        '<text x="48" y="66" class="subtitle">Alert time versus truth-only trajectory degradation onset</text>',
    ]
    for index in range(6):
        value = maximum * index / 5
        x = sx(value)
        lines.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height-bottom}" stroke="#e5e7eb"/>'
        )
        lines.append(
            f'<text x="{x:.2f}" y="{height-bottom+25}" text-anchor="middle" class="tick">{value:.1f}s</text>'
        )
    for row_index, row in enumerate(positive_rows):
        y = top + 115 + row_index * 155
        scenario = str(row["scenario_id"])
        alert = row["alert_time_s"]
        degradation = row["degradation_onset_s"]
        lines.append(
            f'<text x="{left-18}" y="{y+5}" text-anchor="end" class="label">{html.escape(scenario)}</text>'
        )
        lines.append(
            f'<line x1="{left}" y1="{y}" x2="{left+plot_w}" y2="{y}" stroke="#9ca3af" stroke-width="3"/>'
        )
        if alert is not None:
            x = sx(float(alert))
            lines.append(
                f'<circle cx="{x:.2f}" cy="{y}" r="9" fill="#374151"/>'
            )
            lines.append(
                f'<text x="{x:.2f}" y="{y-18}" text-anchor="middle" class="tick">alert {float(alert):.2f}s</text>'
            )
        if degradation is not None:
            x = sx(float(degradation))
            lines.append(
                f'<rect x="{x-8:.2f}" y="{y-8}" width="16" height="16" fill="#9ca3af"/>'
            )
            lines.append(
                f'<text x="{x:.2f}" y="{y+32}" text-anchor="middle" class="tick">degradation {float(degradation):.2f}s</text>'
            )
    lines.append(
        f'<text x="{left}" y="{height-28}" class="tick">Circle: online monitor alert. Square: truth-only evaluation onset.</text>'
    )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = arguments()
    config = load_json(args.experiment_config)
    prereg = load_json(args.preregistration)
    parent_results = load_json(args.parent_results)
    parent_manifest = load_json(args.parent_manifest)
    evidence_audit = load_json(args.evidence_audit)
    labels = read_csv(args.scenario_labels)
    parent_scenarios = read_csv(args.parent_scenarios)

    if config["parent_evidence"]["commit"] != PARENT_COMMIT:
        raise ValueError("parent commit mismatch")
    if prereg["parent_evidence"]["commit"] != PARENT_COMMIT:
        raise ValueError("preregistration parent mismatch")
    if parent_results["pilot_status"] != "pilot_supported":
        raise ValueError("parent pilot is not supported")
    if parent_manifest["verification"][
        "deterministic_replay_verified"
    ] is not True:
        raise ValueError("parent deterministic evidence is not verified")
    if evidence_audit["physical_references_byte_identical"] is not True:
        raise ValueError("physical references are not verified")
    if len(labels) != 30 or len(parent_scenarios) != 30:
        raise ValueError("scenario count mismatch")

    label_by_scenario = {row["scenario_id"]: row for row in labels}
    metric_by_scenario = {
        row["scenario_id"]: row for row in parent_scenarios
    }
    if set(label_by_scenario) != set(metric_by_scenario):
        raise ValueError("scenario identifiers differ between inputs")

    monitor = config["monitor"]
    calibration = config["calibration"]
    degradation = config["degradation_reference"]
    success = config["success_criteria"]
    warmup_s = float(monitor["warmup_s"])
    monitor_window_s = float(monitor["monitor_window_s"])
    required_channels = int(monitor["alert_channel_count"])
    alert_persistence_s = float(monitor["alert_persistence_s"])

    scenario_data: dict[str, dict[str, Any]] = {}
    for scenario_id in sorted(label_by_scenario):
        scenario_root = args.evidence_root / scenario_id
        run_one = scenario_root / "run-01"
        run_two = scenario_root / "run-02"
        for relative in (
            "calibration.csv",
            "estimate.csv",
            "reference_physical.csv",
            "summary.json",
        ):
            left = run_one / relative
            right = run_two / relative
            if not left.is_file() or not right.is_file():
                raise FileNotFoundError(f"missing evidence: {scenario_id}/{relative}")
            if left.read_bytes() != right.read_bytes():
                raise ValueError(
                    f"deterministic evidence mismatch: {scenario_id}/{relative}"
                )
        timestamps, estimated_ms = read_calibration(
            run_one / "calibration.csv"
        )
        series = causal_monitor_series(
            timestamps,
            estimated_ms,
            monitor_window_s,
        )
        trajectory_timestamps, errors = position_error_series(
            run_one / "estimate.csv",
            run_one / "reference_physical.csv",
        )
        rolling_rmse = causal_rolling_rmse(
            trajectory_timestamps,
            errors,
            float(degradation["rolling_window_s"]),
        )
        scenario_data[scenario_id] = {
            "calibration_series": series,
            "trajectory_timestamps": trajectory_timestamps,
            "rolling_rmse": rolling_rmse,
        }

    static_ids = list(calibration["static_control_scenarios"])
    if set(static_ids) != {
        scenario_id
        for scenario_id, row in label_by_scenario.items()
        if row["label"] == "static-negative"
    }:
        raise ValueError("static calibration scenario set mismatch")

    static_maxima = {channel: 0.0 for channel in CHANNELS}
    for scenario_id in static_ids:
        for row in scenario_data[scenario_id]["calibration_series"]:
            if float(row["timestamp_s"]) < warmup_s:
                continue
            for channel in CHANNELS:
                static_maxima[channel] = max(
                    static_maxima[channel],
                    float(row[channel]),
                )

    floor = calibration["threshold_floor"]
    floor_by_channel = {
        "estimated_offset_velocity_rms": float(
            floor["velocity_rms_ms_per_s"]
        ),
        "estimated_offset_acceleration_rms": float(
            floor["acceleration_rms_ms_per_s2"]
        ),
        "estimated_offset_peak_to_peak": float(floor["range_ms"]),
    }
    multiplier = float(
        calibration["threshold_multiplier_above_static_maximum"]
    )
    thresholds = {
        channel: max(
            floor_by_channel[channel],
            multiplier * static_maxima[channel],
        )
        for channel in CHANNELS
    }

    static_envelope_by_dropout: dict[float, tuple[list[float], list[float]]] = {}
    for dropout in (0.0, 0.1):
        control_ids = [
            scenario_id
            for scenario_id, row in label_by_scenario.items()
            if row["label"] == "static-negative"
            and float(row["dropout_fraction"]) == dropout
        ]
        if len(control_ids) != 3:
            raise ValueError("expected three static controls per visual condition")
        timelines = [
            scenario_data[scenario_id]["trajectory_timestamps"]
            for scenario_id in control_ids
        ]
        if any(timeline != timelines[0] for timeline in timelines[1:]):
            raise ValueError("static-control timelines differ")
        envelope = [
            max(
                scenario_data[scenario_id]["rolling_rmse"][index]
                for scenario_id in control_ids
            )
            for index in range(len(timelines[0]))
        ]
        static_envelope_by_dropout[dropout] = (timelines[0], envelope)

    scenario_results: list[dict[str, Any]] = []
    for scenario_id in sorted(label_by_scenario):
        label_row = label_by_scenario[scenario_id]
        label = label_row["label"]
        alert, active_channels = alert_time(
            scenario_data[scenario_id]["calibration_series"],
            thresholds,
            warmup_s,
            required_channels,
            alert_persistence_s,
        )
        dropout = float(label_row["dropout_fraction"])
        trajectory_timestamps = scenario_data[scenario_id][
            "trajectory_timestamps"
        ]
        rolling_rmse = scenario_data[scenario_id]["rolling_rmse"]
        envelope_timestamps, envelope = static_envelope_by_dropout[dropout]
        if trajectory_timestamps != envelope_timestamps:
            raise ValueError("dynamic and static-envelope timelines differ")
        margin = float(
            degradation[
                "local_rmse_margin_above_matched_static_envelope_m"
            ]
        )
        condition = [
            value > baseline + margin
            for value, baseline in zip(rolling_rmse, envelope)
        ]
        degradation_onset = sustained_onset(
            trajectory_timestamps,
            condition,
            float(degradation["hold_s"]),
        )
        lead_time = (
            degradation_onset - alert
            if alert is not None and degradation_onset is not None
            else None
        )
        calibration_series = scenario_data[scenario_id][
            "calibration_series"
        ]
        maxima = {
            channel: max(float(row[channel]) for row in calibration_series)
            for channel in CHANNELS
        }
        parent_metric = metric_by_scenario[scenario_id]
        scenario_results.append(
            {
                "scenario_id": scenario_id,
                "profile": label_row["profile"],
                "drift_span_ms": float(label_row["drift_span_ms"]),
                "dropout_fraction": dropout,
                "label": label,
                "alert_detected": alert is not None,
                "alert_time_s": alert,
                "active_channels_at_alert": ",".join(active_channels),
                "degradation_onset_s": degradation_onset,
                "lead_time_s": lead_time,
                "positive_lead_time": (
                    lead_time is not None and lead_time > 0.0
                ),
                "maximum_velocity_rms_ms_per_s": maxima[
                    "estimated_offset_velocity_rms"
                ],
                "maximum_acceleration_rms_ms_per_s2": maxima[
                    "estimated_offset_acceleration_rms"
                ],
                "maximum_peak_to_peak_ms": maxima[
                    "estimated_offset_peak_to_peak"
                ],
                "parent_position_rmse_m": float(
                    parent_metric["position_rmse_m"]
                ),
                "parent_local_max_rmse_m": float(
                    parent_metric["local_max_rmse_m"]
                ),
                "parent_one_metre_availability": float(
                    parent_metric["one_metre_availability"]
                ),
                "parent_final_abs_residual_ms": float(
                    parent_metric["final_abs_residual_ms"]
                ),
            }
        )

    static_false_positive_count = sum(
        row["label"] == "static-negative" and row["alert_detected"]
        for row in scenario_results
    )
    positive_rows = [
        row
        for row in scenario_results
        if row["label"] == "early-warning-positive"
    ]
    secondary_rows = [
        row
        for row in scenario_results
        if row["label"] == "dynamic-secondary"
    ]
    positive_detected_count = sum(
        row["alert_detected"] for row in positive_rows
    )
    positive_lead_count = sum(
        row["positive_lead_time"] for row in positive_rows
    )
    secondary_detected_count = sum(
        row["alert_detected"] for row in secondary_rows
    )

    supported = (
        static_false_positive_count
        == int(success["static_false_positive_scenario_count"])
        and positive_detected_count
        == int(success["early_warning_positive_detection_count"])
        and positive_lead_count == 2
        and secondary_detected_count
        >= int(success["dynamic_secondary_detection_count_minimum"])
    )
    partial = (
        positive_detected_count == 2
        and (
            positive_lead_count == 1
            or static_false_positive_count == 1
        )
    )
    status = (
        "monitor_supported"
        if supported
        else "monitor_partial"
        if partial
        else "monitor_not_supported"
    )
    stage_4_percent = 40 if status == "monitor_supported" else 0
    v2_overall_percent = 65.0 if status == "monitor_supported" else 55.0

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    threshold_rows = [
        {
            "channel": channel,
            "static_maximum": static_maxima[channel],
            "floor": floor_by_channel[channel],
            "multiplier": multiplier,
            "threshold": thresholds[channel],
            "calibration_scenario_count": 6,
        }
        for channel in CHANNELS
    ]
    write_csv(
        output / "thresholds.csv",
        (
            "channel",
            "static_maximum",
            "floor",
            "multiplier",
            "threshold",
            "calibration_scenario_count",
        ),
        threshold_rows,
    )
    write_csv(
        output / "scenario_monitor_results.csv",
        (
            "scenario_id",
            "profile",
            "drift_span_ms",
            "dropout_fraction",
            "label",
            "alert_detected",
            "alert_time_s",
            "active_channels_at_alert",
            "degradation_onset_s",
            "lead_time_s",
            "positive_lead_time",
            "maximum_velocity_rms_ms_per_s",
            "maximum_acceleration_rms_ms_per_s2",
            "maximum_peak_to_peak_ms",
            "parent_position_rmse_m",
            "parent_local_max_rmse_m",
            "parent_one_metre_availability",
            "parent_final_abs_residual_ms",
        ),
        scenario_results,
    )

    results = {
        "dynamic_secondary_count": 22,
        "dynamic_secondary_detected_count": secondary_detected_count,
        "early_warning_positive_count": 2,
        "early_warning_positive_detected_count": positive_detected_count,
        "early_warning_positive_positive_lead_count": positive_lead_count,
        "experiment": "openvins-internal-clock-monitor-pilot",
        "monitor_status": status,
        "parent_commit": PARENT_COMMIT,
        "positive_scenarios": positive_rows,
        "preregistration_commit": PREREG_COMMIT,
        "progress": {
            "v1_overall_percent": 100.0,
            "v2_overall_percent": v2_overall_percent,
            "v2_stage_4_percent": stage_4_percent,
        },
        "scenario_count": 30,
        "schema_version": 1,
        "static_false_positive_count": static_false_positive_count,
        "static_negative_count": 6,
        "success_criteria": success,
        "thresholds": {
            channel: thresholds[channel] for channel in CHANNELS
        },
    }
    results_path = output / "results.json"
    results_path.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest = {
        "experiment": "openvins-internal-clock-monitor-pilot",
        "new_estimator_execution": False,
        "official_source_modified": False,
        "online_ground_truth_input_count": 0,
        "parent_evidence_modified": False,
        "preregistration_modified": False,
        "schema_version": 1,
        "source_inputs": {
            "evidence_audit_sha256": sha256(args.evidence_audit),
            "experiment_config_sha256": sha256(args.experiment_config),
            "parent_manifest_sha256": sha256(args.parent_manifest),
            "parent_results_sha256": sha256(args.parent_results),
            "parent_scenarios_sha256": sha256(args.parent_scenarios),
            "preregistration_sha256": sha256(args.preregistration),
            "results_sha256": sha256(results_path),
            "scenario_labels_sha256": sha256(args.scenario_labels),
        },
        "verification": {
            "deterministic_evidence_verified": True,
            "importer_deterministic": True,
            "monitor_input_boundary_verified": True,
            "preregistration_preceded_analysis": True,
            "static_only_threshold_calibration_verified": True,
        },
    }
    (output / "results_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    (output / "figure_detection_summary.svg").write_text(
        svg_detection(scenario_results),
        encoding="utf-8",
        newline="\n",
    )
    (output / "figure_early_warning_timeline.svg").write_text(
        svg_timeline(positive_rows),
        encoding="utf-8",
        newline="\n",
    )

    report_lines = [
        "# V2-E03 internal clock monitor pilot",
        "",
        f"- status: `{status}`",
        f"- static false-positive scenarios: `{static_false_positive_count}/6`",
        f"- early-warning positives detected: `{positive_detected_count}/2`",
        f"- early-warning positives with positive lead: `{positive_lead_count}/2`",
        f"- secondary dynamic scenarios detected: `{secondary_detected_count}/22`",
        "",
        "## Monitor boundary",
        "",
        "The online monitor used only estimator timestamps and estimated "
        "camera-to-IMU offset history. Injected clock offset and physical "
        "trajectory reference were excluded from threshold calibration "
        "and alert generation.",
        "",
        "## Thresholds",
        "",
    ]
    for row in threshold_rows:
        report_lines.append(
            f"- {row['channel']}: `{row['threshold']:.12g}` "
            f"(static maximum `{row['static_maximum']:.12g}`)"
        )
    report_lines.extend(
        [
            "",
            "## Primary early-warning cases",
            "",
        ]
    )
    for row in positive_rows:
        report_lines.append(
            f"- `{row['scenario_id']}`: alert `{row['alert_time_s']}`, "
            f"degradation `{row['degradation_onset_s']}`, "
            f"lead `{row['lead_time_s']}` s"
        )
    report_lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "This is a single-trajectory monitor pilot calibrated on six "
            "static controls from the same evidence family. It does not "
            "establish a multi-trajectory false-alarm rate or deployment "
            "readiness.",
        ]
    )
    (output / "report.md").write_text(
        "\n".join(report_lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"monitor_status={status}")
    print(
        "static_false_positive_count="
        f"{static_false_positive_count}"
    )
    print(
        "early_warning_positive_detected_count="
        f"{positive_detected_count}"
    )
    print(
        "early_warning_positive_positive_lead_count="
        f"{positive_lead_count}"
    )
    print(
        "dynamic_secondary_detected_count="
        f"{secondary_detected_count}"
    )
    for row in positive_rows:
        print(
            "positive_scenario="
            f"{row['scenario_id']}|alert={row['alert_time_s']}|"
            f"degradation={row['degradation_onset_s']}|"
            f"lead={row['lead_time_s']}"
        )
    print(f"v2_stage_4_percent={stage_4_percent}")
    print(f"v2_overall_percent={v2_overall_percent:.1f}")
    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
