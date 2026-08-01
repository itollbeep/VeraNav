#!/usr/bin/env python3
"""Import the deterministic OpenVINS multi-start visual-outage sweep."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_SCENARIOS = (
    "baseline",
    "burst-t030-d1",
    "burst-t030-d3",
    "burst-t090-d1",
    "burst-t090-d3",
    "burst-t150-d1",
    "burst-t150-d3",
    "burst-t210-d1",
    "burst-t210-d3",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--experiment-config", type=Path, required=True)
    parser.add_argument("--official-config", type=Path, required=True)
    parser.add_argument("--official-manifest", type=Path, required=True)
    parser.add_argument("--previous-manifest", type=Path, required=True)
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


def read_trajectory(
    path: Path,
) -> tuple[list[float], list[tuple[float, float, float]]]:
    timestamps: list[float] = []
    positions: list[tuple[float, float, float]] = []

    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        expected = {
            "timestamp_s",
            "north_m",
            "east_m",
            "down_m",
        }
        if set(reader.fieldnames or ()) != expected:
            raise ValueError(f"unexpected trajectory columns in {path}")

        for row in reader:
            timestamp = float(row["timestamp_s"])
            north = float(row["north_m"])
            east = float(row["east_m"])
            down = float(row["down_m"])

            if not all(
                math.isfinite(value)
                for value in (timestamp, north, east, down)
            ):
                raise ValueError(f"non-finite trajectory value in {path}")

            if timestamps and timestamp <= timestamps[-1]:
                raise ValueError(
                    f"non-increasing trajectory timestamp in {path}"
                )

            timestamps.append(timestamp)
            positions.append((north, east, down))

    if len(timestamps) < 100:
        raise ValueError(f"too few trajectory samples in {path}")

    return timestamps, positions


def position_errors(
    estimate: Sequence[tuple[float, float, float]],
    reference: Sequence[tuple[float, float, float]],
) -> list[float]:
    if len(estimate) != len(reference):
        raise ValueError("estimate and reference lengths differ")

    return [
        math.sqrt(
            (est[0] - ref[0]) ** 2
            + (est[1] - ref[1]) ** 2
            + (est[2] - ref[2]) ** 2
        )
        for est, ref in zip(estimate, reference)
    ]


def rmse(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("RMSE window must contain samples")
    return math.sqrt(
        math.fsum(value * value for value in values)
        / len(values)
    )


def select_values(
    timestamps: Sequence[float],
    values: Sequence[float],
    start: float,
    end: float,
) -> list[float]:
    selected = [
        value
        for timestamp, value in zip(timestamps, values)
        if start <= timestamp < end
    ]
    if not selected:
        raise ValueError(
            f"empty metric window [{start}, {end})"
        )
    return selected


def positive_excess_integral(
    timestamps: Sequence[float],
    degraded: Sequence[float],
    baseline: Sequence[float],
    start: float,
    end: float,
) -> float:
    points = [
        (
            timestamp,
            max(0.0, degraded_error - baseline_error),
        )
        for timestamp, degraded_error, baseline_error in zip(
            timestamps,
            degraded,
            baseline,
        )
        if start <= timestamp <= end
    ]

    if len(points) < 2:
        raise ValueError("excess integration window is too short")

    total = 0.0
    for left, right in zip(points, points[1:]):
        dt = right[0] - left[0]
        total += 0.5 * (left[1] + right[1]) * dt
    return total


def rolling_positive_excess_rmse(
    timestamps: Sequence[float],
    degraded: Sequence[float],
    baseline: Sequence[float],
    start: float,
    end: float,
) -> float:
    values = [
        max(0.0, degraded_error - baseline_error)
        for timestamp, degraded_error, baseline_error in zip(
            timestamps,
            degraded,
            baseline,
        )
        if start <= timestamp < end
    ]
    return rmse(values)


def recovery_time(
    timestamps: Sequence[float],
    degraded: Sequence[float],
    baseline: Sequence[float],
    outage_end: float,
    threshold: float,
    rolling_window_s: float,
    hold_s: float,
    horizon_s: float,
) -> float | None:
    candidates = [
        timestamp
        for timestamp in timestamps
        if outage_end <= timestamp <= outage_end + horizon_s
    ]

    for candidate in candidates:
        hold_end = candidate + hold_s
        if hold_end > outage_end + horizon_s:
            break

        probe_times = [
            timestamp
            for timestamp in timestamps
            if candidate <= timestamp <= hold_end
        ]
        if not probe_times:
            continue

        valid = True
        for probe in probe_times:
            try:
                rolling = rolling_positive_excess_rmse(
                    timestamps,
                    degraded,
                    baseline,
                    probe,
                    probe + rolling_window_s,
                )
            except ValueError:
                valid = False
                break

            if rolling > threshold:
                valid = False
                break

        if valid:
            return max(0.0, candidate - outage_end)

    return None


def float_text(value: float) -> str:
    return f"{value:.12g}"


def main() -> int:
    args = arguments()

    if args.upstream_commit != EXPECTED_COMMIT:
        raise ValueError("unexpected OpenVINS upstream commit")

    for name, path in {
        "experiment_config": args.experiment_config,
        "official_config": args.official_config,
        "official_manifest": args.official_manifest,
        "previous_manifest": args.previous_manifest,
        "runner_source": args.runner_source,
        "runner_cmake": args.runner_cmake,
        "runner_binary": args.runner_binary,
    }.items():
        require_file(path, name)

    config = load_json(args.experiment_config)
    official = load_json(args.official_manifest)
    previous = load_json(args.previous_manifest)

    if config["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("experiment configuration commit mismatch")
    if official["upstream"]["commit"] != EXPECTED_COMMIT:
        raise ValueError("official reproduction commit mismatch")
    if previous["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("previous runner manifest commit mismatch")
    if sha256(args.runner_source) != previous["runner"]["source_sha256"]:
        raise ValueError("runner source hash differs from prior evidence")
    if sha256(args.runner_cmake) != previous["runner"]["cmake_sha256"]:
        raise ValueError("runner CMake hash differs from prior evidence")
    if sha256(args.runner_binary) != previous["runner"]["binary_sha256"]:
        raise ValueError("runner binary hash differs from prior evidence")

    scenarios = config["scenarios"]
    scenario_names = tuple(item["name"] for item in scenarios)
    if scenario_names != EXPECTED_SCENARIOS:
        raise ValueError("scenario order mismatch")

    local = config["local_metrics"]
    pre_window_s = float(local["pre_window_s"])
    post_window_s = float(local["post_window_s"])
    recovery_hold_s = float(local["recovery_hold_s"])
    recovery_horizon_s = float(local["recovery_horizon_s"])
    rolling_window_s = float(local["rolling_window_s"])
    threshold_fraction = float(
        local["recovery_threshold_fraction_of_baseline_rmse"]
    )

    baseline_reference_bytes: bytes | None = None
    trajectories: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, dict[str, str]] = {}

    for configured in scenarios:
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

        for artifact in ("estimate", "reference", "summary"):
            left = files[f"{artifact}_a"].read_bytes()
            right = files[f"{artifact}_b"].read_bytes()
            if left != right:
                raise ValueError(
                    f"{name} {artifact} replay mismatch"
                )

        reference_bytes = files["reference_a"].read_bytes()
        if baseline_reference_bytes is None:
            baseline_reference_bytes = reference_bytes
        elif reference_bytes != baseline_reference_bytes:
            raise ValueError(
                f"{name} paired reference trajectory mismatch"
            )

        summary = load_json(files["summary_a"])
        if summary["scenario"] != name:
            raise ValueError(f"{name} summary scenario mismatch")
        if summary["mode"] != configured["mode"]:
            raise ValueError(f"{name} summary mode mismatch")

        estimate_times, estimate_positions = read_trajectory(
            files["estimate_a"]
        )
        reference_times, reference_positions = read_trajectory(
            files["reference_a"]
        )

        if estimate_times != reference_times:
            raise ValueError(
                f"{name} estimate and reference timestamps differ"
            )

        trajectories[name] = {
            "timestamps": estimate_times,
            "estimate_positions": estimate_positions,
            "reference_positions": reference_positions,
            "summary": summary,
            "config": configured,
        }

        artifacts[name] = {
            "estimate_sha256": sha256(files["estimate_a"]),
            "reference_sha256": sha256(files["reference_a"]),
            "run_log_sha256": sha256(files["log_a"]),
            "summary_sha256": sha256(files["summary_a"]),
        }

    baseline_data = trajectories["baseline"]
    timestamps = baseline_data["timestamps"]
    origin = timestamps[0]
    relative_times = [timestamp - origin for timestamp in timestamps]
    baseline_errors = position_errors(
        baseline_data["estimate_positions"],
        baseline_data["reference_positions"],
    )
    baseline_overall_rmse = rmse(baseline_errors)
    baseline_overall_max = max(baseline_errors)
    recovery_threshold = (
        baseline_overall_rmse * threshold_fraction
    )

    scenario_results: list[dict[str, Any]] = []

    for configured in scenarios:
        name = configured["name"]
        data = trajectories[name]

        if data["timestamps"] != timestamps:
            raise ValueError(
                f"{name} timestamps differ from baseline"
            )

        errors = position_errors(
            data["estimate_positions"],
            data["reference_positions"],
        )
        summary = data["summary"]
        start = float(configured["burst_start_s"])
        duration = float(configured["burst_duration_s"])

        if name == "baseline":
            scenario_results.append(
                {
                    "baseline_local_window_peak_m": (
                        baseline_overall_max
                    ),
                    "baseline_local_window_rmse_m": (
                        baseline_overall_rmse
                    ),
                    "burst_duration_s": 0.0,
                    "burst_start_s": 0.0,
                    "degraded_frames": 0,
                    "dropped_observations": 0,
                    "integrated_positive_excess_m_s": 0.0,
                    "local_window_peak_m": baseline_overall_max,
                    "local_window_peak_ratio": 1.0,
                    "local_window_rmse_m": baseline_overall_rmse,
                    "local_window_rmse_ratio": 1.0,
                    "mode": "baseline",
                    "outage_rmse_m": baseline_overall_rmse,
                    "overall_max_m": baseline_overall_max,
                    "overall_rmse_m": baseline_overall_rmse,
                    "peak_excess_error_m": 0.0,
                    "post_window_rmse_m": baseline_overall_rmse,
                    "pre_window_rmse_m": baseline_overall_rmse,
                    "recovered_within_horizon": True,
                    "recovery_time_s": 0.0,
                    "sample_count": len(errors),
                    "scenario": name,
                }
            )
            continue

        outage_end = start + duration
        pre_start = max(0.0, start - pre_window_s)
        local_end = outage_end + post_window_s
        integration_end = outage_end + recovery_horizon_s

        pre_errors = select_values(
            relative_times,
            errors,
            pre_start,
            start,
        )
        outage_errors = select_values(
            relative_times,
            errors,
            start,
            outage_end,
        )
        post_errors = select_values(
            relative_times,
            errors,
            outage_end,
            local_end,
        )
        local_errors = select_values(
            relative_times,
            errors,
            start,
            local_end,
        )
        baseline_local_errors = select_values(
            relative_times,
            baseline_errors,
            start,
            local_end,
        )

        local_rmse = rmse(local_errors)
        baseline_local_rmse = rmse(baseline_local_errors)
        local_peak = max(local_errors)
        baseline_local_peak = max(baseline_local_errors)

        local_pairs = [
            (degraded_error, baseline_error)
            for timestamp, degraded_error, baseline_error in zip(
                relative_times,
                errors,
                baseline_errors,
            )
            if start <= timestamp < local_end
        ]
        if not local_pairs:
            raise ValueError(f"{name} local excess window is empty")

        peak_excess = max(
            0.0,
            max(
                degraded_error - baseline_error
                for degraded_error, baseline_error in local_pairs
            ),
        )

        integrated_excess = positive_excess_integral(
            relative_times,
            errors,
            baseline_errors,
            start,
            integration_end,
        )

        recovered_at = recovery_time(
            relative_times,
            errors,
            baseline_errors,
            outage_end,
            recovery_threshold,
            rolling_window_s,
            recovery_hold_s,
            recovery_horizon_s,
        )

        scenario_results.append(
            {
                "baseline_local_window_peak_m": baseline_local_peak,
                "baseline_local_window_rmse_m": baseline_local_rmse,
                "burst_duration_s": duration,
                "burst_start_s": start,
                "degraded_frames": int(
                    summary["degraded_frames"]
                ),
                "dropped_observations": int(
                    summary["dropped_observations"]
                ),
                "integrated_positive_excess_m_s": (
                    integrated_excess
                ),
                "local_window_peak_m": local_peak,
                "local_window_peak_ratio": (
                    local_peak / baseline_local_peak
                ),
                "local_window_rmse_m": local_rmse,
                "local_window_rmse_ratio": (
                    local_rmse / baseline_local_rmse
                ),
                "mode": configured["mode"],
                "outage_rmse_m": rmse(outage_errors),
                "overall_max_m": max(errors),
                "overall_rmse_m": rmse(errors),
                "peak_excess_error_m": peak_excess,
                "post_window_rmse_m": rmse(post_errors),
                "pre_window_rmse_m": rmse(pre_errors),
                "recovered_within_horizon": (
                    recovered_at is not None
                ),
                "recovery_time_s": recovered_at,
                "sample_count": len(errors),
                "scenario": name,
            }
        )

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    results_payload = {
        "experiment": (
            "openvins-visual-burst-timing-sensitivity"
        ),
        "recovery_definition": {
            "hold_s": recovery_hold_s,
            "horizon_s": recovery_horizon_s,
            "rolling_window_s": rolling_window_s,
            "threshold_m": recovery_threshold,
            "threshold_policy": (
                "rolling positive excess-error RMSE not exceeding "
                "10% of full-run baseline RMSE"
            ),
        },
        "scenarios": scenario_results,
        "schema_version": 1,
    }

    manifest = {
        "experiment": (
            "openvins-visual-burst-timing-sensitivity"
        ),
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
        "scenario_artifacts": artifacts,
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
        "burst_start_s",
        "burst_duration_s",
        "sample_count",
        "degraded_frames",
        "dropped_observations",
        "overall_rmse_m",
        "overall_max_m",
        "pre_window_rmse_m",
        "outage_rmse_m",
        "post_window_rmse_m",
        "local_window_rmse_m",
        "baseline_local_window_rmse_m",
        "local_window_rmse_ratio",
        "local_window_peak_m",
        "baseline_local_window_peak_m",
        "local_window_peak_ratio",
        "peak_excess_error_m",
        "integrated_positive_excess_m_s",
        "recovery_time_s",
        "recovered_within_horizon",
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
                            float_text(result[key])
                            if isinstance(result[key], float)
                            else result[key]
                        )
                    )
                    for key in columns
                }
            )

    table_rows = []
    for result in scenario_results:
        recovery = (
            "baseline"
            if result["scenario"] == "baseline"
            else (
                f"{result['recovery_time_s']:.3f}"
                if result["recovery_time_s"] is not None
                else "not recovered"
            )
        )
        table_rows.append(
            "| {scenario} | {overall:.6f} | {local_ratio:.3f} | "
            "{peak_ratio:.3f} | {peak_excess:.6f} | {integral:.6f} | "
            "{recovery} |".format(
                scenario=result["scenario"],
                overall=result["overall_rmse_m"],
                local_ratio=result["local_window_rmse_ratio"],
                peak_ratio=result["local_window_peak_ratio"],
                peak_excess=result["peak_excess_error_m"],
                integral=result[
                    "integrated_positive_excess_m_s"
                ],
                recovery=recovery,
            )
        )

    duration_groups: dict[float, list[dict[str, Any]]] = {}
    for result in scenario_results[1:]:
        duration_groups.setdefault(
            float(result["burst_duration_s"]),
            [],
        ).append(result)

    sensitivity_lines = []
    for duration in sorted(duration_groups):
        group = duration_groups[duration]
        ratios = [
            float(item["local_window_rmse_ratio"])
            for item in group
        ]
        peaks = [
            float(item["local_window_peak_ratio"])
            for item in group
        ]
        sensitivity_lines.append(
            "- {duration:g} s outages: local RMSE ratio range "
            "{minimum:.3f}–{maximum:.3f}; local peak ratio range "
            "{peak_minimum:.3f}–{peak_maximum:.3f}.".format(
                duration=duration,
                minimum=min(ratios),
                maximum=max(ratios),
                peak_minimum=min(peaks),
                peak_maximum=max(peaks),
            )
        )

    report = f"""# OpenVINS visual-outage timing-sensitivity audit

