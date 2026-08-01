#!/usr/bin/env python3
"""Import the deterministic OpenVINS camera timestamp-offset sweep."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Sequence

from veranav.adapter_io import read_position_trajectory_csv
from veranav.trajectory import evaluate_position_trajectory


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_SCENARIOS = (
    "baseline",
    "neg-50ms",
    "neg-20ms",
    "neg-10ms",
    "neg-5ms",
    "pos-5ms",
    "pos-10ms",
    "pos-20ms",
    "pos-50ms",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--experiment-config", type=Path, required=True)
    parser.add_argument("--official-config", type=Path, required=True)
    parser.add_argument("--official-manifest", type=Path, required=True)
    parser.add_argument("--baseline-metrics", type=Path, required=True)
    parser.add_argument("--runner-source", type=Path, required=True)
    parser.add_argument("--runner-cmake", type=Path, required=True)
    parser.add_argument("--runner-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--upstream-commit", required=True)
    return parser.parse_args()


def require_file(path: Path, name: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"{name} must be a nonempty file")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def read_calibration(
    path: Path,
) -> tuple[list[float], list[float], list[float]]:
    timestamps: list[float] = []
    estimates: list[float] = []
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
            raise ValueError("unexpected calibration CSV columns")

        for row in reader:
            timestamp = float(row["timestamp_s"])
            estimate = float(row["estimated_cam_to_imu_s"])
            residual = float(row["residual_s"])

            if not all(
                math.isfinite(value)
                for value in (timestamp, estimate, residual)
            ):
                raise ValueError("non-finite calibration value")
            if timestamps and timestamp <= timestamps[-1]:
                raise ValueError(
                    "non-increasing calibration timestamp"
                )

            timestamps.append(timestamp)
            estimates.append(estimate)
            residuals.append(residual)

    if len(timestamps) < 100:
        raise ValueError("too few calibration samples")

    return timestamps, estimates, residuals


def rmse(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("RMSE requires samples")
    return math.sqrt(
        math.fsum(value * value for value in values)
        / len(values)
    )


def convergence_time(
    timestamps: Sequence[float],
    residuals: Sequence[float],
    threshold_s: float,
    hold_s: float,
) -> float | None:
    for index, candidate in enumerate(timestamps):
        hold_end = candidate + hold_s
        selected = [
            abs(residual)
            for timestamp, residual in zip(
                timestamps[index:],
                residuals[index:],
            )
            if timestamp <= hold_end
        ]

        if not selected:
            continue
        if timestamps[-1] < hold_end:
            break
        if max(selected) <= threshold_s:
            return candidate

    return None


def main() -> int:
    args = arguments()

    if args.upstream_commit != EXPECTED_COMMIT:
        raise ValueError("unexpected OpenVINS upstream commit")

    for name, path in {
        "experiment_config": args.experiment_config,
        "official_config": args.official_config,
        "official_manifest": args.official_manifest,
        "baseline_metrics": args.baseline_metrics,
        "runner_source": args.runner_source,
        "runner_cmake": args.runner_cmake,
        "runner_binary": args.runner_binary,
    }.items():
        require_file(path, name)

    config = load_json(args.experiment_config)
    official = load_json(args.official_manifest)
    baseline_record = load_json(args.baseline_metrics)

    if config["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("experiment configuration commit mismatch")
    if config["online_time_calibration_required"] is not True:
        raise ValueError("online time calibration is not required")
    if official["upstream"]["commit"] != EXPECTED_COMMIT:
        raise ValueError("official reproduction commit mismatch")
    if official["verification"]["official_source_modified"] is not False:
        raise ValueError("official source modification flag is not false")

    configured_names = tuple(
        item["name"]
        for item in config["scenarios"]
    )
    if configured_names != EXPECTED_SCENARIOS:
        raise ValueError("scenario order mismatch")

    expected_baseline_rmse = float(
        baseline_record["metrics"]["position_rmse_m"]
    )

    calibration_config = config["calibration_evaluation"]
    convergence_threshold_s = (
        float(calibration_config["convergence_threshold_ms"])
        / 1000.0
    )
    convergence_hold_s = float(
        calibration_config["convergence_hold_s"]
    )
    tail_window_s = float(
        calibration_config["tail_window_s"]
    )

    scenario_results: list[dict[str, Any]] = []
    scenario_artifacts: dict[str, dict[str, str]] = {}
    physical_reference_bytes: bytes | None = None
    camera_fingerprint: str | None = None
    imu_fingerprint: str | None = None

    for configured in config["scenarios"]:
        name = configured["name"]
        run_a = args.evidence_root / name / "run-a"
        run_b = args.evidence_root / name / "run-b"

        files = {
            "estimate_a": run_a / "estimate.csv",
            "calibrated_a": run_a / "reference_calibrated.csv",
            "nominal_a": run_a / "reference_nominal.csv",
            "physical_a": run_a / "reference_physical.csv",
            "calibration_a": run_a / "calibration.csv",
            "summary_a": run_a / "summary.json",
            "log_a": run_a / "run.log",
            "estimate_b": run_b / "estimate.csv",
            "calibrated_b": run_b / "reference_calibrated.csv",
            "nominal_b": run_b / "reference_nominal.csv",
            "physical_b": run_b / "reference_physical.csv",
            "calibration_b": run_b / "calibration.csv",
            "summary_b": run_b / "summary.json",
            "log_b": run_b / "run.log",
        }

        for file_name, path in files.items():
            require_file(path, f"{name}.{file_name}")

        for artifact in (
            "estimate",
            "calibrated",
            "nominal",
            "physical",
            "calibration",
            "summary",
        ):
            if files[f"{artifact}_a"].read_bytes() != files[
                f"{artifact}_b"
            ].read_bytes():
                raise ValueError(
                    f"{name} {artifact} replay mismatch"
                )

        physical_bytes = files["physical_a"].read_bytes()
        if physical_reference_bytes is None:
            physical_reference_bytes = physical_bytes
        elif physical_bytes != physical_reference_bytes:
            raise ValueError(
                f"{name} physical reference mismatch"
            )

        summary = load_json(files["summary_a"])
        if summary["scenario"] != name:
            raise ValueError(f"{name} summary scenario mismatch")
        if summary["online_time_calibration_enabled"] is not True:
            raise ValueError(
                f"{name} online time calibration is disabled"
            )

        expected_offset_s = (
            float(configured["camera_timestamp_offset_ms"])
            / 1000.0
        )
        actual_offset_s = float(
            summary["injected_camera_timestamp_offset_s"]
        )
        if not math.isclose(
            expected_offset_s,
            actual_offset_s,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError(f"{name} offset mismatch")

        current_camera_fingerprint = str(
            summary["camera_measurement_fingerprint"]
        )
        current_imu_fingerprint = str(
            summary["imu_measurement_fingerprint"]
        )

        if camera_fingerprint is None:
            camera_fingerprint = current_camera_fingerprint
            imu_fingerprint = current_imu_fingerprint
        elif (
            current_camera_fingerprint != camera_fingerprint
            or current_imu_fingerprint != imu_fingerprint
        ):
            raise ValueError(
                f"{name} measurement fingerprint mismatch"
            )

        estimate = read_position_trajectory_csv(
            files["estimate_a"],
            source_name=f"openvins-{name}-estimate",
        )
        calibrated_reference = read_position_trajectory_csv(
            files["calibrated_a"],
            source_name=f"openvins-{name}-calibrated-reference",
        )
        nominal_reference = read_position_trajectory_csv(
            files["nominal_a"],
            source_name=f"openvins-{name}-nominal-reference",
        )
        physical_reference = read_position_trajectory_csv(
            files["physical_a"],
            source_name=f"openvins-{name}-physical-reference",
        )

        calibrated_metrics = evaluate_position_trajectory(
            calibrated_reference,
            estimate,
        ).metrics
        nominal_metrics = evaluate_position_trajectory(
            nominal_reference,
            estimate,
        ).metrics
        physical_metrics = evaluate_position_trajectory(
            physical_reference,
            estimate,
        ).metrics

        timestamps, estimates, residuals = read_calibration(
            files["calibration_a"]
        )

        if len(timestamps) != nominal_metrics.sample_count:
            raise ValueError(
                f"{name} calibration and trajectory counts differ"
            )

        tail_start = timestamps[-1] - tail_window_s
        tail_residuals = [
            residual
            for timestamp, residual in zip(
                timestamps,
                residuals,
            )
            if timestamp >= tail_start
        ]
        tail_rmse_ms = rmse(tail_residuals) * 1000.0

        converged_at = convergence_time(
            timestamps,
            residuals,
            convergence_threshold_s,
            convergence_hold_s,
        )

        true_dt_s = float(summary["true_cam_to_imu_s"])
        target_dt_s = float(summary["target_cam_to_imu_s"])
        initial_dt_s = float(
            summary["initial_estimated_cam_to_imu_s"]
        )
        final_dt_s = float(
            summary["final_estimated_cam_to_imu_s"]
        )
        injected_offset_ms = expected_offset_s * 1000.0
        estimated_correction_ms = (
            true_dt_s - final_dt_s
        ) * 1000.0

        scenario_results.append(
            {
                "calibration_aware_max_m": (
                    calibrated_metrics.position_max_m
                ),
                "calibration_aware_rmse_m": (
                    calibrated_metrics.position_rmse_m
                ),
                "converged_within_run": (
                    converged_at is not None
                ),
                "convergence_time_s": converged_at,
                "correction_error_ms": (
                    estimated_correction_ms
                    - injected_offset_ms
                ),
                "estimated_timestamp_correction_ms": (
                    estimated_correction_ms
                ),
                "final_calibration_residual_ms": (
                    final_dt_s - target_dt_s
                )
                * 1000.0,
                "final_estimated_cam_to_imu_ms": (
                    final_dt_s * 1000.0
                ),
                "initial_estimated_cam_to_imu_ms": (
                    initial_dt_s * 1000.0
                ),
                "injected_offset_ms": injected_offset_ms,
                "nominal_clock_max_m": (
                    nominal_metrics.position_max_m
                ),
                "nominal_clock_rmse_m": (
                    nominal_metrics.position_rmse_m
                ),
                "physical_time_max_m": (
                    physical_metrics.position_max_m
                ),
                "physical_time_rmse_m": (
                    physical_metrics.position_rmse_m
                ),
                "sample_count": nominal_metrics.sample_count,
                "scenario": name,
                "tail_calibration_rmse_ms": tail_rmse_ms,
                "target_cam_to_imu_ms": target_dt_s * 1000.0,
                "true_cam_to_imu_ms": true_dt_s * 1000.0,
            }
        )

        scenario_artifacts[name] = {
            "calibration_sha256": sha256(files["calibration_a"]),
            "estimate_sha256": sha256(files["estimate_a"]),
            "reference_calibrated_sha256": sha256(
                files["calibrated_a"]
            ),
            "reference_nominal_sha256": sha256(
                files["nominal_a"]
            ),
            "reference_physical_sha256": sha256(
                files["physical_a"]
            ),
            "run_log_sha256": sha256(files["log_a"]),
            "summary_sha256": sha256(files["summary_a"]),
        }

    baseline = scenario_results[0]
    baseline_nominal_rmse = float(
        baseline["nominal_clock_rmse_m"]
    )
    baseline_calibrated_rmse = float(
        baseline["calibration_aware_rmse_m"]
    )

    if not math.isclose(
        baseline_nominal_rmse,
        expected_baseline_rmse,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            "timestamp runner baseline does not reproduce committed "
            "OpenVINS baseline"
        )

    for result in scenario_results:
        result["nominal_clock_rmse_ratio"] = (
            float(result["nominal_clock_rmse_m"])
            / baseline_nominal_rmse
        )
        result["calibration_aware_rmse_ratio"] = (
            float(result["calibration_aware_rmse_m"])
            / baseline_calibrated_rmse
        )

    baseline["nominal_clock_rmse_ratio"] = 1.0
    baseline["calibration_aware_rmse_ratio"] = 1.0

    if camera_fingerprint is None or imu_fingerprint is None:
        raise ValueError("measurement fingerprints are missing")

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    results_payload = {
        "calibration_convergence_definition": {
            "hold_s": convergence_hold_s,
            "tail_window_s": tail_window_s,
            "threshold_ms": (
                convergence_threshold_s * 1000.0
            ),
        },
        "experiment": "openvins-camera-timestamp-offset",
        "scenarios": scenario_results,
        "schema_version": 1,
    }

    manifest = {
        "experiment": "openvins-camera-timestamp-offset",
        "experiment_config_sha256": sha256(
            args.experiment_config
        ),
        "measurement_realization": {
            "camera_fingerprint": camera_fingerprint,
            "imu_fingerprint": imu_fingerprint,
        },
        "official_configuration_sha256": sha256(
            args.official_config
        ),
        "official_reproduction_manifest_sha256": sha256(
            args.official_manifest
        ),
        "official_source_modified": False,
        "online_time_calibration_enabled": True,
        "release_tag": "v2.7",
        "runner": {
            "binary_sha256": sha256(args.runner_binary),
            "cmake_sha256": sha256(args.runner_cmake),
            "source_sha256": sha256(args.runner_source),
        },
        "runner_source_location": "external-only",
        "scenario_artifacts": scenario_artifacts,
        "schema_version": 1,
        "upstream_commit": EXPECTED_COMMIT,
        "verification": {
            "all_scenario_replays_byte_identical": True,
            "common_measurement_realization": True,
            "frame_mapping": (
                "openvins-global-xyz-to-veranav-ned"
            ),
            "output_schema": "veranav-position-trajectory-v1",
            "physical_reference_trajectories_byte_identical": True,
        },
    }

    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "results.json").write_text(
        json.dumps(
            results_payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    columns = [
        "scenario",
        "injected_offset_ms",
        "sample_count",
        "true_cam_to_imu_ms",
        "target_cam_to_imu_ms",
        "initial_estimated_cam_to_imu_ms",
        "final_estimated_cam_to_imu_ms",
        "final_calibration_residual_ms",
        "tail_calibration_rmse_ms",
        "estimated_timestamp_correction_ms",
        "correction_error_ms",
        "converged_within_run",
        "convergence_time_s",
        "nominal_clock_rmse_m",
        "nominal_clock_max_m",
        "nominal_clock_rmse_ratio",
        "calibration_aware_rmse_m",
        "calibration_aware_max_m",
        "calibration_aware_rmse_ratio",
        "physical_time_rmse_m",
        "physical_time_max_m",
    ]

    with (output / "results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=columns,
            lineterminator="\n",
        )
        writer.writeheader()

        for result in scenario_results:
            writer.writerow(
                {
                    key: (
                        ""
                        if result[key] is None
                        else (
                            f"{result[key]:.12g}"
                            if isinstance(result[key], float)
                            else result[key]
                        )
                    )
                    for key in columns
                }
            )

    table_rows = []
    for result in scenario_results:
        convergence = (
            f"{result['convergence_time_s']:.3f}"
            if result["convergence_time_s"] is not None
            else "not converged"
        )
        table_rows.append(
            "| {scenario} | {offset:.1f} | {nominal:.6f} | "
            "{calibrated:.6f} | {final_dt:.3f} | {target_dt:.3f} | "
            "{residual:.3f} | {convergence} |".format(
                scenario=result["scenario"],
                offset=result["injected_offset_ms"],
                nominal=result["nominal_clock_rmse_m"],
                calibrated=result["calibration_aware_rmse_m"],
                final_dt=result[
                    "final_estimated_cam_to_imu_ms"
                ],
                target_dt=result["target_cam_to_imu_ms"],
                residual=result["final_calibration_residual_ms"],
                convergence=convergence,
            )
        )

    report = f"""# OpenVINS camera timestamp-offset experiment

