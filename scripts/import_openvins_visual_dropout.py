#!/usr/bin/env python3
"""Import a deterministic OpenVINS visual-observation dropout sweep."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from veranav.adapter_io import read_position_trajectory_csv
from veranav.trajectory import evaluate_position_trajectory


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_SCENARIOS = (
    "baseline",
    "random-10",
    "random-30",
    "random-50",
    "burst-1s",
    "burst-3s",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--experiment-config", type=Path, required=True)
    parser.add_argument("--official-config", type=Path, required=True)
    parser.add_argument("--official-manifest", type=Path, required=True)
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
        "official_manifest": args.official_manifest,
        "runner_source": args.runner_source,
        "runner_cmake": args.runner_cmake,
        "runner_binary": args.runner_binary,
    }.items():
        require_file(path, name)

    experiment_config = load_json(args.experiment_config)
    official_manifest = load_json(args.official_manifest)

    if experiment_config["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("experiment configuration commit mismatch")
    if official_manifest["upstream"]["commit"] != EXPECTED_COMMIT:
        raise ValueError("official reproduction commit mismatch")
    if (
        official_manifest["verification"]["official_source_modified"]
        is not False
    ):
        raise ValueError("official source modification flag is not false")

    configured_names = tuple(
        scenario["name"]
        for scenario in experiment_config["scenarios"]
    )
    if configured_names != EXPECTED_SCENARIOS:
        raise ValueError("experiment configuration scenario order mismatch")

    baseline_reference: bytes | None = None
    scenario_results: list[dict[str, Any]] = []
    scenario_hashes: dict[str, dict[str, str]] = {}

    for configured in experiment_config["scenarios"]:
        name = configured["name"]
        scenario_root = args.evidence_root / name
        run_a = scenario_root / "run-a"
        run_b = scenario_root / "run-b"

        files = {
            "estimate_a": run_a / "estimate.csv",
            "reference_a": run_a / "reference.csv",
            "summary_a": run_a / "summary.json",
            "log_a": run_a / "run.log",
            "estimate_b": run_b / "estimate.csv",
            "reference_b": run_b / "reference.csv",
            "summary_b": run_b / "summary.json",
            "log_b": run_b / "run.log",
        }
        for file_name, path in files.items():
            require_file(path, f"{name}.{file_name}")

        if files["estimate_a"].read_bytes() != files[
            "estimate_b"
        ].read_bytes():
            raise ValueError(f"{name} estimate replay mismatch")
        if files["reference_a"].read_bytes() != files[
            "reference_b"
        ].read_bytes():
            raise ValueError(f"{name} reference replay mismatch")
        if files["summary_a"].read_bytes() != files[
            "summary_b"
        ].read_bytes():
            raise ValueError(f"{name} summary replay mismatch")

        reference_bytes = files["reference_a"].read_bytes()
        if baseline_reference is None:
            baseline_reference = reference_bytes
        elif reference_bytes != baseline_reference:
            raise ValueError(
                f"{name} does not use the paired baseline reference"
            )

        summary = load_json(files["summary_a"])
        if summary["scenario"] != name:
            raise ValueError(f"{name} summary scenario mismatch")
        if summary["mode"] != configured["mode"]:
            raise ValueError(f"{name} summary mode mismatch")
        if int(summary["seed"]) != int(configured["seed"]):
            raise ValueError(f"{name} summary seed mismatch")

        estimate = read_position_trajectory_csv(
            files["estimate_a"],
            source_name=f"openvins-{name}-estimate",
        )
        reference = read_position_trajectory_csv(
            files["reference_a"],
            source_name=f"openvins-{name}-reference",
        )
        evaluation = evaluate_position_trajectory(
            reference,
            estimate,
        )
        values = evaluation.metrics

        scenario_results.append(
            {
                "burst_duration_s": float(
                    configured["burst_duration_s"]
                ),
                "burst_start_s": float(
                    configured["burst_start_s"]
                ),
                "degraded_frames": int(
                    summary["degraded_frames"]
                ),
                "dropped_observations": int(
                    summary["dropped_observations"]
                ),
                "mode": configured["mode"],
                "position_max_m": values.position_max_m,
                "position_mean_m": values.position_mean_m,
                "position_rmse_m": values.position_rmse_m,
                "probability": float(configured["probability"]),
                "realized_frame_drop_fraction": float(
                    summary["realized_frame_drop_fraction"]
                ),
                "sample_count": values.sample_count,
                "scenario": name,
                "seed": int(configured["seed"]),
                "total_frames": int(summary["total_frames"]),
            }
        )

        scenario_hashes[name] = {
            "estimate_sha256": sha256(files["estimate_a"]),
            "reference_sha256": sha256(files["reference_a"]),
            "run_log_sha256": sha256(files["log_a"]),
            "summary_sha256": sha256(files["summary_a"]),
        }

    baseline = scenario_results[0]
    baseline_rmse = float(baseline["position_rmse_m"])
    baseline_max = float(baseline["position_max_m"])

    if baseline_rmse <= 0.0 or baseline_max <= 0.0:
        raise ValueError("baseline metrics must be positive")

    for result in scenario_results:
        rmse = float(result["position_rmse_m"])
        maximum = float(result["position_max_m"])

        result["rmse_delta_m"] = max(0.0, rmse - baseline_rmse)
        result["rmse_ratio"] = rmse / baseline_rmse
        result["max_delta_m"] = max(0.0, maximum - baseline_max)
        result["max_ratio"] = maximum / baseline_max

    baseline["rmse_delta_m"] = 0.0
    baseline["rmse_ratio"] = 1.0
    baseline["max_delta_m"] = 0.0
    baseline["max_ratio"] = 1.0

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    results_payload = {
        "experiment": "openvins-visual-observation-dropout",
        "scenarios": scenario_results,
        "schema_version": 1,
    }

    manifest = {
        "experiment": "openvins-visual-observation-dropout",
        "experiment_config_sha256": sha256(
            args.experiment_config
        ),
        "official_configuration_sha256": sha256(
            args.official_config
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
        "scenario_artifacts": scenario_hashes,
        "schema_version": 1,
        "upstream_commit": EXPECTED_COMMIT,
        "verification": {
            "all_scenario_replays_byte_identical": True,
            "frame_mapping": (
                "openvins-global-xyz-to-veranav-ned"
            ),
            "output_schema": "veranav-position-trajectory-v1",
            "paired_reference_trajectories_byte_identical": True,
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
        "mode",
        "probability",
        "burst_start_s",
        "burst_duration_s",
        "seed",
        "total_frames",
        "degraded_frames",
        "realized_frame_drop_fraction",
        "dropped_observations",
        "sample_count",
        "position_rmse_m",
        "position_mean_m",
        "position_max_m",
        "rmse_delta_m",
        "rmse_ratio",
        "max_delta_m",
        "max_ratio",
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
                        f"{result[key]:.12g}"
                        if isinstance(result[key], float)
                        else result[key]
                    )
                    for key in columns
                }
            )

    rows = []
    for result in scenario_results:
        rows.append(
            "| {scenario} | {drop:.4f} | {rmse:.6f} | "
            "{rmse_ratio:.3f} | {maximum:.6f} | "
            "{max_ratio:.3f} |".format(
                scenario=result["scenario"],
                drop=result["realized_frame_drop_fraction"],
                rmse=result["position_rmse_m"],
                rmse_ratio=result["rmse_ratio"],
                maximum=result["position_max_m"],
                max_ratio=result["max_ratio"],
            )
        )

    report = f"""# OpenVINS visual-observation dropout experiment

