#!/usr/bin/env python3
"""Import fixed versus online OpenVINS temporal-calibration results."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

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
    parser.add_argument("--fixed-openvins-config", type=Path, required=True)
    parser.add_argument("--official-manifest", type=Path, required=True)
    parser.add_argument("--online-manifest", type=Path, required=True)
    parser.add_argument("--online-results", type=Path, required=True)
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


def main() -> int:
    args = arguments()

    if args.upstream_commit != EXPECTED_COMMIT:
        raise ValueError("unexpected OpenVINS upstream commit")

    for name, path in {
        "experiment_config": args.experiment_config,
        "official_config": args.official_config,
        "fixed_openvins_config": args.fixed_openvins_config,
        "official_manifest": args.official_manifest,
        "online_manifest": args.online_manifest,
        "online_results": args.online_results,
        "runner_source": args.runner_source,
        "runner_cmake": args.runner_cmake,
        "runner_binary": args.runner_binary,
    }.items():
        require_file(path, name)

    config = load_json(args.experiment_config)
    official = load_json(args.official_manifest)
    online_manifest = load_json(args.online_manifest)
    online_results = load_json(args.online_results)

    if config["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("experiment configuration commit mismatch")
    if config["online_time_calibration_enabled"] is not False:
        raise ValueError("fixed experiment configuration enables calibration")
    if official["upstream"]["commit"] != EXPECTED_COMMIT:
        raise ValueError("official reproduction commit mismatch")
    if online_manifest["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("online experiment commit mismatch")
    if online_manifest["online_time_calibration_enabled"] is not True:
        raise ValueError("online comparison experiment is not online")

    configured_names = tuple(
        item["name"]
        for item in config["scenarios"]
    )
    if configured_names != EXPECTED_SCENARIOS:
        raise ValueError("fixed scenario order mismatch")

    online_by_name = {
        item["scenario"]: item
        for item in online_results["scenarios"]
    }
    if tuple(online_by_name) != EXPECTED_SCENARIOS:
        raise ValueError("online scenario order mismatch")

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

        if files["calibrated_a"].read_bytes() != files[
            "nominal_a"
        ].read_bytes():
            raise ValueError(
                f"{name} fixed calibrated and nominal references differ"
            )

        physical_bytes = files["physical_a"].read_bytes()
        if physical_reference_bytes is None:
            physical_reference_bytes = physical_bytes
        elif physical_bytes != physical_reference_bytes:
            raise ValueError(
                f"{name} fixed physical reference mismatch"
            )

        summary = load_json(files["summary_a"])
        if summary["scenario"] != name:
            raise ValueError(f"{name} summary scenario mismatch")
        if summary["online_time_calibration_enabled"] is not False:
            raise ValueError(
                f"{name} unexpectedly enables online calibration"
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

        initial_dt_s = float(
            summary["initial_estimated_cam_to_imu_s"]
        )
        final_dt_s = float(
            summary["final_estimated_cam_to_imu_s"]
        )
        if not math.isclose(
            initial_dt_s,
            final_dt_s,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise ValueError(
                f"{name} fixed temporal calibration changed"
            )

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
                f"{name} fixed measurement fingerprint mismatch"
            )

        estimate = read_position_trajectory_csv(
            files["estimate_a"],
            source_name=f"openvins-fixed-{name}-estimate",
        )
        nominal_reference = read_position_trajectory_csv(
            files["nominal_a"],
            source_name=f"openvins-fixed-{name}-nominal",
        )
        physical_reference = read_position_trajectory_csv(
            files["physical_a"],
            source_name=f"openvins-fixed-{name}-physical",
        )

        nominal_metrics = evaluate_position_trajectory(
            nominal_reference,
            estimate,
        ).metrics
        physical_metrics = evaluate_position_trajectory(
            physical_reference,
            estimate,
        ).metrics

        online = online_by_name[name]
        fixed_residual_ms = (
            final_dt_s - float(summary["target_cam_to_imu_s"])
        ) * 1000.0
        online_residual_ms = float(
            online["final_calibration_residual_ms"]
        )
        online_calibrated_rmse = float(
            online["calibration_aware_rmse_m"]
        )

        reduction_m = (
            nominal_metrics.position_rmse_m
            - online_calibrated_rmse
        )
        reduction_fraction = (
            reduction_m / nominal_metrics.position_rmse_m
        )
        online_to_fixed_ratio = (
            online_calibrated_rmse
            / nominal_metrics.position_rmse_m
        )

        if abs(fixed_residual_ms) > 1e-9:
            parameter_reduction = (
                1.0
                - abs(online_residual_ms)
                / abs(fixed_residual_ms)
            )
        else:
            parameter_reduction = None

        scenario_results.append(
            {
                "fixed_final_calibration_residual_ms": (
                    fixed_residual_ms
                ),
                "fixed_nominal_max_m": (
                    nominal_metrics.position_max_m
                ),
                "fixed_nominal_rmse_m": (
                    nominal_metrics.position_rmse_m
                ),
                "fixed_physical_max_m": (
                    physical_metrics.position_max_m
                ),
                "fixed_physical_rmse_m": (
                    physical_metrics.position_rmse_m
                ),
                "injected_offset_ms": (
                    expected_offset_s * 1000.0
                ),
                "online_calibration_aware_rmse_m": (
                    online_calibrated_rmse
                ),
                "online_calibration_rmse_reduction_fraction": (
                    reduction_fraction
                ),
                "online_calibration_rmse_reduction_m": reduction_m,
                "online_convergence_time_s": (
                    online["convergence_time_s"]
                ),
                "online_final_calibration_residual_ms": (
                    online_residual_ms
                ),
                "online_nominal_rmse_m": float(
                    online["nominal_clock_rmse_m"]
                ),
                "online_to_fixed_rmse_ratio": (
                    online_to_fixed_ratio
                ),
                "parameter_residual_reduction_fraction": (
                    parameter_reduction
                ),
                "sample_count": nominal_metrics.sample_count,
                "scenario": name,
            }
        )

        scenario_artifacts[name] = {
            "calibration_sha256": sha256(files["calibration_a"]),
            "estimate_sha256": sha256(files["estimate_a"]),
            "reference_nominal_sha256": sha256(
                files["nominal_a"]
            ),
            "reference_physical_sha256": sha256(
                files["physical_a"]
            ),
            "run_log_sha256": sha256(files["log_a"]),
            "summary_sha256": sha256(files["summary_a"]),
        }

    baseline_rmse = float(
        scenario_results[0]["fixed_nominal_rmse_m"]
    )
    if baseline_rmse <= 0.0:
        raise ValueError("fixed baseline RMSE must be positive")

    for result in scenario_results:
        result["fixed_rmse_ratio_to_fixed_baseline"] = (
            float(result["fixed_nominal_rmse_m"])
            / baseline_rmse
        )

    scenario_results[0]["fixed_rmse_ratio_to_fixed_baseline"] = 1.0

    if camera_fingerprint is None or imu_fingerprint is None:
        raise ValueError("fixed measurement fingerprints are missing")

    if (
        camera_fingerprint
        != online_manifest["measurement_realization"][
            "camera_fingerprint"
        ]
        or imu_fingerprint
        != online_manifest["measurement_realization"][
            "imu_fingerprint"
        ]
    ):
        raise ValueError(
            "fixed and online measurement fingerprints differ"
        )

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    results_payload = {
        "experiment": (
            "openvins-camera-timestamp-offset-fixed-calibration"
        ),
        "paired_online_experiment": (
            "openvins-camera-timestamp-offset"
        ),
        "scenarios": scenario_results,
        "schema_version": 1,
    }

    manifest = {
        "configuration_change": (
            "calib_cam_timeoffset:true-to-false"
        ),
        "configurations": {
            "fixed_config_sha256": sha256(
                args.fixed_openvins_config
            ),
            "official_config_sha256": sha256(
                args.official_config
            ),
        },
        "experiment": (
            "openvins-camera-timestamp-offset-fixed-calibration"
        ),
        "experiment_config_sha256": sha256(
            args.experiment_config
        ),
        "measurement_realization": {
            "camera_fingerprint": camera_fingerprint,
            "imu_fingerprint": imu_fingerprint,
        },
        "official_reproduction_manifest_sha256": sha256(
            args.official_manifest
        ),
        "official_source_modified": False,
        "online_experiment_manifest_sha256": sha256(
            args.online_manifest
        ),
        "online_experiment_results_sha256": sha256(
            args.online_results
        ),
        "online_time_calibration_enabled": False,
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
            "fixed_calibrated_and_nominal_references_byte_identical": True,
            "frame_mapping": (
                "openvins-global-xyz-to-veranav-ned"
            ),
            "online_fixed_physical_references_byte_identical": True,
            "output_schema": "veranav-position-trajectory-v1",
            "paired_online_fixed_measurement_realization": True,
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
        "fixed_final_calibration_residual_ms",
        "fixed_nominal_rmse_m",
        "fixed_nominal_max_m",
        "fixed_physical_rmse_m",
        "fixed_physical_max_m",
        "fixed_rmse_ratio_to_fixed_baseline",
        "online_nominal_rmse_m",
        "online_calibration_aware_rmse_m",
        "online_final_calibration_residual_ms",
        "online_convergence_time_s",
        "online_calibration_rmse_reduction_m",
        "online_calibration_rmse_reduction_fraction",
        "online_to_fixed_rmse_ratio",
        "parameter_residual_reduction_fraction",
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
        parameter_reduction = result[
            "parameter_residual_reduction_fraction"
        ]
        parameter_text = (
            "n/a"
            if parameter_reduction is None
            else f"{parameter_reduction:.3f}"
        )
        table_rows.append(
            "| {scenario} | {offset:.1f} | {fixed:.6f} | "
            "{online:.6f} | {ratio:.3f} | {reduction:.3f} | "
            "{fixed_residual:.3f} | {online_residual:.3f} | "
            "{parameter_reduction} |".format(
                scenario=result["scenario"],
                offset=result["injected_offset_ms"],
                fixed=result["fixed_nominal_rmse_m"],
                online=result["online_calibration_aware_rmse_m"],
                ratio=result["online_to_fixed_rmse_ratio"],
                reduction=result[
                    "online_calibration_rmse_reduction_fraction"
                ],
                fixed_residual=result[
                    "fixed_final_calibration_residual_ms"
                ],
                online_residual=result[
                    "online_final_calibration_residual_ms"
                ],
                parameter_reduction=parameter_text,
            )
        )

    report = f"""# OpenVINS fixed versus online time-calibration comparison

