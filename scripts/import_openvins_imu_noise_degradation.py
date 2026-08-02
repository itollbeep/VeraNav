#!/usr/bin/env python3
"""Import deterministic OpenVINS IMU-noise degradation evidence."""

from __future__ import annotations

import argparse
import bisect
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
    "white-2x",
    "white-5x",
    "white-10x",
    "randomwalk-2x",
    "randomwalk-5x",
    "randomwalk-10x",
    "all-2x",
    "all-5x",
    "all-10x",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--scenario-config-root", type=Path, required=True)
    parser.add_argument("--experiment-config", type=Path, required=True)
    parser.add_argument("--official-config", type=Path, required=True)
    parser.add_argument("--official-imu-config", type=Path, required=True)
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


def read_consistency(
    path: Path,
) -> dict[str, list[float]]:
    columns = {
        "timestamp_s": [],
        "cov_trace": [],
        "position_nees": [],
    }

    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        expected = {
            "timestamp_s",
            "error_north_m",
            "error_east_m",
            "error_down_m",
            "cov_nn",
            "cov_ee",
            "cov_dd",
            "cov_trace",
            "position_nees",
        }
        if set(reader.fieldnames or ()) != expected:
            raise ValueError("unexpected consistency CSV columns")

        previous = None
        for row in reader:
            timestamp = float(row["timestamp_s"])
            cov_trace = float(row["cov_trace"])
            nees = float(row["position_nees"])

            if not all(
                math.isfinite(value)
                for value in (timestamp, cov_trace, nees)
            ):
                raise ValueError("non-finite consistency value")
            if cov_trace <= 0.0 or nees < 0.0:
                raise ValueError("invalid covariance or NEES value")
            if previous is not None and timestamp <= previous:
                raise ValueError(
                    "non-increasing consistency timestamp"
                )

            columns["timestamp_s"].append(timestamp)
            columns["cov_trace"].append(cov_trace)
            columns["position_nees"].append(nees)
            previous = timestamp

    if len(columns["timestamp_s"]) < 100:
        raise ValueError("too few consistency samples")

    return columns