## Purpose

This deterministic sweep evaluates constant camera timestamp biases
with the official OpenVINS v2.7 simulation configuration. The official
configuration enables online camera-to-IMU time-offset calibration.

Positive injection means that a camera measurement is reported later
than its physical acquisition time. For an injected offset `delta`, the
consistent camera-to-IMU calibration target is:

`target = true_camera_to_imu_offset - delta`

Nine scenarios are evaluated: baseline and ±5 ms, ±10 ms, ±20 ms and
±50 ms timestamp biases. Each scenario is executed twice.

## Pairing and determinism

The runner hashes the raw simulated camera observations and IMU
measurements before injecting the timestamp bias. All scenarios must
have identical camera and IMU fingerprints. Physical-time reference
trajectories must also be byte-identical across scenarios.

Estimate, reference, calibration and summary files must be
byte-identical across the two executions of each scenario.

## Error views

Three position-error views are retained:

- nominal-clock error: ground truth at the reported camera timestamp
  plus the simulator true camera-to-IMU offset
- calibration-aware error: ground truth at the reported camera
  timestamp plus the filter's current estimated camera-to-IMU offset
- physical-time error: ground truth at the original physical
  acquisition time

The nominal-clock view represents downstream use that assumes the
nominal time mapping. The calibration-aware view measures the internal
state after applying OpenVINS online temporal calibration.

