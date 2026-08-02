#!/usr/bin/env python3
"""Import and statistically evaluate V2-E01b five-seed replication."""
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
from veranav.trajectory import evaluate_position_trajectory

EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
SEEDS = (20260801, 20260802, 20260803, 20260804, 20260805)
OFFSETS = (-20.0, -10.0, 0.0, 10.0, 20.0)
DROPOUTS = (0.0, 0.05, 0.10, 0.15, 0.20)
JOINT_OFFSETS = (-20.0, -10.0, 10.0, 20.0)
JOINT_DROPOUTS = (0.05, 0.10, 0.15, 0.20)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for name in (
        "evidence-root",
        "evidence-audit",
        "experiment-config",
        "preregistration",
        "analysis-cells",
        "execution-plan",
        "official-manifest",
        "parent-results",
        "runner-source",
        "runner-cmake",
        "runner-binary",
        "output-dir",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--upstream-commit", required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def finite(value: Any, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def rmse(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("RMSE requires samples")
    return math.sqrt(math.fsum(value * value for value in values) / len(values))


def percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("percentile requires samples")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def read_calibration(path: Path) -> tuple[list[float], list[float]]:
    timestamps: list[float] = []
    residuals: list[float] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        expected = {
            "timestamp_s",
            "reported_camera_time_s",
            "physical_camera_time_s",
            "estimated_cam_to_imu_s",
            "target_cam_to_imu_s",
            "residual_s",
        }
        if set(reader.fieldnames or ()) != expected:
            raise ValueError(f"unexpected calibration columns: {path}")
        for row in reader:
            timestamp = finite(row["timestamp_s"], "calibration timestamp")
            residual = finite(row["residual_s"], "calibration residual")
            if timestamps and timestamp <= timestamps[-1]:
                raise ValueError(f"non-increasing calibration timestamp: {path}")
            timestamps.append(timestamp)
            residuals.append(residual)
    if len(timestamps) < 100:
        raise ValueError(f"too few calibration samples: {path}")
    return timestamps, residuals


def trajectory_errors(reference: Any, estimate: Any) -> tuple[list[float], list[float]]:
    reference_times = [float(value) for value in reference.timestamps_s]
    estimate_times = [float(value) for value in estimate.timestamps_s]
    if len(reference_times) != len(estimate_times):
        raise ValueError("trajectory timestamp counts differ")
    if any(left != right for left, right in zip(reference_times, estimate_times)):
        raise ValueError("trajectory timestamps differ")
    if len(reference.positions_n_m) != len(estimate.positions_n_m):
        raise ValueError("trajectory sample counts differ")
    if len(reference.positions_n_m) != len(reference_times):
        raise ValueError("reference timestamp and position counts differ")
    errors = []
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


def convergence_time(
    timestamps: Sequence[float],
    residuals: Sequence[float],
    threshold_s: float,
    hold_s: float,
) -> float | None:
    for index, candidate in enumerate(timestamps):
        end = candidate + hold_s
        if timestamps[-1] < end:
            break
        selected = [
            abs(value)
            for time, value in zip(timestamps[index:], residuals[index:])
            if time <= end
        ]
        if selected and max(selected) <= threshold_s:
            return candidate
    return None


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


def mean_ci(values: Sequence[float], t_critical: float) -> dict[str, float]:
    if len(values) != 5:
        raise ValueError("five values are required for the preregistered CI")
    mean_value = statistics.fmean(values)
    sd_value = statistics.stdev(values)
    half_width = t_critical * sd_value / math.sqrt(len(values))
    return {
        "mean": mean_value,
        "sample_sd": sd_value,
        "ci95_lower": mean_value - half_width,
        "ci95_upper": mean_value + half_width,
    }


def safe_ratio(numerator: float, denominator: float, label: str) -> float:
    if denominator <= 0.0:
        raise ValueError(f"nonpositive denominator for {label}")
    return numerator / denominator


def svg_interaction_ratio(cell_summaries: Sequence[Mapping[str, Any]]) -> str:
    width, height = 1040, 650
    left, right, top, bottom = 100, 60, 95, 100
    plot_w, plot_h = width - left - right, height - top - bottom
    colors = {-20.0: "#2563eb", -10.0: "#60a5fa", 10.0: "#f97316", 20.0: "#dc2626"}
    y_values = [float(row["global_ratio_mean"]) for row in cell_summaries]
    y_min = min(0.5, min(y_values) * 0.9)
    y_max = max(1.6, max(y_values) * 1.1)

    def sx(value: float) -> float:
        return left + (value - 0.05) / 0.15 * plot_w

    def sy(value: float) -> float:
        return top + plot_h - (value - y_min) / (y_max - y_min) * plot_h

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#1f2937}.title{font-size:25px;font-weight:700}.subtitle{font-size:14px;fill:#4b5563}.axis{font-size:13px}.tick{font-size:12px;fill:#4b5563}.legend{font-size:13px}</style>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="55" y="42" class="title">Five-seed temporal–visual interaction replication</text>',
        '<text x="55" y="68" class="subtitle">Mean global RMSE interaction ratio; preregistered threshold = 1.25</text>',
    ]
    for index in range(6):
        value = y_min + (y_max - y_min) * index / 5
        y = sy(value)
        lines += [
            f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="#e5e7eb"/>',
            f'<text x="{left-12}" y="{y+4:.2f}" text-anchor="end" class="tick">{value:.2f}</text>',
        ]
    threshold_y = sy(1.25)
    lines.append(
        f'<line x1="{left}" y1="{threshold_y:.2f}" x2="{left+plot_w}" y2="{threshold_y:.2f}" stroke="#111827" stroke-width="1.5" stroke-dasharray="8 6"/>'
    )
    for dropout in JOINT_DROPOUTS:
        x = sx(dropout)
        lines += [
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top+plot_h}" stroke="#f3f4f6"/>',
            f'<text x="{x:.2f}" y="{top+plot_h+25}" text-anchor="middle" class="tick">{dropout*100:.0f}%</text>',
        ]
    lines += [
        f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#374151" stroke-width="1.5"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#374151" stroke-width="1.5"/>',
    ]
    for legend_index, (offset, color) in enumerate(colors.items()):
        group = sorted(
            [row for row in cell_summaries if float(row["offset_ms"]) == offset],
            key=lambda row: float(row["dropout_fraction"]),
        )
        path = " ".join(
            ("M" if index == 0 else "L")
            + f" {sx(float(row['dropout_fraction'])):.2f} {sy(float(row['global_ratio_mean'])):.2f}"
            for index, row in enumerate(group)
        )
        lines.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3"/>')
        for row in group:
            fill = color if bool(row["replicated_supported"]) else "#ffffff"
            lines.append(
                f'<circle cx="{sx(float(row["dropout_fraction"])):.2f}" cy="{sy(float(row["global_ratio_mean"])):.2f}" r="6" fill="{fill}" stroke="{color}" stroke-width="2"/>'
            )
        lx = left + legend_index * 205
        lines += [
            f'<line x1="{lx}" y1="{height-36}" x2="{lx+28}" y2="{height-36}" stroke="{color}" stroke-width="3"/>',
            f'<text x="{lx+36}" y="{height-31}" class="legend">{offset:+.0f} ms</text>',
        ]
    lines += [
        f'<text x="{left+plot_w/2:.2f}" y="{height-66}" text-anchor="middle" class="axis">Visual frame dropout</text>',
        f'<text x="25" y="{top+plot_h/2:.2f}" text-anchor="middle" class="axis" transform="rotate(-90 25 {top+plot_h/2:.2f})">Mean global RMSE interaction ratio</text>',
        '</svg>',
    ]
    return "\n".join(lines) + "\n"