def nearest_rank(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires samples")
    ordered = sorted(values)
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[min(len(ordered) - 1, rank - 1)]


def position_errors(
    estimate_positions: Sequence[tuple[float, float, float]],
    reference_positions: Sequence[tuple[float, float, float]],
) -> list[float]:
    if len(estimate_positions) != len(reference_positions):
        raise ValueError("estimate/reference sample counts differ")

    return [
        math.sqrt(
            (estimate[0] - reference[0]) ** 2
            + (estimate[1] - reference[1]) ** 2
            + (estimate[2] - reference[2]) ** 2
        )
        for estimate, reference in zip(
            estimate_positions,
            reference_positions,
        )
    ]


def rolling_rmse(
    timestamps: Sequence[float],
    errors: Sequence[float],
    window_s: float,
) -> list[float]:
    squares = [value * value for value in errors]
    prefix = [0.0]
    for value in squares:
        prefix.append(prefix[-1] + value)

    result = []
    for index, timestamp in enumerate(timestamps):
        stop = bisect.bisect_left(
            timestamps,
            timestamp + window_s,
            lo=index + 1,
        )
        if stop <= index:
            stop = index + 1
        count = stop - index
        result.append(
            math.sqrt((prefix[stop] - prefix[index]) / count)
        )
    return result


def sustained_failure_onset(
    timestamps: Sequence[float],
    errors: Sequence[float],
    threshold_m: float = 1.0,
    rolling_window_s: float = 1.0,
    hold_s: float = 3.0,
) -> float | None:
    rolling = rolling_rmse(
        timestamps,
        errors,
        rolling_window_s,
    )

    for index, timestamp in enumerate(timestamps):
        hold_end = timestamp + hold_s
        if hold_end > timestamps[-1]:
            break

        stop = bisect.bisect_right(
            timestamps,
            hold_end,
            lo=index,
        )
        if all(value > threshold_m for value in rolling[index:stop]):
            return timestamp

    return None


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean requires samples")
    return math.fsum(values) / len(values)


def main() -> int:
    args = arguments()

    if args.upstream_commit != EXPECTED_COMMIT:
        raise ValueError("unexpected OpenVINS upstream commit")

    for name, path in {
        "experiment_config": args.experiment_config,
        "official_config": args.official_config,
        "official_imu_config": args.official_imu_config,
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
    nees_upper = float(
        config["consistency"]["position_nees_upper_95"]
    )

    scenario_results: list[dict[str, Any]] = []
    scenario_artifacts: dict[str, dict[str, str]] = {}
    scenario_config_hashes: dict[str, dict[str, str]] = {}
    reference_bytes: bytes | None = None
    camera_fingerprint: str | None = None
    nominal_imu_fingerprint: str | None = None

    for configured in config["scenarios"]:
        name = configured["name"]
        run_a = args.evidence_root / name / "run-a"
        run_b = args.evidence_root / name / "run-b"
        scenario_config_dir = args.scenario_config_root / name

        files = {
            "estimate_a": run_a / "estimate.csv",
            "reference_a": run_a / "reference.csv",
            "consistency_a": run_a / "consistency.csv",
            "summary_a": run_a / "summary.json",
            "log_a": run_a / "run.log",
            "estimate_b": run_b / "estimate.csv",
            "reference_b": run_b / "reference.csv",
            "consistency_b": run_b / "consistency.csv",
            "summary_b": run_b / "summary.json",
            "log_b": run_b / "run.log",
        }

        for file_name, path in files.items():
            require_file(path, f"{name}.{file_name}")

        for artifact in (
            "estimate",
            "reference",
            "consistency",
            "summary",
        ):
            if files[f"{artifact}_a"].read_bytes() != files[
                f"{artifact}_b"
            ].read_bytes():
                raise ValueError(
                    f"{name} {artifact} replay mismatch"
                )

        current_reference = files["reference_a"].read_bytes()
        if reference_bytes is None:
            reference_bytes = current_reference
        elif current_reference != reference_bytes:
            raise ValueError(
                f"{name} reference trajectory mismatch"
            )

        summary = load_json(files["summary_a"])
        if summary["scenario"] != name:
            raise ValueError(f"{name} summary scenario mismatch")
        if summary["estimator_uses_nominal_noise_model"] is not True:
            raise ValueError(
                f"{name} estimator does not use nominal noise model"
            )

        expected_white = float(
            configured["white_noise_scale"]
        )
        expected_rw = float(
            configured["random_walk_scale"]
        )

        if not math.isclose(
            float(summary["white_noise_scale"]),
            expected_white,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError(f"{name} white scale mismatch")
        if not math.isclose(
            float(summary["random_walk_scale"]),
            expected_rw,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError(f"{name} random-walk scale mismatch")

        current_camera_fingerprint = str(
            summary["camera_measurement_fingerprint"]
        )
        current_nominal_imu_fingerprint = str(
            summary["nominal_imu_measurement_fingerprint"]
        )

        if camera_fingerprint is None:
            camera_fingerprint = current_camera_fingerprint
            nominal_imu_fingerprint = (
                current_nominal_imu_fingerprint
            )
        elif (
            current_camera_fingerprint != camera_fingerprint
            or current_nominal_imu_fingerprint
            != nominal_imu_fingerprint
        ):
            raise ValueError(
                f"{name} common measurement realization mismatch"
            )

        estimate = read_position_trajectory_csv(
            files["estimate_a"],
            source_name=f"openvins-{name}-estimate",
        )
        reference = read_position_trajectory_csv(
            files["reference_a"],
            source_name=f"openvins-{name}-reference",
        )
        metrics = evaluate_position_trajectory(
            reference,
            estimate,
        ).metrics

        estimate_positions = [
            tuple(float(value) for value in row)
            for row in estimate.positions_n_m
        ]
        reference_positions = [
            tuple(float(value) for value in row)
            for row in reference.positions_n_m
        ]
        timestamps = [
            float(value)
            for value in estimate.timestamps_s
        ]
        errors = position_errors(
            estimate_positions,
            reference_positions,
        )

        consistency = read_consistency(
            files["consistency_a"]
        )
        if consistency["timestamp_s"] != timestamps:
            raise ValueError(
                f"{name} consistency timeline mismatch"
            )

        nees = consistency["position_nees"]
        cov_trace = consistency["cov_trace"]

        result = {
            "accelerometer_delta_rms_mps2": float(
                summary["accelerometer_delta_rms_mps2"]
            ),
            "availability_0_1m": (
                sum(error <= 0.1 for error in errors)
                / len(errors)
            ),
            "availability_0_5m": (
                sum(error <= 0.5 for error in errors)
                / len(errors)
            ),
            "availability_1m": (
                sum(error <= 1.0 for error in errors)
                / len(errors)
            ),
            "covariance_trace_mean_m2": mean(cov_trace),
            "gyroscope_delta_rms_radps": float(
                summary["gyroscope_delta_rms_radps"]
            ),
            "position_max_m": metrics.position_max_m,
            "position_mean_m": metrics.position_mean_m,
            "position_nees_95_coverage": (
                sum(value <= nees_upper for value in nees)
                / len(nees)
            ),
            "position_nees_mean": mean(nees),
            "position_nees_median": nearest_rank(nees, 0.50),
            "position_nees_p95": nearest_rank(nees, 0.95),
            "position_p95_m": nearest_rank(errors, 0.95),
            "position_rmse_m": metrics.position_rmse_m,
            "random_walk_scale": expected_rw,
            "sample_count": metrics.sample_count,
            "scenario": name,
            "sustained_failure_onset_s": sustained_failure_onset(
                timestamps,
                errors,
            ),
            "white_noise_scale": expected_white,
        }
        scenario_results.append(result)

        scenario_artifacts[name] = {
            "consistency_sha256": sha256(
                files["consistency_a"]
            ),
            "estimate_sha256": sha256(files["estimate_a"]),
            "reference_sha256": sha256(files["reference_a"]),
            "run_log_sha256": sha256(files["log_a"]),
            "summary_sha256": sha256(files["summary_a"]),
        }

        scenario_config_hashes[name] = {
            "estimator_config_sha256": sha256(
                scenario_config_dir / "estimator_config.yaml"
            ),
            "imu_config_sha256": sha256(
                scenario_config_dir / "kalibr_imu_chain.yaml"
            ),
        }

    baseline_rmse = float(
        scenario_results[0]["position_rmse_m"]
    )
    if not math.isclose(
        baseline_rmse,
        expected_baseline_rmse,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            "IMU-noise runner baseline does not reproduce committed "
            "OpenVINS baseline"
        )

    for result in scenario_results:
        result["rmse_ratio"] = (
            float(result["position_rmse_m"])
            / baseline_rmse
        )

    scenario_results[0]["rmse_ratio"] = 1.0

    if camera_fingerprint is None or nominal_imu_fingerprint is None:
        raise ValueError("measurement fingerprints are missing")

    baseline_summary = load_json(
        args.evidence_root / "baseline/run-a/summary.json"
    )
    if (
        baseline_summary["nominal_imu_measurement_fingerprint"]
        != baseline_summary["degraded_imu_measurement_fingerprint"]
    ):
        raise ValueError("baseline IMU fingerprints differ")

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    results_payload = {
        "consistency_definition": {
            "position_nees_dimension": 3,
            "position_nees_upper_95": nees_upper,
        },
        "experiment": "openvins-imu-noise-degradation",
        "scenarios": scenario_results,
        "schema_version": 1,
    }

    manifest = {
        "estimator_uses_nominal_noise_model": True,
        "experiment": "openvins-imu-noise-degradation",
        "experiment_config_sha256": sha256(
            args.experiment_config
        ),
        "measurement_realization": {
            "camera_fingerprint": camera_fingerprint,
            "nominal_imu_fingerprint": nominal_imu_fingerprint,
        },
        "official_configuration_sha256": sha256(
            args.official_config
        ),
        "official_imu_configuration_sha256": sha256(
            args.official_imu_config
        ),
        "official_reproduction_manifest_sha256": sha256(
            args.official_manifest
        ),
        "official_source_modified": False,
        "release_tag": "v2.7",
        "runner": {
            "binary_sha256": sha256(args.runner_binary),
            "cmake_sha256": sha256(args.runner_cmake),
            "source_sha256": sha256(args.runner_source),
        },
        "runner_source_location": "external-only",
        "scenario_artifacts": scenario_artifacts,
        "scenario_configuration_hashes": scenario_config_hashes,
        "schema_version": 1,
        "upstream_commit": EXPECTED_COMMIT,
        "verification": {
            "all_scenario_replays_byte_identical": True,
            "common_nominal_measurement_realization": True,
            "frame_mapping": (
                "openvins-global-xyz-to-veranav-ned"
            ),
            "output_schema": "veranav-position-trajectory-v1",
            "position_covariance_positive_definite": True,
            "reference_trajectories_byte_identical": True,
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
        "white_noise_scale",
        "random_walk_scale",
        "sample_count",
        "position_rmse_m",
        "position_mean_m",
        "position_p95_m",
        "position_max_m",
        "rmse_ratio",
        "availability_0_1m",
        "availability_0_5m",
        "availability_1m",
        "sustained_failure_onset_s",
        "position_nees_mean",
        "position_nees_median",
        "position_nees_p95",
        "position_nees_95_coverage",
        "covariance_trace_mean_m2",
        "gyroscope_delta_rms_radps",
        "accelerometer_delta_rms_mps2",
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
        onset = (
            "none"
            if result["sustained_failure_onset_s"] is None
            else f"{result['sustained_failure_onset_s']:.2f}"
        )
        table_rows.append(
            "| {scenario} | {white:.1f} | {rw:.1f} | "
            "{rmse:.6f} | {ratio:.3f} | {p95:.6f} | "
            "{maximum:.6f} | {availability:.4f} | "
            "{nees:.3f} | {coverage:.4f} | {onset} |".format(
                scenario=result["scenario"],
                white=result["white_noise_scale"],
                rw=result["random_walk_scale"],
                rmse=result["position_rmse_m"],
                ratio=result["rmse_ratio"],
                p95=result["position_p95_m"],
                maximum=result["position_max_m"],
                availability=result["availability_1m"],
                nees=result["position_nees_mean"],
                coverage=result["position_nees_95_coverage"],
                onset=onset,
            )
        )

    report = f"""# OpenVINS IMU-noise degradation experiment

## Purpose

This deterministic experiment evaluates OpenVINS sensitivity to
unmodelled IMU noise degradation. The estimator always uses the official
nominal OpenVINS v2.7 IMU noise model. A separate simulator uses derived
noise parameters.

The experiment distinguishes:

- white-noise density degradation
- bias random-walk degradation
- simultaneous white-noise and random-walk degradation

Each category is evaluated at 2×, 5× and 10× nominal magnitude, with a
nominal baseline.

## Pairing

For every scenario, a nominal simulator and a degraded simulator are
advanced in lockstep with the same official trajectory and measurement
seed.

The experiment is accepted only when:

- nominal and degraded camera observations are exactly identical
- nominal IMU fingerprints are identical across all scenarios
- event schedules and sample counts are identical
- every scenario is byte-identical across two executions
- all reference trajectories are byte-identical
- the baseline reproduces the committed OpenVINS RMSE within 1 nm

Only the degraded IMU stream is fed to the estimator. Camera
observations remain nominal.

## Consistency

The runner records the marginal 3D position covariance and computes
position NEES for every output sample.

For a three-dimensional position error, the retained 95% upper
chi-square threshold is `7.814727903251179`. The report includes mean,
median and p95 NEES together with the fraction of samples below this
upper threshold.

A high fraction below the upper threshold does not by itself prove
consistency because this single deterministic trajectory does not
provide an ensemble. The values are retained as diagnostic evidence.

## Results

| Scenario | White scale | Random-walk scale | RMSE (m) | RMSE ratio | p95 (m) | Maximum (m) | Availability ≤1 m | Mean position NEES | NEES ≤95% upper | Sustained 1 m failure onset (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(table_rows)}

## Interpretation boundary

The experiment measures a single official deterministic simulation
trajectory and deliberately keeps the estimator noise model nominal.
It therefore evaluates robustness to noise-model mismatch, not the
best achievable result after retuning process noise.

Population-level reliability requires additional trajectories, seeds
and paired estimator configurations with matched degraded noise models.

Official OpenVINS source and configuration files remain unchanged. The
GPL-linked runner, derived simulator configurations, raw trajectories
and consistency traces remain outside the Apache-2.0 repository.
"""

    (output / "report.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print(f"scenario_count={len(scenario_results)}")
    print(f"baseline_rmse_m={baseline_rmse:.9f}")
    print(f"camera_measurement_fingerprint={camera_fingerprint}")
    print(
        "nominal_imu_measurement_fingerprint="
        f"{nominal_imu_fingerprint}"
    )

    for result in scenario_results:
        print(
            f"{result['scenario']}_rmse_m="
            f"{result['position_rmse_m']:.9f}"
        )
        print(
            f"{result['scenario']}_rmse_ratio="
            f"{result['rmse_ratio']:.9f}"
        )
        print(
            f"{result['scenario']}_nees_mean="
            f"{result['position_nees_mean']:.9f}"
        )
        print(
            f"{result['scenario']}_availability_1m="
            f"{result['availability_1m']:.9f}"
        )
        print(
            f"{result['scenario']}_failure_onset_s="
            f"{result['sustained_failure_onset_s']}"
        )

    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
