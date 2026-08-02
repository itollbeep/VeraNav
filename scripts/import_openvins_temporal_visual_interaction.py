#!/usr/bin/env python3
"""Import deterministic OpenVINS temporal-visual interaction evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from veranav.adapter_io import read_position_trajectory_csv
from veranav.trajectory import evaluate_position_trajectory

EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_SCENARIOS = (
    "neg20-drop00", "neg20-drop10", "neg20-drop30", "neg20-drop50",
    "zero-drop00", "zero-drop10", "zero-drop30", "zero-drop50",
    "pos20-drop00", "pos20-drop10", "pos20-drop30", "pos20-drop50",
)
EXPECTED_INTERACTIONS = (
    "neg20-drop10", "neg20-drop30", "neg20-drop50",
    "pos20-drop10", "pos20-drop30", "pos20-drop50",
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for name in (
        "evidence-root",
        "experiment-config",
        "official-config",
        "official-manifest",
        "baseline-metrics",
        "time-offset-results",
        "visual-dropout-results",
        "registry-manifest",
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


def require_file(path: Path, name: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"{name} must be a nonempty file")


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
    return math.sqrt(math.fsum(x * x for x in values) / len(values))


def percentile(values: Sequence[float], p: float) -> float:
    ordered = sorted(values)
    position = p * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def read_calibration(path: Path) -> tuple[list[float], list[float]]:
    times: list[float] = []
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
            raise ValueError("unexpected calibration columns")
        for row in reader:
            timestamp = finite(row["timestamp_s"], "timestamp")
            residual = finite(row["residual_s"], "residual")
            if times and timestamp <= times[-1]:
                raise ValueError("non-increasing calibration time")
            times.append(timestamp)
            residuals.append(residual)
    if len(times) < 100:
        raise ValueError("too few calibration samples")
    return times, residuals


def read_mask(path: Path) -> tuple[list[float], list[int]]:
    uniforms: list[float] = []
    dropped: list[int] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        expected = {"frame_index", "elapsed_s", "uniform_value", "dropped"}
        if set(reader.fieldnames or ()) != expected:
            raise ValueError("unexpected dropout-mask columns")
        for expected_index, row in enumerate(reader):
            if int(row["frame_index"]) != expected_index:
                raise ValueError("dropout-mask frame index mismatch")
            uniform = finite(row["uniform_value"], "uniform")
            flag = int(row["dropped"])
            if not 0.0 <= uniform < 1.0 or flag not in {0, 1}:
                raise ValueError("invalid dropout-mask value")
            uniforms.append(uniform)
            dropped.append(flag)
    if len(uniforms) < 100:
        raise ValueError("too few dropout-mask samples")
    return uniforms, dropped


def trajectory_errors(reference: Any, estimate: Any) -> tuple[list[float], list[float]]:
    reference_timestamps = [float(value) for value in reference.timestamps_s]
    estimate_timestamps = [float(value) for value in estimate.timestamps_s]
    if len(reference_timestamps) != len(estimate_timestamps):
        raise ValueError("trajectory timestamp counts differ")
    if any(
        reference_time != estimate_time
        for reference_time, estimate_time in zip(
            reference_timestamps,
            estimate_timestamps,
        )
    ):
        raise ValueError("trajectory timestamps differ")
    if len(reference.positions_n_m) != len(estimate.positions_n_m):
        raise ValueError("trajectory sample counts differ")
    if len(reference.positions_n_m) != len(reference_timestamps):
        raise ValueError("reference timestamp and position counts differ")
    if len(estimate.positions_n_m) != len(estimate_timestamps):
        raise ValueError("estimate timestamp and position counts differ")
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
    return reference_timestamps, errors


def rolling_rmse(
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


def xml(value: str) -> str:
    return html.escape(value, quote=True)


def build_figure(records: Sequence[Mapping[str, Any]]) -> str:
    width, height = 1000, 620
    left, right, top, bottom = 100, 55, 95, 90
    plot_w, plot_h = width - left - right, height - top - bottom
    colors = {-20.0: "#2563eb", 0.0: "#4b5563", 20.0: "#dc2626"}
    y_max = max(float(row["position_rmse_m"]) for row in records) * 1.12
    y_max = max(y_max, 0.001)

    def sx(value: float) -> float:
        return left + value / 0.5 * plot_w

    def sy(value: float) -> float:
        return top + plot_h - value / y_max * plot_h

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#1f2937}.title{font-size:26px;font-weight:700}.subtitle{font-size:14px;fill:#4b5563}.axis{font-size:13px}.tick{font-size:12px;fill:#4b5563}.legend{font-size:13px}</style>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="55" y="42" class="title">Temporal calibration × visual dropout interaction</text>',
        '<text x="55" y="67" class="subtitle">Physical-time RMSE under shared nested dropout masks</text>',
    ]
    for index in range(6):
        value = y_max * index / 5
        y = sy(value)
        lines += [
            f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="#e5e7eb"/>',
            f'<text x="{left-12}" y="{y+4:.2f}" text-anchor="end" class="tick">{value:.3f}</text>',
        ]
    for probability in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
        x = sx(probability)
        lines += [
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top+plot_h}" stroke="#f3f4f6"/>',
            f'<text x="{x:.2f}" y="{top+plot_h+24}" text-anchor="middle" class="tick">{probability*100:.0f}%</text>',
        ]
    lines += [
        f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#374151" stroke-width="1.5"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#374151" stroke-width="1.5"/>',
    ]
    for legend_index, (offset, color) in enumerate(colors.items()):
        group = sorted(
            [row for row in records if float(row["offset_ms"]) == offset],
            key=lambda row: float(row["realized_dropout_fraction"]),
        )
        path = " ".join(
            (
                ("M" if index == 0 else "L")
                + f" {sx(float(row['realized_dropout_fraction'])):.2f}"
                + f" {sy(float(row['position_rmse_m'])):.2f}"
            )
            for index, row in enumerate(group)
        )
        lines.append(
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3"/>'
        )
        for row in group:
            lines.append(
                f'<circle cx="{sx(float(row["realized_dropout_fraction"])):.2f}" cy="{sy(float(row["position_rmse_m"])):.2f}" r="5" fill="{color}" stroke="#ffffff" stroke-width="1.5"/>'
            )
        lx = left + legend_index * 210
        lines += [
            f'<line x1="{lx}" y1="{height-35}" x2="{lx+28}" y2="{height-35}" stroke="{color}" stroke-width="3"/>',
            f'<text x="{lx+36}" y="{height-30}" class="legend">{offset:+.0f} ms</text>',
        ]
    lines += [
        f'<text x="{left+plot_w/2:.2f}" y="{height-58}" text-anchor="middle" class="axis">Realized visual frame dropout</text>',
        f'<text x="24" y="{top+plot_h/2:.2f}" text-anchor="middle" class="axis" transform="rotate(-90 24 {top+plot_h/2:.2f})">Physical-time position RMSE (m)</text>',
        "</svg>",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = arguments()
    if args.upstream_commit != EXPECTED_COMMIT:
        raise ValueError("unexpected OpenVINS upstream commit")
    required_files = {
        "experiment_config": args.experiment_config,
        "official_config": args.official_config,
        "official_manifest": args.official_manifest,
        "baseline_metrics": args.baseline_metrics,
        "time_offset_results": args.time_offset_results,
        "visual_dropout_results": args.visual_dropout_results,
        "registry_manifest": args.registry_manifest,
        "runner_source": args.runner_source,
        "runner_cmake": args.runner_cmake,
        "runner_binary": args.runner_binary,
    }
    for name, path in required_files.items():
        require_file(path, name)
    if not args.evidence_root.is_dir():
        raise ValueError("evidence_root must be a directory")

    config = load_json(args.experiment_config)
    official = load_json(args.official_manifest)
    baseline = load_json(args.baseline_metrics)
    time_anchor = load_json(args.time_offset_results)
    dropout_anchor = load_json(args.visual_dropout_results)
    registry = load_json(args.registry_manifest)

    if config["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("experiment configuration commit mismatch")
    if official["upstream"]["commit"] != EXPECTED_COMMIT:
        raise ValueError("official reproduction commit mismatch")
    if official["verification"]["official_source_modified"] is not False:
        raise ValueError("official source modification flag mismatch")
    if registry["project_progress"]["v2_overall_percent"] != 10.0:
        raise ValueError("unexpected pre-experiment v2 progress")
    if tuple(x["name"] for x in config["scenarios"]) != EXPECTED_SCENARIOS:
        raise ValueError("scenario order mismatch")

    calibration = config["calibration_evaluation"]
    local = config["local_error_evaluation"]
    decision = config["interaction_decision"]
    convergence_threshold_s = float(calibration["convergence_threshold_ms"]) / 1000.0
    convergence_hold_s = float(calibration["convergence_hold_s"])
    tail_window_s = float(calibration["tail_window_s"])
    local_window_s = float(local["rolling_window_s"])
    service_window_s = float(local["service_rolling_window_s"])
    service_threshold_m = float(local["service_threshold_m"])
    failure_hold_s = float(local["sustained_failure_hold_s"])

    scenario_results: list[dict[str, Any]] = []
    scenario_artifacts: dict[str, dict[str, str]] = {}
    physical_reference_bytes: bytes | None = None
    camera_fingerprint: str | None = None
    imu_fingerprint: str | None = None
    mask_bytes: dict[float, bytes] = {}
    dropped_sets: dict[float, set[int]] = {}

    artifacts = (
        "estimate.csv",
        "reference_calibrated.csv",
        "reference_nominal.csv",
        "reference_physical.csv",
        "calibration.csv",
        "dropout_mask.csv",
        "summary.json",
    )

    for configured in config["scenarios"]:
        name = configured["name"]
        run_a = args.evidence_root / name / "run-a"
        run_b = args.evidence_root / name / "run-b"
        for artifact in artifacts:
            left, right = run_a / artifact, run_b / artifact
            require_file(left, f"{name}.{artifact}.run-a")
            require_file(right, f"{name}.{artifact}.run-b")
            if left.read_bytes() != right.read_bytes():
                raise ValueError(f"{name} deterministic mismatch: {artifact}")

        reference_bytes = (run_a / "reference_physical.csv").read_bytes()
        if physical_reference_bytes is None:
            physical_reference_bytes = reference_bytes
        elif physical_reference_bytes != reference_bytes:
            raise ValueError(f"{name} physical reference mismatch")

        summary = load_json(run_a / "summary.json")
        if summary["scenario"] != name:
            raise ValueError(f"{name} summary mismatch")
        offset_ms = float(configured["camera_timestamp_offset_ms"])
        probability = float(configured["dropout_fraction"])
        if not math.isclose(
            float(summary["injected_camera_timestamp_offset_s"]) * 1000.0,
            offset_ms,
            abs_tol=1e-12,
        ):
            raise ValueError(f"{name} offset mismatch")
        if not math.isclose(
            float(summary["requested_dropout_fraction"]),
            probability,
            abs_tol=1e-15,
        ):
            raise ValueError(f"{name} dropout mismatch")

        current_camera = str(summary["camera_measurement_fingerprint"])
        current_imu = str(summary["imu_measurement_fingerprint"])
        if camera_fingerprint is None:
            camera_fingerprint, imu_fingerprint = current_camera, current_imu
        elif (current_camera, current_imu) != (
            camera_fingerprint,
            imu_fingerprint,
        ):
            raise ValueError(f"{name} raw measurement fingerprint mismatch")

        current_mask = (run_a / "dropout_mask.csv").read_bytes()
        if probability in mask_bytes and mask_bytes[probability] != current_mask:
            raise ValueError(f"{name} mask differs across offsets")
        mask_bytes.setdefault(probability, current_mask)
        uniforms, flags = read_mask(run_a / "dropout_mask.csv")
        if flags != [1 if value < probability else 0 for value in uniforms]:
            raise ValueError(f"{name} dropout decision mismatch")
        dropped_sets.setdefault(
            probability,
            {index for index, flag in enumerate(flags) if flag},
        )

        estimate = read_position_trajectory_csv(
            run_a / "estimate.csv",
            source_name=f"{name}-estimate",
        )
        calibrated_reference = read_position_trajectory_csv(
            run_a / "reference_calibrated.csv",
            source_name=f"{name}-calibrated-reference",
        )
        physical_reference = read_position_trajectory_csv(
            run_a / "reference_physical.csv",
            source_name=f"{name}-physical-reference",
        )
        physical_metrics = evaluate_position_trajectory(
            physical_reference,
            estimate,
        ).metrics
        calibrated_metrics = evaluate_position_trajectory(
            calibrated_reference,
            estimate,
        ).metrics
        timestamps, errors = trajectory_errors(physical_reference, estimate)
        local_series = rolling_rmse(timestamps, errors, local_window_s)
        service_series = rolling_rmse(timestamps, errors, service_window_s)
        calibration_times, residuals = read_calibration(
            run_a / "calibration.csv"
        )
        if calibration_times != timestamps:
            raise ValueError(f"{name} calibration timestamps mismatch")
        tail_start = timestamps[-1] - tail_window_s
        tail_residuals = [
            value
            for time, value in zip(calibration_times, residuals)
            if time >= tail_start
        ]
        result = {
            "calibration_aware_rmse_m": calibrated_metrics.position_rmse_m,
            "convergence_time_s": convergence_time(
                calibration_times,
                residuals,
                convergence_threshold_s,
                convergence_hold_s,
            ),
            "degraded_frames": int(summary["degraded_frames"]),
            "drop_mask_fingerprint": str(summary["drop_mask_fingerprint"]),
            "final_abs_residual_ms": abs(residuals[-1]) * 1000.0,
            "final_signed_residual_ms": residuals[-1] * 1000.0,
            "local_max_rmse_m": max(local_series),
            "local_max_start_s": timestamps[local_series.index(max(local_series))],
            "mean_error_m": math.fsum(errors) / len(errors),
            "offset_ms": offset_ms,
            "one_metre_availability": (
                sum(error <= service_threshold_m for error in errors)
                / len(errors)
            ),
            "p95_error_m": percentile(errors, 0.95),
            "position_max_m": max(errors),
            "position_rmse_m": physical_metrics.position_rmse_m,
            "realized_dropout_fraction": float(
                summary["realized_dropout_fraction"]
            ),
            "requested_dropout_fraction": probability,
            "sample_count": physical_metrics.sample_count,
            "scenario": name,
            "sustained_failure_onset_s": sustained_failure(
                timestamps,
                service_series,
                service_threshold_m,
                failure_hold_s,
            ),
            "tail_residual_rmse_ms": rmse(tail_residuals) * 1000.0,
            "total_camera_frames": int(summary["total_camera_frames"]),
        }
        scenario_results.append(result)
        scenario_artifacts[name] = {
            artifact: sha256(run_a / artifact)
            for artifact in artifacts
        }

    probabilities = sorted(dropped_sets)
    for lower, higher in zip(probabilities, probabilities[1:]):
        if not dropped_sets[lower].issubset(dropped_sets[higher]):
            raise ValueError(f"dropout masks not nested: {lower}->{higher}")

    by_cell = {
        (float(row["offset_ms"]), float(row["requested_dropout_fraction"])): row
        for row in scenario_results
    }
    base = by_cell[(0.0, 0.0)]
    expected_baseline = float(baseline["metrics"]["position_rmse_m"])
    if not math.isclose(
        float(base["position_rmse_m"]),
        expected_baseline,
        abs_tol=1e-9,
    ):
        raise ValueError("official baseline RMSE not reproduced")

    time_by_name = {
        str(row["scenario"]): row
        for row in time_anchor["scenarios"]
    }
    for offset, anchor_name in {
        -20.0: "neg-20ms",
        0.0: "baseline",
        20.0: "pos-20ms",
    }.items():
        current = float(by_cell[(offset, 0.0)]["position_rmse_m"])
        expected = float(time_by_name[anchor_name]["physical_time_rmse_m"])
        if not math.isclose(current, expected, abs_tol=1e-9):
            raise ValueError(f"time-offset anchor mismatch: {offset}")

    dropout_by_name = {
        str(row["scenario"]): row
        for row in dropout_anchor["scenarios"]
    }
    for probability, anchor_name in {
        0.0: "baseline",
        0.1: "random-10",
        0.3: "random-30",
        0.5: "random-50",
    }.items():
        current = float(by_cell[(0.0, probability)]["position_rmse_m"])
        expected = float(dropout_by_name[anchor_name]["position_rmse_m"])
        if not math.isclose(current, expected, abs_tol=1e-9):
            raise ValueError(f"visual-dropout anchor mismatch: {probability}")

    baseline_rmse = float(base["position_rmse_m"])
    baseline_local = float(base["local_max_rmse_m"])
    for row in scenario_results:
        row["position_rmse_ratio_to_baseline"] = (
            float(row["position_rmse_m"]) / baseline_rmse
        )
        row["local_rmse_ratio_to_baseline"] = (
            float(row["local_max_rmse_m"]) / baseline_local
        )

    interactions: list[dict[str, Any]] = []
    for offset in (-20.0, 20.0):
        for probability in (0.1, 0.3, 0.5):
            joint = by_cell[(offset, probability)]
            offset_only = by_cell[(offset, 0.0)]
            dropout_only = by_cell[(0.0, probability)]
            additive_rmse = (
                float(offset_only["position_rmse_m"])
                + float(dropout_only["position_rmse_m"])
                - float(base["position_rmse_m"])
            )
            additive_local = (
                float(offset_only["local_max_rmse_m"])
                + float(dropout_only["local_max_rmse_m"])
                - float(base["local_max_rmse_m"])
            )
            rmse_add = float(joint["position_rmse_m"]) - additive_rmse
            local_add = float(joint["local_max_rmse_m"]) - additive_local
            rmse_ratio = (
                float(joint["position_rmse_m"])
                * float(base["position_rmse_m"])
                / (
                    float(offset_only["position_rmse_m"])
                    * float(dropout_only["position_rmse_m"])
                )
            )
            local_ratio = (
                float(joint["local_max_rmse_m"])
                * float(base["local_max_rmse_m"])
                / (
                    float(offset_only["local_max_rmse_m"])
                    * float(dropout_only["local_max_rmse_m"])
                )
            )
            offset_conv = offset_only["convergence_time_s"]
            joint_conv = joint["convergence_time_s"]
            convergence_lost = offset_conv is not None and joint_conv is None
            convergence_delay = (
                None
                if offset_conv is None or joint_conv is None
                else float(joint_conv) - float(offset_conv)
            )
            residual_excess = (
                float(joint["final_abs_residual_ms"])
                - float(offset_only["final_abs_residual_ms"])
                - float(dropout_only["final_abs_residual_ms"])
                + float(base["final_abs_residual_ms"])
            )
            expected_availability = (
                float(offset_only["one_metre_availability"])
                + float(dropout_only["one_metre_availability"])
                - float(base["one_metre_availability"])
            )
            availability_shortfall = (
                expected_availability
                - float(joint["one_metre_availability"])
            )
            flags = {
                "rmse_supported": (
                    rmse_ratio
                    >= float(decision["rmse_interaction_ratio_threshold"])
                    and rmse_add
                    >= float(decision["rmse_additive_threshold_m"])
                ),
                "local_rmse_supported": (
                    local_ratio
                    >= float(
                        decision["local_rmse_interaction_ratio_threshold"]
                    )
                    and local_add
                    >= float(decision["local_rmse_additive_threshold_m"])
                ),
                "convergence_supported": (
                    convergence_lost
                    or (
                        convergence_delay is not None
                        and convergence_delay
                        >= float(decision["convergence_delay_threshold_s"])
                    )
                ),
                "residual_supported": (
                    residual_excess
                    >= float(
                        decision["final_residual_excess_threshold_ms"]
                    )
                ),
                "availability_supported": (
                    availability_shortfall
                    >= float(decision["availability_shortfall_threshold"])
                ),
            }
            count = sum(flags.values())
            interactions.append(
                {
                    "availability_shortfall": availability_shortfall,
                    "convergence_delay_s": convergence_delay,
                    "convergence_lost": convergence_lost,
                    "criterion_supported": (
                        count >= int(decision["minimum_supported_metrics"])
                    ),
                    "final_residual_excess_ms": residual_excess,
                    "local_rmse_additive_interaction_m": local_add,
                    "local_rmse_interaction_ratio": local_ratio,
                    "metric_flags": flags,
                    "offset_ms": offset,
                    "requested_dropout_fraction": probability,
                    "rmse_additive_interaction_m": rmse_add,
                    "rmse_interaction_ratio": rmse_ratio,
                    "scenario": str(joint["scenario"]),
                    "supported_metric_count": count,
                }
            )

    if tuple(row["scenario"] for row in interactions) != EXPECTED_INTERACTIONS:
        raise ValueError("interaction order mismatch")
    strongest = max(
        interactions,
        key=lambda row: (
            int(row["supported_metric_count"]),
            float(row["rmse_interaction_ratio"]),
            float(row["local_rmse_interaction_ratio"]),
        ),
    )
    max_support = int(strongest["supported_metric_count"])
    minimum_support = int(decision["minimum_supported_metrics"])
    status = (
        "pilot_supported"
        if max_support >= minimum_support
        else "pilot_weak_support"
        if max_support == 1
        else "pilot_not_supported"
    )

    progress = {
        "v1_overall_percent": 100.0,
        "v2_overall_percent": 20.0,
        "v2_stage_1_percent": 100,
        "v2_stage_2_percent": 40,
        "v2_stage_3_percent": 0,
        "v2_stage_4_percent": 0,
        "v2_stage_5_percent": 0,
        "v2_stage_6_percent": 0,
    }
    results = {
        "experiment": (
            "openvins-temporal-calibration-visual-degradation-interaction"
        ),
        "interaction_decision": decision,
        "interaction_status": status,
        "interactions": interactions,
        "project_progress": progress,
        "schema_version": 1,
        "scenarios": scenario_results,
        "strongest_interaction": strongest,
    }
    figure = build_figure(scenario_results)
    manifest = {
        "anchor_hashes": {
            "time_offset_results_sha256": sha256(args.time_offset_results),
            "visual_dropout_results_sha256": sha256(
                args.visual_dropout_results
            ),
        },
        "experiment": (
            "openvins-temporal-calibration-visual-degradation-interaction"
        ),
        "experiment_config_sha256": sha256(args.experiment_config),
        "figure_sha256": hashlib.sha256(figure.encode()).hexdigest(),
        "measurement_realization": {
            "camera_fingerprint": camera_fingerprint,
            "imu_fingerprint": imu_fingerprint,
        },
        "official_config_sha256": sha256(args.official_config),
        "official_source_modified": False,
        "registry_manifest_sha256": sha256(args.registry_manifest),
        "runner": {
            "binary_sha256": sha256(args.runner_binary),
            "cmake_sha256": sha256(args.runner_cmake),
            "source_sha256": sha256(args.runner_source),
        },
        "scenario_artifacts": scenario_artifacts,
        "schema_version": 1,
        "upstream_commit": EXPECTED_COMMIT,
        "verification": {
            "deterministic_replay_verified": True,
            "dropout_masks_equal_across_offsets": True,
            "dropout_masks_nested": True,
            "physical_references_byte_identical": True,
            "raw_measurement_fingerprints_identical": True,
            "single_factor_anchors_reproduced": True,
        },
    }

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "figure_interaction.svg").write_text(
        figure,
        encoding="utf-8",
        newline="\n",
    )

    scenario_columns = [
        "scenario", "offset_ms", "requested_dropout_fraction",
        "realized_dropout_fraction", "degraded_frames", "position_rmse_m",
        "position_rmse_ratio_to_baseline", "local_max_rmse_m",
        "local_rmse_ratio_to_baseline", "final_abs_residual_ms",
        "tail_residual_rmse_ms", "convergence_time_s",
        "one_metre_availability", "sustained_failure_onset_s",
    ]
    with (output / "scenarios.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=scenario_columns, lineterminator="\n"
        )
        writer.writeheader()
        for row in scenario_results:
            writer.writerow(
                {
                    key: (
                        ""
                        if row[key] is None
                        else f"{row[key]:.12g}"
                        if isinstance(row[key], float)
                        else row[key]
                    )
                    for key in scenario_columns
                }
            )

    interaction_columns = [
        "scenario", "offset_ms", "requested_dropout_fraction",
        "rmse_additive_interaction_m", "rmse_interaction_ratio",
        "local_rmse_additive_interaction_m",
        "local_rmse_interaction_ratio", "convergence_delay_s",
        "convergence_lost", "final_residual_excess_ms",
        "availability_shortfall", "supported_metric_count",
        "criterion_supported",
    ]
    with (output / "interactions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=interaction_columns, lineterminator="\n"
        )
        writer.writeheader()
        for row in interactions:
            writer.writerow(
                {
                    key: (
                        ""
                        if row[key] is None
                        else f"{row[key]:.12g}"
                        if isinstance(row[key], float)
                        else row[key]
                    )
                    for key in interaction_columns
                }
            )

    scenario_rows = "\n".join(
        f"| {row['scenario']} | {row['offset_ms']:+.0f} | "
        f"{row['realized_dropout_fraction']*100:.1f}% | "
        f"{row['position_rmse_m']:.6f} | {row['local_max_rmse_m']:.6f} | "
        f"{row['final_abs_residual_ms']:.3f} | {row['convergence_time_s']} |"
        for row in scenario_results
    )
    interaction_rows = "\n".join(
        f"| {row['scenario']} | {row['rmse_interaction_ratio']:.3f} | "
        f"{row['local_rmse_interaction_ratio']:.3f} | "
        f"{row['convergence_delay_s']} | "
        f"{row['final_residual_excess_ms']:.3f} | "
        f"{row['supported_metric_count']} | {row['criterion_supported']} |"
        for row in interactions
    )
    interpretation = {
        "pilot_supported": (
            "The preregistered single-trajectory pilot supports an "
            "interaction mechanism candidate. Generalization is unproven."
        ),
        "pilot_weak_support": (
            "One preregistered metric shows practical interaction evidence, "
            "but the two-metric criterion is not met."
        ),
        "pilot_not_supported": (
            "The pilot does not support the preregistered interaction "
            "criterion. The null result is retained."
        ),
    }[status]
    report = f"""# OpenVINS temporal-calibration × visual-dropout interaction