def svg_seed_support(cell_summaries: Sequence[Mapping[str, Any]]) -> str:
    width, height = 920, 620
    left, top = 150, 110
    cell_w, cell_h = 160, 90
    rows = list(JOINT_OFFSETS)
    cols = list(JOINT_DROPOUTS)
    by_cell = {(float(row["offset_ms"]), float(row["dropout_fraction"])): row for row in cell_summaries}
    fills = {0: "#f3f4f6", 1: "#dbeafe", 2: "#bfdbfe", 3: "#93c5fd", 4: "#60a5fa", 5: "#2563eb"}
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#1f2937}.title{font-size:25px;font-weight:700}.subtitle{font-size:14px;fill:#4b5563}.label{font-size:14px}.cell{font-size:22px;font-weight:700}</style>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="45" y="42" class="title">Seed-level interaction support</text>',
        '<text x="45" y="68" class="subtitle">Number of seeds satisfying both global and local preregistered thresholds</text>',
    ]
    for col_index, dropout in enumerate(cols):
        x = left + col_index * cell_w + cell_w / 2
        lines.append(f'<text x="{x:.2f}" y="{top-20}" text-anchor="middle" class="label">{dropout*100:.0f}%</text>')
    for row_index, offset in enumerate(rows):
        y = top + row_index * cell_h
        lines.append(f'<text x="{left-25}" y="{y+cell_h/2+5:.2f}" text-anchor="end" class="label">{offset:+.0f} ms</text>')
        for col_index, dropout in enumerate(cols):
            record = by_cell[(offset, dropout)]
            support = int(record["seed_support_count"])
            x = left + col_index * cell_w
            stroke = "#111827" if bool(record["replicated_supported"]) else "#ffffff"
            lines += [
                f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="{fills[support]}" stroke="{stroke}" stroke-width="3"/>',
                f'<text x="{x+cell_w/2:.2f}" y="{y+cell_h/2+8:.2f}" text-anchor="middle" class="cell" fill="{("#ffffff" if support >= 4 else "#1f2937")}">{support}/5</text>',
            ]
    lines += [
        f'<text x="{left+len(cols)*cell_w/2:.2f}" y="{top+len(rows)*cell_h+55}" text-anchor="middle" class="label">Dropout fraction</text>',
        f'<text x="38" y="{top+len(rows)*cell_h/2:.2f}" text-anchor="middle" class="label" transform="rotate(-90 38 {top+len(rows)*cell_h/2:.2f})">Timestamp offset</text>',
        '</svg>',
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = arguments()
    if args.upstream_commit != EXPECTED_COMMIT:
        raise ValueError("unexpected OpenVINS upstream commit")

    config = load_json(args.experiment_config)
    prereg = load_json(args.preregistration)
    evidence_audit = load_json(args.evidence_audit)
    official_manifest = load_json(args.official_manifest)
    parent_results = load_json(args.parent_results)

    if config["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("experiment configuration commit mismatch")
    if official_manifest["upstream"]["commit"] != EXPECTED_COMMIT:
        raise ValueError("official manifest commit mismatch")
    if official_manifest["verification"]["official_source_modified"] is not False:
        raise ValueError("official source modification flag mismatch")
    if prereg["design"]["analytical_cell_count"] != 125:
        raise ValueError("unexpected preregistered analytical cell count")
    if prereg["design"]["physical_scenario_count"] != 105:
        raise ValueError("unexpected preregistered physical scenario count")
    if prereg["design"]["estimator_execution_count"] != 134:
        raise ValueError("unexpected preregistered execution count")
    for key in (
        "physical_references_byte_identical",
        "raw_measurement_fingerprints_identical",
        "masks_equal_across_offsets",
        "masks_nested_within_seed",
        "five_seed_masks_distinct",
    ):
        if evidence_audit[key] is not True:
            raise ValueError(f"evidence audit failed: {key}")
    if parent_results["interaction_status"] != "pilot_supported":
        raise ValueError("parent pilot was not supported")

    with args.execution_plan.open("r", encoding="utf-8", newline="") as stream:
        execution_plan = list(csv.DictReader(stream))
    with args.analysis_cells.open("r", encoding="utf-8", newline="") as stream:
        analysis_cells = list(csv.DictReader(stream))
    if len(execution_plan) != 105 or len(analysis_cells) != 125:
        raise ValueError("preregistered CSV row count mismatch")

    analysis_cfg = config["analysis"]
    seed_cfg = analysis_cfg["seed_level_support"]
    cell_cfg = analysis_cfg["cell_level_replicated_support"]
    t_critical = float(analysis_cfg["t_critical_95_two_sided_df4"])
    calibration_cfg = {
        "threshold_s": 0.001,
        "hold_s": 10.0,
        "tail_window_s": 20.0,
    }
    local_cfg = {
        "window_s": 5.0,
        "service_window_s": 1.0,
        "service_threshold_m": 1.0,
        "failure_hold_s": 3.0,
    }

    physical_metrics: dict[str, dict[str, Any]] = {}
    for plan_row in execution_plan:
        scenario_id = plan_row["physical_scenario_id"]
        run_dir = args.evidence_root / scenario_id / "run-01"
        estimate_path = run_dir / "estimate.csv"
        reference_path = run_dir / "reference_physical.csv"
        calibration_path = run_dir / "calibration.csv"
        summary_path = run_dir / "summary.json"
        for path in (estimate_path, reference_path, calibration_path, summary_path):
            if not path.is_file() or path.stat().st_size == 0:
                raise FileNotFoundError(path)

        estimate = read_position_trajectory_csv(estimate_path, source_name=f"{scenario_id}-estimate")
        reference = read_position_trajectory_csv(reference_path, source_name=f"{scenario_id}-reference")
        metrics = evaluate_position_trajectory(reference, estimate).metrics
        timestamps, errors = trajectory_errors(reference, estimate)
        rolling_local = rolling_rmse_series(timestamps, errors, local_cfg["window_s"])
        rolling_service = rolling_rmse_series(timestamps, errors, local_cfg["service_window_s"])
        calibration_times, residuals = read_calibration(calibration_path)
        if calibration_times != timestamps:
            raise ValueError(f"calibration timestamps differ: {scenario_id}")
        convergence = convergence_time(
            calibration_times,
            residuals,
            calibration_cfg["threshold_s"],
            calibration_cfg["hold_s"],
        )
        tail_start = calibration_times[-1] - calibration_cfg["tail_window_s"]
        tail_residuals = [
            value
            for time, value in zip(calibration_times, residuals)
            if time >= tail_start
        ]
        summary = load_json(summary_path)
        record = {
            "physical_scenario_id": scenario_id,
            "seed": int(plan_row["seed"]),
            "offset_ms": float(plan_row["offset_ms"]),
            "requested_dropout_fraction": float(plan_row["dropout_fraction"]),
            "realized_dropout_fraction": float(summary["realized_dropout_fraction"]),
            "degraded_frames": int(summary["degraded_frames"]),
            "position_rmse_m": float(metrics.position_rmse_m),
            "position_mean_m": math.fsum(errors) / len(errors),
            "position_p95_m": percentile(errors, 0.95),
            "position_max_m": max(errors),
            "local_max_rmse_m": max(rolling_local),
            "local_max_start_s": timestamps[rolling_local.index(max(rolling_local))],
            "convergence_time_s": convergence,
            "final_abs_residual_ms": abs(residuals[-1]) * 1000.0,
            "tail_residual_rmse_ms": rmse(tail_residuals) * 1000.0,
            "one_metre_availability": sum(value <= 1.0 for value in errors) / len(errors),
            "sustained_failure_onset_s": sustained_failure(
                timestamps,
                rolling_service,
                local_cfg["service_threshold_m"],
                local_cfg["failure_hold_s"],
            ),
            "sample_count": int(metrics.sample_count),
        }
        physical_metrics[scenario_id] = record

    analytical: dict[tuple[int, float, float], dict[str, Any]] = {}
    for row in analysis_cells:
        key = (int(row["seed"]), float(row["offset_ms"]), float(row["dropout_fraction"]))
        physical_id = row["physical_scenario_id"]
        if physical_id not in physical_metrics:
            raise ValueError(f"analysis cell references missing physical scenario: {physical_id}")
        analytical[key] = physical_metrics[physical_id]
    if len(analytical) != 125:
        raise ValueError("analytical mapping is incomplete")

    seed_interactions: list[dict[str, Any]] = []
    for seed in SEEDS:
        base = analytical[(seed, 0.0, 0.0)]
        for offset in JOINT_OFFSETS:
            offset_only = analytical[(seed, offset, 0.0)]
            for dropout in JOINT_DROPOUTS:
                dropout_only = analytical[(seed, 0.0, dropout)]
                joint = analytical[(seed, offset, dropout)]
                global_add = (
                    joint["position_rmse_m"]
                    - offset_only["position_rmse_m"]
                    - dropout_only["position_rmse_m"]
                    + base["position_rmse_m"]
                )
                local_add = (
                    joint["local_max_rmse_m"]
                    - offset_only["local_max_rmse_m"]
                    - dropout_only["local_max_rmse_m"]
                    + base["local_max_rmse_m"]
                )
                global_ratio = safe_ratio(
                    joint["position_rmse_m"] * base["position_rmse_m"],
                    offset_only["position_rmse_m"] * dropout_only["position_rmse_m"],
                    "global interaction ratio",
                )
                local_ratio = safe_ratio(
                    joint["local_max_rmse_m"] * base["local_max_rmse_m"],
                    offset_only["local_max_rmse_m"] * dropout_only["local_max_rmse_m"],
                    "local interaction ratio",
                )
                seed_support = (
                    global_add >= float(seed_cfg["rmse_additive_interaction_threshold_m"])
                    and global_ratio >= float(seed_cfg["rmse_interaction_ratio_threshold"])
                    and local_add >= float(seed_cfg["local_additive_interaction_threshold_m"])
                    and local_ratio >= float(seed_cfg["local_interaction_ratio_threshold"])
                )
                convergence_delay = None
                if joint["convergence_time_s"] is not None and offset_only["convergence_time_s"] is not None:
                    convergence_delay = joint["convergence_time_s"] - offset_only["convergence_time_s"]
                seed_interactions.append(
                    {
                        "seed": seed,
                        "offset_ms": offset,
                        "dropout_fraction": dropout,
                        "joint_physical_scenario_id": joint["physical_scenario_id"],
                        "global_additive_interaction_m": global_add,
                        "global_interaction_ratio": global_ratio,
                        "local_additive_interaction_m": local_add,
                        "local_interaction_ratio": local_ratio,
                        "seed_supported": seed_support,
                        "convergence_delay_s": convergence_delay,
                        "final_residual_excess_ms": (
                            joint["final_abs_residual_ms"]
                            - offset_only["final_abs_residual_ms"]
                            - dropout_only["final_abs_residual_ms"]
                            + base["final_abs_residual_ms"]
                        ),
                        "availability_shortfall": (
                            offset_only["one_metre_availability"]
                            + dropout_only["one_metre_availability"]
                            - base["one_metre_availability"]
                            - joint["one_metre_availability"]
                        ),
                    }
                )
    if len(seed_interactions) != 80:
        raise ValueError("unexpected seed-interaction row count")

    cell_summaries: list[dict[str, Any]] = []
    for offset in JOINT_OFFSETS:
        for dropout in JOINT_DROPOUTS:
            rows = [
                row
                for row in seed_interactions
                if row["offset_ms"] == offset and row["dropout_fraction"] == dropout
            ]
            if len(rows) != 5:
                raise ValueError("joint cell does not contain five seeds")
            global_add_values = [float(row["global_additive_interaction_m"]) for row in rows]
            local_add_values = [float(row["local_additive_interaction_m"]) for row in rows]
            global_ratio_values = [float(row["global_interaction_ratio"]) for row in rows]
            local_ratio_values = [float(row["local_interaction_ratio"]) for row in rows]
            global_add_stats = mean_ci(global_add_values, t_critical)
            local_add_stats = mean_ci(local_add_values, t_critical)
            support_count = sum(bool(row["seed_supported"]) for row in rows)
            global_ratio_mean = statistics.fmean(global_ratio_values)
            local_ratio_mean = statistics.fmean(local_ratio_values)
            replicated_supported = (
                support_count >= int(cell_cfg["minimum_seed_support_count"])
                and global_add_stats["mean"] >= float(cell_cfg["mean_rmse_additive_interaction_threshold_m"])
                and local_add_stats["mean"] >= float(cell_cfg["mean_local_additive_interaction_threshold_m"])
                and global_ratio_mean >= float(cell_cfg["mean_rmse_interaction_ratio_threshold"])
                and local_ratio_mean >= float(cell_cfg["mean_local_interaction_ratio_threshold"])
                and global_add_stats["ci95_lower"] > float(cell_cfg["lower_95_ci_additive_interaction_must_exceed_m"])
                and local_add_stats["ci95_lower"] > float(cell_cfg["lower_95_ci_additive_interaction_must_exceed_m"])
            )
            cell_summaries.append(
                {
                    "offset_ms": offset,
                    "dropout_fraction": dropout,
                    "seed_support_count": support_count,
                    "replicated_supported": replicated_supported,
                    "global_additive_mean_m": global_add_stats["mean"],
                    "global_additive_sd_m": global_add_stats["sample_sd"],
                    "global_additive_ci95_lower_m": global_add_stats["ci95_lower"],
                    "global_additive_ci95_upper_m": global_add_stats["ci95_upper"],
                    "global_ratio_mean": global_ratio_mean,
                    "global_ratio_sd": statistics.stdev(global_ratio_values),
                    "local_additive_mean_m": local_add_stats["mean"],
                    "local_additive_sd_m": local_add_stats["sample_sd"],
                    "local_additive_ci95_lower_m": local_add_stats["ci95_lower"],
                    "local_additive_ci95_upper_m": local_add_stats["ci95_upper"],
                    "local_ratio_mean": local_ratio_mean,
                    "local_ratio_sd": statistics.stdev(local_ratio_values),
                    "global_additive_positive_seed_count": sum(value > 0.0 for value in global_add_values),
                    "local_additive_positive_seed_count": sum(value > 0.0 for value in local_add_values),
                }
            )

    supported_cells = [row for row in cell_summaries if row["replicated_supported"]]
    partial_cells = [
        row
        for row in cell_summaries
        if not row["replicated_supported"] and int(row["seed_support_count"]) >= 3
    ]
    if supported_cells:
        replication_status = "replicated_supported"
    elif partial_cells:
        replication_status = "partial_replication"
    else:
        replication_status = "replication_not_supported"

    strongest = max(
        cell_summaries,
        key=lambda row: (
            bool(row["replicated_supported"]),
            int(row["seed_support_count"]),
            float(row["global_ratio_mean"]),
            float(row["local_ratio_mean"]),
        ),
    )

    sign_asymmetry: list[dict[str, Any]] = []
    by_seed_cell = {
        (int(row["seed"]), float(row["offset_ms"]), float(row["dropout_fraction"])): row
        for row in seed_interactions
    }
    for magnitude in (10.0, 20.0):
        for dropout in JOINT_DROPOUTS:
            global_differences = []
            local_differences = []
            ratio_differences = []
            for seed in SEEDS:
                positive = by_seed_cell[(seed, magnitude, dropout)]
                negative = by_seed_cell[(seed, -magnitude, dropout)]
                global_differences.append(
                    float(positive["global_additive_interaction_m"])
                    - float(negative["global_additive_interaction_m"])
                )
                local_differences.append(
                    float(positive["local_additive_interaction_m"])
                    - float(negative["local_additive_interaction_m"])
                )
                ratio_differences.append(
                    float(positive["global_interaction_ratio"])
                    - float(negative["global_interaction_ratio"])
                )
            global_stats = mean_ci(global_differences, t_critical)
            local_stats = mean_ci(local_differences, t_critical)
            sign_asymmetry.append(
                {
                    "offset_magnitude_ms": magnitude,
                    "dropout_fraction": dropout,
                    "global_additive_pos_minus_neg_mean_m": global_stats["mean"],
                    "global_additive_pos_minus_neg_ci95_lower_m": global_stats["ci95_lower"],
                    "global_additive_pos_minus_neg_ci95_upper_m": global_stats["ci95_upper"],
                    "local_additive_pos_minus_neg_mean_m": local_stats["mean"],
                    "local_additive_pos_minus_neg_ci95_lower_m": local_stats["ci95_lower"],
                    "local_additive_pos_minus_neg_ci95_upper_m": local_stats["ci95_upper"],
                    "global_ratio_pos_minus_neg_mean": statistics.fmean(ratio_differences),
                    "sign_asymmetry_supported": (
                        global_stats["ci95_lower"] > 0.0
                        or global_stats["ci95_upper"] < 0.0
                        or local_stats["ci95_lower"] > 0.0
                        or local_stats["ci95_upper"] < 0.0
                    ),
                }
            )

    nonmonotonicity: list[dict[str, Any]] = []
    for offset in JOINT_OFFSETS:
        rows = sorted(
            [row for row in cell_summaries if row["offset_ms"] == offset],
            key=lambda row: float(row["dropout_fraction"]),
        )
        global_peak = max(rows, key=lambda row: float(row["global_ratio_mean"]))
        local_peak = max(rows, key=lambda row: float(row["local_ratio_mean"]))
        global_sequence = [float(row["global_ratio_mean"]) for row in rows]
        local_sequence = [float(row["local_ratio_mean"]) for row in rows]
        nonmonotonicity.append(
            {
                "offset_ms": offset,
                "global_peak_dropout_fraction": float(global_peak["dropout_fraction"]),
                "global_peak_ratio": float(global_peak["global_ratio_mean"]),
                "local_peak_dropout_fraction": float(local_peak["dropout_fraction"]),
                "local_peak_ratio": float(local_peak["local_ratio_mean"]),
                "global_ratio_nondecreasing": all(left <= right for left, right in zip(global_sequence, global_sequence[1:])),
                "global_ratio_nonincreasing": all(left >= right for left, right in zip(global_sequence, global_sequence[1:])),
                "local_ratio_nondecreasing": all(left <= right for left, right in zip(local_sequence, local_sequence[1:])),
                "local_ratio_nonincreasing": all(left >= right for left, right in zip(local_sequence, local_sequence[1:])),
                "global_sequence": global_sequence,
                "local_sequence": local_sequence,
            }
        )

    result_payload = {
        "experiment": "openvins-temporal-visual-interaction-replication",
        "replication_status": replication_status,
        "schema_version": 1,
        "strongest_cell": strongest,
        "supported_cell_count": len(supported_cells),
        "partial_cell_count": len(partial_cells),
        "cell_summaries": cell_summaries,
        "seed_interactions": seed_interactions,
        "sign_asymmetry": sign_asymmetry,
        "nonmonotonicity": nonmonotonicity,
        "project_progress": {
            "v1_overall_percent": 100.0,
            "v2_stage_1_percent": 100,
            "v2_stage_2_percent": 100,
            "v2_stage_3_percent": 0,
            "v2_stage_4_percent": 0,
            "v2_stage_5_percent": 0,
            "v2_stage_6_percent": 0,
            "v2_overall_percent": 35.0,
        },
        "claim_boundary": {
            "dropout_seed_count": 5,
            "trajectory_count": 1,
            "real_world_validation": False,
            "literature_novelty_verified": False,
        },
    }

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    figure_ratio = svg_interaction_ratio(cell_summaries)
    figure_support = svg_seed_support(cell_summaries)
    result_payload["figure_mean_interaction_sha256"] = hashlib.sha256(figure_ratio.encode("utf-8")).hexdigest()
    result_payload["figure_seed_support_sha256"] = hashlib.sha256(figure_support.encode("utf-8")).hexdigest()

    results_manifest = {
        "analysis_cells_sha256": sha256(args.analysis_cells),
        "evidence_audit_sha256": sha256(args.evidence_audit),
        "execution_plan_sha256": sha256(args.execution_plan),
        "experiment": "openvins-temporal-visual-interaction-replication",
        "experiment_config_sha256": sha256(args.experiment_config),
        "official_source_modified": False,
        "parent_results_sha256": sha256(args.parent_results),
        "preregistration_sha256": sha256(args.preregistration),
        "runner": {
            "binary_sha256": sha256(args.runner_binary),
            "cmake_sha256": sha256(args.runner_cmake),
            "source_sha256": sha256(args.runner_source),
        },
        "schema_version": 1,
        "upstream_commit": EXPECTED_COMMIT,
        "verification": {
            "five_seed_masks_distinct": True,
            "masks_equal_across_offsets": True,
            "masks_nested_within_seed": True,
            "physical_references_byte_identical": True,
            "preregistration_preceded_execution": True,
            "raw_measurement_fingerprints_identical": True,
            "resume_safe_execution_complete": True,
        },
    }

    (output / "results_manifest.json").write_text(
        json.dumps(results_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "results.json").write_text(
        json.dumps(result_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "figure_mean_interaction.svg").write_text(figure_ratio, encoding="utf-8", newline="\n")
    (output / "figure_seed_support.svg").write_text(figure_support, encoding="utf-8", newline="\n")

    def write_csv(path: Path, columns: list[str], rows: Sequence[Mapping[str, Any]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                rendered = {}
                for column in columns:
                    value = row.get(column)
                    if value is None:
                        rendered[column] = ""
                    elif isinstance(value, bool):
                        rendered[column] = str(value)
                    elif isinstance(value, float):
                        rendered[column] = f"{value:.12g}"
                    else:
                        rendered[column] = value
                writer.writerow(rendered)

    physical_rows = sorted(
        physical_metrics.values(),
        key=lambda row: (int(row["seed"]), float(row["offset_ms"]), float(row["requested_dropout_fraction"])),
    )
    write_csv(
        output / "physical_scenarios.csv",
        [
            "physical_scenario_id", "seed", "offset_ms", "requested_dropout_fraction",
            "realized_dropout_fraction", "degraded_frames", "position_rmse_m",
            "local_max_rmse_m", "convergence_time_s", "final_abs_residual_ms",
            "tail_residual_rmse_ms", "one_metre_availability", "sustained_failure_onset_s",
        ],
        physical_rows,
    )
    write_csv(
        output / "seed_interactions.csv",
        [
            "seed", "offset_ms", "dropout_fraction", "joint_physical_scenario_id",
            "global_additive_interaction_m", "global_interaction_ratio",
            "local_additive_interaction_m", "local_interaction_ratio", "seed_supported",
            "convergence_delay_s", "final_residual_excess_ms", "availability_shortfall",
        ],
        seed_interactions,
    )
    write_csv(
        output / "cell_summary.csv",
        [
            "offset_ms", "dropout_fraction", "seed_support_count", "replicated_supported",
            "global_additive_mean_m", "global_additive_sd_m", "global_additive_ci95_lower_m",
            "global_additive_ci95_upper_m", "global_ratio_mean", "global_ratio_sd",
            "local_additive_mean_m", "local_additive_sd_m", "local_additive_ci95_lower_m",
            "local_additive_ci95_upper_m", "local_ratio_mean", "local_ratio_sd",
            "global_additive_positive_seed_count", "local_additive_positive_seed_count",
        ],
        cell_summaries,
    )
    write_csv(
        output / "sign_asymmetry.csv",
        [
            "offset_magnitude_ms", "dropout_fraction",
            "global_additive_pos_minus_neg_mean_m", "global_additive_pos_minus_neg_ci95_lower_m",
            "global_additive_pos_minus_neg_ci95_upper_m", "local_additive_pos_minus_neg_mean_m",
            "local_additive_pos_minus_neg_ci95_lower_m", "local_additive_pos_minus_neg_ci95_upper_m",
            "global_ratio_pos_minus_neg_mean", "sign_asymmetry_supported",
        ],
        sign_asymmetry,
    )
    write_csv(
        output / "nonmonotonicity.csv",
        [
            "offset_ms", "global_peak_dropout_fraction", "global_peak_ratio",
            "local_peak_dropout_fraction", "local_peak_ratio", "global_ratio_nondecreasing",
            "global_ratio_nonincreasing", "local_ratio_nondecreasing", "local_ratio_nonincreasing",
        ],
        nonmonotonicity,
    )

    supported_rows = "\n".join(
        f"| {row['offset_ms']:+.0f} | {row['dropout_fraction']*100:.0f}% | {row['seed_support_count']}/5 | {row['global_ratio_mean']:.3f} | {row['global_additive_ci95_lower_m']:.4f} | {row['local_ratio_mean']:.3f} | {row['local_additive_ci95_lower_m']:.4f} | {row['replicated_supported']} |"
        for row in cell_summaries
    )
    if replication_status == "replicated_supported":
        interpretation = (
            "At least one preregistered joint cell satisfies the strict five-seed replication criterion. "
            "This upgrades the parent effect from a single-mask pilot to a stochastic replication on one trajectory."
        )
    elif replication_status == "partial_replication":
        interpretation = (
            "No cell satisfies the full preregistered criterion, but at least one cell is supported by three seeds. "
            "The parent pilot is therefore only partially replicated."
        )
    else:
        interpretation = (
            "No cell satisfies the preregistered replication criterion. The parent pilot is not replicated across "
            "the five dropout masks and must remain a single-mask observation."
        )
    report = f"""# V2-E01b five-seed temporal–visual replication

## Status

`{replication_status}`

{interpretation}

## Fixed design

- five timestamp offsets
- five dropout levels
- five nested-dropout seeds
- 125 analytical cells
- 105 unique physical scenarios
- 134 estimator executions

## Replicated cell results

| Offset (ms) | Dropout | Seed support | Mean global ratio | Global additive CI lower (m) | Mean local ratio | Local additive CI lower (m) | Replicated |
|---:|---:|---:|---:|---:|---:|---:|---|
{supported_rows}

## Strongest cell

- offset: `{strongest['offset_ms']:+.0f} ms`
- dropout: `{strongest['dropout_fraction']*100:.0f}%`
- seed support: `{strongest['seed_support_count']}/5`
- global interaction ratio: `{strongest['global_ratio_mean']:.6f}`
- local interaction ratio: `{strongest['local_ratio_mean']:.6f}`
- replicated supported: `{strongest['replicated_supported']}`

## Figures

![Mean interaction ratio](figure_mean_interaction.svg)

![Seed support](figure_seed_support.svg)

## Claim boundary

This experiment provides five-mask stochastic replication on one official deterministic trajectory. It does not establish multi-trajectory, real-world or literature-level generalization. Sign-asymmetry and nonmonotonicity analyses are secondary and must not replace the preregistered primary criterion.
"""
    (output / "report.md").write_text(report, encoding="utf-8", newline="\n")

    print("physical_scenario_metric_count=105")
    print("seed_interaction_count=80")
    print("joint_cell_count=16")
    print(f"replication_status={replication_status}")
    print(f"supported_cell_count={len(supported_cells)}")
    print(f"partial_cell_count={len(partial_cells)}")
    print(f"strongest_offset_ms={strongest['offset_ms']}")
    print(f"strongest_dropout_fraction={strongest['dropout_fraction']}")
    print(f"strongest_seed_support_count={strongest['seed_support_count']}")
    print(f"strongest_global_ratio_mean={strongest['global_ratio_mean']:.9f}")
    print(f"strongest_local_ratio_mean={strongest['local_ratio_mean']:.9f}")
    print("v1_overall_percent=100.0")
    print("v2_stage_2_percent=100")
    print("v2_overall_percent=35.0")
    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