## Purpose

The earlier fixed-window sweep found that a 3 s visual outage beginning
30 s after the first processed camera frame produced an overall RMSE
close to baseline. This audit tests whether that result is specific to
the outage location.

The same verified external OpenVINS runner is reused without
modification. One-second and three-second complete visual-observation
outages are injected at 30 s, 90 s, 150 s and 210 s. A no-degradation
baseline is included.

Every scenario is run twice. Estimate, reference and summary files must
be byte-identical across replays, and every scenario must use the same
byte-identical reference trajectory.

## Local metrics

For each outage, the audit reports:

- full-run RMSE and maximum error
- 10 s pre-outage RMSE
- outage RMSE
- 10 s post-outage RMSE
- RMSE and peak error over the outage plus 10 s post window
- matched baseline-window RMSE and peak ratios
- peak positive excess error over the matched local window
- positive excess-error integral through 30 s after outage end
- recovery time

Recovery is the first post-outage time at which the rolling 1 s RMSE of
positive error excess over baseline stays below
`{recovery_threshold:.9f} m` for 3 s. Recovery is searched for 30 s.

## Results

| Scenario | Overall RMSE (m) | Local RMSE ratio | Local peak ratio | Peak excess (m) | Positive excess integral (m·s) | Recovery time (s) |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(table_rows)}

## Timing sensitivity

{chr(10).join(sensitivity_lines)}

## Interpretation boundary

This audit isolates outage timing on one deterministic official
simulation trajectory. It can establish that sensitivity varies by
trajectory location, but it does not yet provide population-level
confidence intervals. Formal reliability boundaries require additional
trajectories, seeds and cross-estimator paired experiments.

Official OpenVINS source files remain unchanged. The GPL-linked runner,
raw trajectories and logs remain outside the Apache-2.0 repository.
"""

    (output / "report.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print(f"scenario_count={len(scenario_results)}")
    print(f"baseline_rmse_m={baseline_overall_rmse:.9f}")
    print(f"recovery_threshold_m={recovery_threshold:.9f}")

    for result in scenario_results:
        print(
            f"{result['scenario']}_overall_rmse_m="
            f"{result['overall_rmse_m']:.9f}"
        )
        print(
            f"{result['scenario']}_local_rmse_ratio="
            f"{result['local_window_rmse_ratio']:.9f}"
        )
        print(
            f"{result['scenario']}_recovery_time_s="
            f"{result['recovery_time_s']}"
        )

    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