## Purpose

This paired experiment repeats the signed camera timestamp-offset sweep
with OpenVINS online camera-to-IMU time calibration disabled. It is
compared directly with the committed online-calibration experiment.

The fixed OpenVINS configuration is derived from the official v2.7
configuration by changing exactly one entry:

`calib_cam_timeoffset: true` to `calib_cam_timeoffset: false`

Official OpenVINS source files and the official configuration remain
unchanged.

## Pairing

The same nine scenarios and seed are used: baseline and ±5 ms, ±10 ms,
±20 ms and ±50 ms.

All fixed-calibration scenarios are run twice. Their raw camera and IMU
measurement fingerprints must match the online-calibration experiment.
Physical-time reference trajectories must be byte-identical between
online and fixed runs.

With temporal calibration fixed, the calibration-aware and nominal
reference trajectories must be byte-identical.

## Results

| Scenario | Injected offset (ms) | Fixed-calibration RMSE (m) | Online calibration-aware RMSE (m) | Online/fixed RMSE ratio | Online RMSE reduction fraction | Fixed parameter residual (ms) | Online parameter residual (ms) | Parameter residual reduction fraction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(table_rows)}

A positive RMSE reduction fraction means online temporal calibration
reduced position RMSE relative to the paired fixed-calibration run. A
negative value means the online-calibration trajectory had higher RMSE
for that deterministic scenario.