## Results

| Scenario | Injected offset (ms) | Nominal-clock RMSE (m) | Calibration-aware RMSE (m) | Final estimated offset (ms) | Target offset (ms) | Final residual (ms) | Calibration convergence (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(table_rows)}

Calibration convergence requires the absolute temporal calibration
residual to remain within 1 ms for 10 s. Tail calibration RMSE is
computed over the final 20 s.

## Interpretation boundary

This experiment measures one official deterministic simulation
trajectory with online temporal calibration enabled. It does not
represent fixed-calibration behavior and does not yet establish a
population-level timing reliability boundary. A paired follow-up with
online temporal calibration disabled is required to separate intrinsic
estimator sensitivity from calibration compensation.

Official OpenVINS source files remain unchanged. The GPL-linked runner,
raw trajectories and logs remain outside the Apache-2.0 repository.
"""

    (output / "report.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print(f"scenario_count={len(scenario_results)}")
    print(f"baseline_nominal_rmse_m={baseline_nominal_rmse:.9f}")
    print(
        f"baseline_calibration_aware_rmse_m="
        f"{baseline_calibrated_rmse:.9f}"
    )
    print(f"camera_measurement_fingerprint={camera_fingerprint}")
    print(f"imu_measurement_fingerprint={imu_fingerprint}")

    for result in scenario_results:
        print(
            f"{result['scenario']}_nominal_rmse_m="
            f"{result['nominal_clock_rmse_m']:.9f}"
        )
        print(
            f"{result['scenario']}_calibrated_rmse_m="
            f"{result['calibration_aware_rmse_m']:.9f}"
        )
        print(
            f"{result['scenario']}_final_residual_ms="
            f"{result['final_calibration_residual_ms']:.9f}"
        )
        print(
            f"{result['scenario']}_convergence_time_s="
            f"{result['convergence_time_s']}"
        )

    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