## Design

This preregistered 3 × 4 factorial pilot combines camera timestamp
offsets of -20 ms, 0 ms and +20 ms with random visual frame dropout of
0%, 10%, 30% and 50%.

All scenarios share the same physical camera and IMU measurements.
One common per-frame uniform sequence generates nested dropout masks,
and the same probability mask is used for all three offsets. Every
scenario is executed twice and compared byte for byte.

## Single-factor anchors

Zero-dropout cells reproduce the committed timestamp-offset experiment.
Zero-offset cells reproduce the committed visual-dropout experiment.

## Scenario results

| Scenario | Offset (ms) | Realized dropout | RMSE (m) | Max 5 s RMSE (m) | Final residual (ms) | Convergence (s) |
|---|---:|---:|---:|---:|---:|---:|
{scenario_rows}

## Interaction contrasts

The RMSE interaction ratio is joint × baseline divided by offset-only ×
dropout-only. The pilot criterion requires at least two preregistered
metrics to cross their practical thresholds in one joint scenario.

| Scenario | RMSE ratio | Local ratio | Convergence delay (s) | Residual excess (ms) | Supported metrics | Criterion |
|---|---:|---:|---:|---:|---:|---|
{interaction_rows}

## Pilot decision

Status: `{status}`

Strongest joint scenario: `{strongest['scenario']}`

Supported metric count: `{strongest['supported_metric_count']}`

RMSE interaction ratio: `{strongest['rmse_interaction_ratio']:.6f}`

Local RMSE interaction ratio:
`{strongest['local_rmse_interaction_ratio']:.6f}`

{interpretation}

![Temporal and visual interaction](figure_interaction.svg)

## Claim boundary

This is one deterministic trajectory and one nested dropout realization.
It is mechanism-discovery evidence, not a universal failure boundary,
population-level interaction or established literature novelty.
"""
    (output / "report.md").write_text(
        report, encoding="utf-8", newline="\n"
    )
    print(f"scenario_count={len(scenario_results)}")
    print(f"interaction_count={len(interactions)}")
    print(f"interaction_status={status}")
    print(f"strongest_scenario={strongest['scenario']}")
    print(
        "strongest_supported_metric_count="
        f"{strongest['supported_metric_count']}"
    )
    print(
        "strongest_rmse_interaction_ratio="
        f"{strongest['rmse_interaction_ratio']:.9f}"
    )
    print(f"camera_measurement_fingerprint={camera_fingerprint}")
    print(f"imu_measurement_fingerprint={imu_fingerprint}")
    print("v2_stage_2_percent=40")
    print("v2_overall_percent=20.0")
    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