Parameter residual reduction measures how much of the fixed temporal
mismatch was removed by online estimation. Baseline has no injected
mismatch, so that fraction is not defined.

## Interpretation boundary

This experiment separates online calibration compensation from fixed
temporal mismatch on one deterministic official simulation trajectory.
Non-monotonic position RMSE remains possible because filter update
history and trajectory dynamics are deterministic. Population-level
timing reliability requires additional trajectories and seeds.

The derived configuration, GPL-linked runner, raw trajectories and logs
remain outside the Apache-2.0 VeraNav repository.
"""

    (output / "report.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print(f"scenario_count={len(scenario_results)}")
    print(f"fixed_baseline_rmse_m={baseline_rmse:.9f}")
    print(f"camera_measurement_fingerprint={camera_fingerprint}")
    print(f"imu_measurement_fingerprint={imu_fingerprint}")

    for result in scenario_results:
        print(
            f"{result['scenario']}_fixed_rmse_m="
            f"{result['fixed_nominal_rmse_m']:.9f}"
        )
        print(
            f"{result['scenario']}_online_calibrated_rmse_m="
            f"{result['online_calibration_aware_rmse_m']:.9f}"
        )
        print(
            f"{result['scenario']}_online_reduction_fraction="
            f"{result['online_calibration_rmse_reduction_fraction']:.9f}"
        )
        print(
            f"{result['scenario']}_fixed_residual_ms="
            f"{result['fixed_final_calibration_residual_ms']:.9f}"
        )

    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
