#!/usr/bin/env python3
"""Diagnose fixed-time OpenVINS divergence from committed trajectories."""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Sequence


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
    parser.add_argument("--fixed-evidence", type=Path, required=True)
    parser.add_argument("--online-evidence", type=Path, required=True)
    parser.add_argument("--analysis-config", type=Path, required=True)
    parser.add_argument("--official-manifest", type=Path, required=True)
    parser.add_argument("--fixed-manifest", type=Path, required=True)
    parser.add_argument("--fixed-results", type=Path, required=True)
    parser.add_argument("--online-manifest", type=Path, required=True)
    parser.add_argument("--online-results", type=Path, required=True)
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
            raise ValueError(f"unexpected trajectory columns: {path}")

        for row in reader:
            values = (
                float(row["timestamp_s"]),
                float(row["north_m"]),
                float(row["east_m"]),
                float(row["down_m"]),
            )
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"non-finite trajectory value: {path}")

            timestamp, north, east, down = values
            if timestamps and timestamp <= timestamps[-1]:
                raise ValueError(
                    f"non-increasing trajectory timestamp: {path}"
                )

            timestamps.append(timestamp)
            positions.append((north, east, down))

    if len(timestamps) < 100:
        raise ValueError(f"too few trajectory samples: {path}")

    return timestamps, positions


def position_errors(
    estimate: Sequence[tuple[float, float, float]],
    reference: Sequence[tuple[float, float, float]],
) -> list[float]:
    if len(estimate) != len(reference):
        raise ValueError("estimate and reference lengths differ")

    values = [
        math.sqrt(
            (est[0] - ref[0]) ** 2
            + (est[1] - ref[1]) ** 2
            + (est[2] - ref[2]) ** 2
        )
        for est, ref in zip(estimate, reference)
    ]

    if not all(math.isfinite(value) for value in values):
        raise ValueError("non-finite position error")

    return values