## Scope

This deterministic sensitivity sweep uses OpenVINS v2.7 commit
`{EXPECTED_COMMIT}`. Selected camera frames retain their timestamps but
receive empty feature sets, so the filter continues propagating while
visual observations are unavailable.

Six fixed scenarios are evaluated:

- no degradation
- Bernoulli whole-frame observation loss at 10%, 30% and 50%
- continuous whole-frame observation loss for 1 s and 3 s beginning
  30 s after the first processed camera frame

Each scenario is executed twice. Estimate, reference and summary files
must be byte-identical across replays. All six scenarios must also use
the same byte-identical reference trajectory.

## Results

| Scenario | Realized frame loss | Position RMSE (m) | RMSE ratio | Maximum error (m) | Maximum ratio |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## Interpretation boundary

This is a deterministic structured-degradation sweep on one official
OpenVINS simulation configuration. It establishes sensitivity and
engineering reproducibility, but it does not provide population-level
confidence intervals or a formal reliability boundary. Those require
additional seeds, trajectories and cross-estimator paired studies.

The GPL-linked degradation runner remains outside the Apache-2.0
VeraNav repository. Official OpenVINS source files are unchanged.
"""

    (output / "report.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print(f"scenario_count={len(scenario_results)}")
    print(f"baseline_rmse_m={baseline_rmse:.9f}")
    for result in scenario_results:
        print(
            f"{result['scenario']}_rmse_m="
            f"{result['position_rmse_m']:.9f}"
        )
        print(
            f"{result['scenario']}_drop_fraction="
            f"{result['realized_frame_drop_fraction']:.9f}"
        )
    print(f"output_dir={output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