def rmse(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("RMSE requires samples")
    return math.sqrt(
        math.fsum(value * value for value in values)
        / len(values)
    )


def nearest_rank(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires samples")
    ordered = sorted(values)
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[min(len(ordered) - 1, rank - 1)]


def first_crossing(
    timestamps: Sequence[float],
    errors: Sequence[float],
    threshold: float,
) -> float | None:
    for timestamp, error in zip(timestamps, errors):
        if error > threshold:
            return timestamp
    return None


def rolling_rmse(
    timestamps: Sequence[float],
    errors: Sequence[float],
    window_s: float,
) -> list[float]:
    squares = [value * value for value in errors]
    prefix = [0.0]
    for value in squares:
        prefix.append(prefix[-1] + value)

    values = []
    for index, timestamp in enumerate(timestamps):
        end = timestamp + window_s
        stop = bisect.bisect_left(timestamps, end, lo=index + 1)
        if stop <= index:
            stop = index + 1

        count = stop - index
        sum_squares = prefix[stop] - prefix[index]
        values.append(math.sqrt(sum_squares / count))

    return values


def first_sustained_condition(
    timestamps: Sequence[float],
    values: Sequence[float],
    threshold: float,
    hold_s: float,
    above: bool,
    start_index: int = 0,
) -> float | None:
    for index in range(start_index, len(timestamps)):
        start = timestamps[index]
        end = start + hold_s

        if end > timestamps[-1]:
            return None

        stop = bisect.bisect_right(timestamps, end, lo=index)
        selected = values[index:stop]
        if not selected:
            continue

        if above:
            valid = all(value > threshold for value in selected)
        else:
            valid = all(value <= threshold for value in selected)

        if valid:
            return start

    return None


def top_squared_error_share(
    errors: Sequence[float],
    fraction: float,
) -> float:
    squares = sorted(
        (value * value for value in errors),
        reverse=True,
    )
    total = math.fsum(squares)
    if total <= 0.0:
        return 0.0

    count = max(1, math.ceil(len(squares) * fraction))
    return math.fsum(squares[:count]) / total


def trace_diagnostics(
    timestamps: Sequence[float],
    errors: Sequence[float],
    config: dict[str, Any],
) -> dict[str, Any]:
    sustained = config["sustained_failure"]
    recovery = config["recovery"]
    classification = config["catastrophic_classification"]

    rolling = rolling_rmse(
        timestamps,
        errors,
        float(sustained["rolling_window_s"]),
    )

    failure_threshold = float(sustained["threshold_m"])
    onset = first_sustained_condition(
        timestamps,
        rolling,
        failure_threshold,
        float(sustained["hold_s"]),
        above=True,
    )

    recovered_at: float | None = None
    if onset is not None:
        start_index = bisect.bisect_left(timestamps, onset)
        recovered_at = first_sustained_condition(
            timestamps,
            rolling,
            float(recovery["threshold_m"]),
            float(recovery["hold_s"]),
            above=False,
            start_index=start_index,
        )

    if onset is None:
        post_onset_fraction = 0.0
    else:
        onset_index = bisect.bisect_left(timestamps, onset)
        post_errors = errors[onset_index:]
        post_onset_fraction = (
            sum(error > failure_threshold for error in post_errors)
            / len(post_errors)
        )

    crossings = {
        f"{float(threshold):g}": first_crossing(
            timestamps,
            errors,
            float(threshold),
        )
        for threshold in config["first_crossing_thresholds_m"]
    }

    availability = {
        f"{float(threshold):g}": (
            sum(error <= float(threshold) for error in errors)
            / len(errors)
        )
        for threshold in config["availability_thresholds_m"]
    }

    max_index = max(
        range(len(errors)),
        key=lambda index: errors[index],
    )

    p90 = nearest_rank(errors, 0.90)
    broad_failure = (
        onset is not None
        and p90 > failure_threshold
        and post_onset_fraction
        >= float(
            classification["broad_failure_post_onset_fraction"]
        )
    )
    required_crossing = crossings[
        f"{float(classification['required_first_crossing_m']):g}"
    ]
    catastrophic = (
        broad_failure
        and required_crossing is not None
    )

    return {
        "availability_fraction": availability,
        "broad_trajectory_failure": broad_failure,
        "catastrophic_divergence": catastrophic,
        "final_error_m": errors[-1],
        "first_crossing_s": crossings,
        "max_m": errors[max_index],
        "max_time_s": timestamps[max_index],
        "mean_m": math.fsum(errors) / len(errors),
        "median_m": nearest_rank(errors, 0.50),
        "p90_m": p90,
        "p95_m": nearest_rank(errors, 0.95),
        "p99_m": nearest_rank(errors, 0.99),
        "post_onset_fraction_above_1m": post_onset_fraction,
        "recovered_after_failure": recovered_at is not None,
        "recovery_time_s": (
            None
            if recovered_at is None or onset is None
            else recovered_at - onset
        ),
        "rmse_m": rmse(errors),
        "sustained_failure_onset_s": onset,
        "top_1_percent_squared_error_share": (
            top_squared_error_share(errors, 0.01)
        ),
        "top_5_percent_squared_error_share": (
            top_squared_error_share(errors, 0.05)
        ),
    }


def assert_close(
    actual: float,
    expected: float,
    name: str,
    tolerance: float = 1e-6,
) -> None:
    if not math.isclose(
        actual,
        expected,
        rel_tol=0.0,
        abs_tol=tolerance,
    ):
        raise ValueError(
            f"{name} mismatch: actual={actual}, expected={expected}"
        )


def main() -> int:
    args = arguments()

    if args.upstream_commit != EXPECTED_COMMIT:
        raise ValueError("unexpected OpenVINS upstream commit")

    for name, path in {
        "analysis_config": args.analysis_config,
        "official_manifest": args.official_manifest,
        "fixed_manifest": args.fixed_manifest,
        "fixed_results": args.fixed_results,
        "online_manifest": args.online_manifest,
        "online_results": args.online_results,
    }.items():
        require_file(path, name)

    config = load_json(args.analysis_config)
    official = load_json(args.official_manifest)
    fixed_manifest = load_json(args.fixed_manifest)
    fixed_results = load_json(args.fixed_results)
    online_manifest = load_json(args.online_manifest)
    online_results = load_json(args.online_results)

    if config["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("analysis configuration commit mismatch")
    if official["upstream"]["commit"] != EXPECTED_COMMIT:
        raise ValueError("official reproduction commit mismatch")
    if fixed_manifest["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("fixed experiment commit mismatch")
    if online_manifest["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("online experiment commit mismatch")

    fixed_by_name = {
        item["scenario"]: item
        for item in fixed_results["scenarios"]
    }
    online_by_name = {
        item["scenario"]: item
        for item in online_results["scenarios"]
    }

    if tuple(fixed_by_name) != EXPECTED_SCENARIOS:
        raise ValueError("fixed scenario order mismatch")
    if tuple(online_by_name) != EXPECTED_SCENARIOS:
        raise ValueError("online scenario order mismatch")

    if (
        fixed_manifest["measurement_realization"]
        != online_manifest["measurement_realization"]
    ):
        raise ValueError("fixed/online measurement fingerprints differ")

    scenario_results: list[dict[str, Any]] = []
    input_artifacts: dict[str, dict[str, str]] = {}

    for name in EXPECTED_SCENARIOS:
        fixed_run = args.fixed_evidence / name / "run-a"
        online_run = args.online_evidence / name / "run-a"

        paths = {
            "fixed_estimate": fixed_run / "estimate.csv",
            "fixed_reference": fixed_run / "reference_nominal.csv",
            "fixed_physical": fixed_run / "reference_physical.csv",
            "online_estimate": online_run / "estimate.csv",
            "online_reference": (
                online_run / "reference_calibrated.csv"
            ),
            "online_physical": (
                online_run / "reference_physical.csv"
            ),
        }

        for path_name, path in paths.items():
            require_file(path, f"{name}.{path_name}")

        if paths["fixed_physical"].read_bytes() != paths[
            "online_physical"
        ].read_bytes():
            raise ValueError(
                f"{name} fixed/online physical reference mismatch"
            )

        fixed_times, fixed_estimate = read_trajectory(
            paths["fixed_estimate"]
        )
        fixed_reference_times, fixed_reference = read_trajectory(
            paths["fixed_reference"]
        )
        online_times, online_estimate = read_trajectory(
            paths["online_estimate"]
        )
        online_reference_times, online_reference = read_trajectory(
            paths["online_reference"]
        )

        if fixed_times != fixed_reference_times:
            raise ValueError(
                f"{name} fixed estimate/reference timestamps differ"
            )
        if online_times != online_reference_times:
            raise ValueError(
                f"{name} online estimate/reference timestamps differ"
            )
        if fixed_times != online_times:
            raise ValueError(
                f"{name} fixed/online timelines differ"
            )

        fixed_errors = position_errors(
            fixed_estimate,
            fixed_reference,
        )
        online_errors = position_errors(
            online_estimate,
            online_reference,
        )

        fixed_trace = trace_diagnostics(
            fixed_times,
            fixed_errors,
            config,
        )
        online_trace = trace_diagnostics(
            online_times,
            online_errors,
            config,
        )

        fixed_record = fixed_by_name[name]
        online_record = online_by_name[name]

        assert_close(
            fixed_trace["rmse_m"],
            float(fixed_record["fixed_nominal_rmse_m"]),
            f"{name}.fixed_rmse",
        )
        assert_close(
            online_trace["rmse_m"],
            float(
                online_record["calibration_aware_rmse_m"]
            ),
            f"{name}.online_rmse",
        )

        scenario_results.append(
            {
                "duration_s": fixed_times[-1] - fixed_times[0],
                "fixed": fixed_trace,
                "injected_offset_ms": float(
                    fixed_record["injected_offset_ms"]
                ),
                "online": online_trace,
                "sample_count": len(fixed_times),
                "scenario": name,
            }
        )

        input_artifacts[name] = {
            key: sha256(path)
            for key, path in paths.items()
        }

    nonbaseline = scenario_results[1:]
    fixed_catastrophic_count = sum(
        bool(item["fixed"]["catastrophic_divergence"])
        for item in nonbaseline
    )
    fixed_broad_failure_count = sum(
        bool(item["fixed"]["broad_trajectory_failure"])
        for item in nonbaseline
    )
    online_catastrophic_count = sum(
        bool(item["online"]["catastrophic_divergence"])
        for item in nonbaseline
    )

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    results_payload = {
        "experiment": (
            "openvins-fixed-time-divergence-diagnostics"
        ),
        "scenario_summary": {
            "fixed_broad_failure_count": (
                fixed_broad_failure_count
            ),
            "fixed_catastrophic_divergence_count": (
                fixed_catastrophic_count
            ),
            "nonbaseline_scenario_count": len(nonbaseline),
            "online_catastrophic_divergence_count": (
                online_catastrophic_count
            ),
        },
        "scenarios": scenario_results,
        "schema_version": 1,
    }

    manifest = {
        "analysis_config_sha256": sha256(
            args.analysis_config
        ),
        "analysis_only": True,
        "experiment": (
            "openvins-fixed-time-divergence-diagnostics"
        ),
        "input_artifacts": input_artifacts,
        "inputs": {
            "fixed_manifest_sha256": sha256(
                args.fixed_manifest
            ),
            "fixed_results_sha256": sha256(
                args.fixed_results
            ),
            "online_manifest_sha256": sha256(
                args.online_manifest
            ),
            "online_results_sha256": sha256(
                args.online_results
            ),
        },
        "measurement_realization": (
            fixed_manifest["measurement_realization"]
        ),
        "official_reproduction_manifest_sha256": sha256(
            args.official_manifest
        ),
        "official_source_modified": False,
        "schema_version": 1,
        "upstream_commit": EXPECTED_COMMIT,
        "verification": {
            "fixed_online_physical_references_byte_identical": True,
            "input_artifact_hashes_verified": True,
            "no_new_estimator_execution": True,
            "paired_measurement_realization": True,
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
        "duration_s",
        "fixed_rmse_m",
        "fixed_median_m",
        "fixed_p90_m",
        "fixed_p95_m",
        "fixed_p99_m",
        "fixed_max_m",
        "fixed_max_time_s",
        "fixed_final_error_m",
        "fixed_first_1m_s",
        "fixed_first_10m_s",
        "fixed_first_100m_s",
        "fixed_first_1000m_s",
        "fixed_sustained_failure_onset_s",
        "fixed_recovery_time_s",
        "fixed_recovered_after_failure",
        "fixed_availability_below_1m",
        "fixed_post_onset_fraction_above_1m",
        "fixed_top_1pct_squared_error_share",
        "fixed_top_5pct_squared_error_share",
        "fixed_broad_trajectory_failure",
        "fixed_catastrophic_divergence",
        "online_rmse_m",
        "online_max_m",
        "online_availability_below_1m",
        "online_catastrophic_divergence",
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
            fixed = result["fixed"]
            online = result["online"]

            writer.writerow(
                {
                    "scenario": result["scenario"],
                    "injected_offset_ms": (
                        f"{result['injected_offset_ms']:.12g}"
                    ),
                    "sample_count": result["sample_count"],
                    "duration_s": (
                        f"{result['duration_s']:.12g}"
                    ),
                    "fixed_rmse_m": f"{fixed['rmse_m']:.12g}",
                    "fixed_median_m": (
                        f"{fixed['median_m']:.12g}"
                    ),
                    "fixed_p90_m": f"{fixed['p90_m']:.12g}",
                    "fixed_p95_m": f"{fixed['p95_m']:.12g}",
                    "fixed_p99_m": f"{fixed['p99_m']:.12g}",
                    "fixed_max_m": f"{fixed['max_m']:.12g}",
                    "fixed_max_time_s": (
                        f"{fixed['max_time_s']:.12g}"
                    ),
                    "fixed_final_error_m": (
                        f"{fixed['final_error_m']:.12g}"
                    ),
                    "fixed_first_1m_s": (
                        ""
                        if fixed["first_crossing_s"]["1"] is None
                        else f"{fixed['first_crossing_s']['1']:.12g}"
                    ),
                    "fixed_first_10m_s": (
                        ""
                        if fixed["first_crossing_s"]["10"] is None
                        else f"{fixed['first_crossing_s']['10']:.12g}"
                    ),
                    "fixed_first_100m_s": (
                        ""
                        if fixed["first_crossing_s"]["100"] is None
                        else f"{fixed['first_crossing_s']['100']:.12g}"
                    ),
                    "fixed_first_1000m_s": (
                        ""
                        if fixed["first_crossing_s"]["1000"] is None
                        else f"{fixed['first_crossing_s']['1000']:.12g}"
                    ),
                    "fixed_sustained_failure_onset_s": (
                        ""
                        if fixed[
                            "sustained_failure_onset_s"
                        ] is None
                        else f"{fixed['sustained_failure_onset_s']:.12g}"
                    ),
                    "fixed_recovery_time_s": (
                        ""
                        if fixed["recovery_time_s"] is None
                        else f"{fixed['recovery_time_s']:.12g}"
                    ),
                    "fixed_recovered_after_failure": (
                        fixed["recovered_after_failure"]
                    ),
                    "fixed_availability_below_1m": (
                        f"{fixed['availability_fraction']['1']:.12g}"
                    ),
                    "fixed_post_onset_fraction_above_1m": (
                        f"{fixed['post_onset_fraction_above_1m']:.12g}"
                    ),
                    "fixed_top_1pct_squared_error_share": (
                        f"{fixed['top_1_percent_squared_error_share']:.12g}"
                    ),
                    "fixed_top_5pct_squared_error_share": (
                        f"{fixed['top_5_percent_squared_error_share']:.12g}"
                    ),
                    "fixed_broad_trajectory_failure": (
                        fixed["broad_trajectory_failure"]
                    ),
                    "fixed_catastrophic_divergence": (
                        fixed["catastrophic_divergence"]
                    ),
                    "online_rmse_m": (
                        f"{online['rmse_m']:.12g}"
                    ),
                    "online_max_m": (
                        f"{online['max_m']:.12g}"
                    ),
                    "online_availability_below_1m": (
                        f"{online['availability_fraction']['1']:.12g}"
                    ),
                    "online_catastrophic_divergence": (
                        online["catastrophic_divergence"]
                    ),
                }
            )

    table_rows = []
    for result in scenario_results:
        fixed = result["fixed"]
        onset = (
            "none"
            if fixed["sustained_failure_onset_s"] is None
            else f"{fixed['sustained_failure_onset_s']:.2f}"
        )
        recovery_text = (
            "not applicable"
            if fixed["sustained_failure_onset_s"] is None
            else (
                f"{fixed['recovery_time_s']:.2f}"
                if fixed["recovery_time_s"] is not None
                else "not recovered"
            )
        )
        first_100 = fixed["first_crossing_s"]["100"]
        first_100_text = (
            "none"
            if first_100 is None
            else f"{first_100:.2f}"
        )

        table_rows.append(
            "| {scenario} | {offset:.1f} | {rmse:.3f} | "
            "{p90:.3f} | {maximum:.3f} | {onset} | "
            "{first_100} | {availability:.4f} | {post:.4f} | "
            "{top1:.4f} | {recovery} | {classification} |".format(
                scenario=result["scenario"],
                offset=result["injected_offset_ms"],
                rmse=fixed["rmse_m"],
                p90=fixed["p90_m"],
                maximum=fixed["max_m"],
                onset=onset,
                first_100=first_100_text,
                availability=fixed["availability_fraction"]["1"],
                post=fixed["post_onset_fraction_above_1m"],
                top1=fixed[
                    "top_1_percent_squared_error_share"
                ],
                recovery=recovery_text,
                classification=(
                    "catastrophic"
                    if fixed["catastrophic_divergence"]
                    else (
                        "broad failure"
                        if fixed["broad_trajectory_failure"]
                        else "not catastrophic"
                    )
                ),
            )
        )

    report = f"""# OpenVINS fixed-time divergence diagnostics

## Purpose

The fixed temporal-calibration experiment produced very large full-run
RMSE values under every nonzero camera timestamp offset. This analysis
determines whether those values represent persistent filter divergence
or are dominated by isolated outliers.

No estimator is rerun. The analysis uses the previously committed fixed
and online trajectory evidence after verifying every input artifact
against its committed SHA256 record.

## Failure definitions

Service failure threshold: `1 m`.

Sustained failure begins when the rolling 1 s position RMSE remains
above 1 m for 3 continuous seconds.

Recovery occurs only when the rolling 1 s RMSE remains at or below 1 m
for 5 continuous seconds after sustained failure begins.

A trace is classified as broad trajectory failure when:

- sustained failure occurs
- p90 position error exceeds 1 m
- at least 50% of samples after onset exceed 1 m

Catastrophic divergence additionally requires the trace to cross
100 m position error.

## Fixed-calibration results

| Scenario | Offset (ms) | RMSE (m) | p90 (m) | Maximum (m) | Sustained onset (s) | First 100 m crossing (s) | Availability ≤1 m | Post-onset fraction >1 m | Top 1% squared-error share | Recovery after onset (s) | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
{chr(10).join(table_rows)}

## Summary

- Fixed nonbaseline scenarios classified as broad failure:
  `{fixed_broad_failure_count}` of `{len(nonbaseline)}`.
- Fixed nonbaseline scenarios classified as catastrophic divergence:
  `{fixed_catastrophic_count}` of `{len(nonbaseline)}`.
- Paired online-calibration scenarios classified as catastrophic:
  `{online_catastrophic_count}` of `{len(nonbaseline)}`.

Top 1% and top 5% squared-error shares are retained to quantify outlier
concentration. They must be interpreted together with p90, service
availability and the post-onset fraction. A large top-share alone does
not imply a single-point artifact when most post-onset samples remain
above the service threshold.

## Interpretation boundary

This diagnostic confirms trace-level behavior for one deterministic
OpenVINS simulation trajectory. The classification thresholds are
engineering definitions for this project, not universal OpenVINS safety
limits. Population-level reliability still requires additional
trajectories and sensor realizations.

Official OpenVINS source files are unchanged, and this analysis starts
no new estimator process.
"""

    (output / "report.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print(f"scenario_count={len(scenario_results)}")
    print(
        "fixed_broad_failure_count="
        f"{fixed_broad_failure_count}"
    )
    print(
        "fixed_catastrophic_divergence_count="
        f"{fixed_catastrophic_count}"
    )
    print(
        "online_catastrophic_divergence_count="
        f"{online_catastrophic_count}"
    )

    for result in scenario_results:
        fixed = result["fixed"]
        print(
            f"{result['scenario']}_fixed_rmse_m="
            f"{fixed['rmse_m']:.9f}"
        )
        print(
            f"{result['scenario']}_fixed_p90_m="
            f"{fixed['p90_m']:.9f}"
        )
        print(
            f"{result['scenario']}_fixed_max_m="
            f"{fixed['max_m']:.9f}"
        )
        print(
            f"{result['scenario']}_fixed_onset_s="
            f"{fixed['sustained_failure_onset_s']}"
        )
        print(
            f"{result['scenario']}_fixed_availability_1m="
            f"{fixed['availability_fraction']['1']:.9f}"
        )
        print(
            f"{result['scenario']}_fixed_catastrophic="
            f"{fixed['catastrophic_divergence']}"
        )

    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
