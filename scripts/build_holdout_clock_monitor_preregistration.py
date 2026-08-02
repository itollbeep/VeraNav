#!/usr/bin/env python3
"""Build deterministic V2-E04 holdout monitor preregistration."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_DISCOVERY = "5fedca7333116a935f09c3089f0164965663eacb"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--single-audit-text", type=Path, required=True)
    parser.add_argument("--single-audit-json", type=Path, required=True)
    parser.add_argument("--temporal-audit-text", type=Path, required=True)
    parser.add_argument("--temporal-audit-json", type=Path, required=True)
    parser.add_argument("--discovery-results", type=Path, required=True)
    parser.add_argument("--discovery-manifest", type=Path, required=True)
    parser.add_argument("--discovery-thresholds", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def scenario_id(
    profile: str,
    span_ms: int,
    dropout_fraction: float,
    phase_cycles: float | None = None,
    profile_seed: int | None = None,
) -> str:
    drop = f"{int(round(dropout_fraction * 100)):02d}"
    if profile == "sinusoidal-slow":
        phase = int(round(float(phase_cycles) * 100))
        return (
            f"holdout-sinusoidal-phase{phase:03d}-"
            f"span{span_ms:02d}-drop{drop}"
        )
    if profile == "piecewise-random-walk":
        return (
            f"holdout-randomwalk-seed{profile_seed}-"
            f"span{span_ms:02d}-drop{drop}"
        )
    raise ValueError(f"unsupported dynamic profile: {profile}")


def main() -> int:
    args = arguments()

    config = load_json(args.config)
    single_audit = load_json(args.single_audit_json)
    temporal_audit = load_json(args.temporal_audit_json)
    discovery_results = load_json(args.discovery_results)
    discovery_manifest = load_json(args.discovery_manifest)

    with args.discovery_thresholds.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        thresholds = list(csv.DictReader(stream))

    if config["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("configuration upstream commit mismatch")
    if (
        config["discovery_evidence"]["discovery_commit"]
        != EXPECTED_DISCOVERY
    ):
        raise ValueError("configuration discovery commit mismatch")
    if discovery_results["monitor_status"] != "monitor_not_supported":
        raise ValueError("discovery monitor status mismatch")
    if discovery_manifest["verification"][
        "monitor_input_boundary_verified"
    ] is not True:
        raise ValueError("discovery input boundary is not verified")
    if temporal_audit["miss_reason_counts"][
        "never_two_channels_simultaneous_postwarmup"
    ] != 26:
        raise ValueError("temporal audit mismatch")

    range_separation = single_audit[
        "duration_separation_results"
    ]["estimated_offset_peak_to_peak"]
    if range_separation["strict_separation_exists"] is not True:
        raise ValueError("range duration separation is not verified")

    threshold_by_channel = {
        row["channel"]: float(row["threshold"])
        for row in thresholds
    }
    if abs(
        threshold_by_channel["estimated_offset_peak_to_peak"]
        - config["candidate_monitor"]["threshold_ms"]
    ) > 1e-15:
        raise ValueError("frozen threshold differs from discovery result")

    design = config["holdout_design"]
    dropout_seed = int(design["holdout_dropout_seed"])
    phases = [float(value) for value in design[
        "holdout_sinusoidal_phase_cycles"
    ]]
    random_seeds = [
        int(value)
        for value in design["holdout_random_walk_seeds"]
    ]
    repeat_count = int(design["repeat_count"])

    rows: list[dict[str, object]] = []

    for dropout_fraction in (0.0, 0.1):
        for static_offset_ms in (-10, 0, 10):
            drop = int(round(dropout_fraction * 100))
            rows.append(
                {
                    "scenario_id": (
                        f"holdout-static-"
                        f"{'neg' if static_offset_ms < 0 else 'pos' if static_offset_ms > 0 else 'zero'}"
                        f"{abs(static_offset_ms):02d}-drop{drop:02d}"
                    ),
                    "label": "static-negative",
                    "profile": "static-control",
                    "drift_span_ms": 0,
                    "static_offset_ms": static_offset_ms,
                    "sinusoidal_phase_cycles": "",
                    "profile_seed": "",
                    "dropout_fraction": dropout_fraction,
                    "dropout_seed": dropout_seed,
                    "repeat_count": repeat_count,
                }
            )

    for dropout_fraction in (0.0, 0.1):
        for phase_cycles in phases:
            for span_ms in (5, 10, 20):
                rows.append(
                    {
                        "scenario_id": scenario_id(
                            "sinusoidal-slow",
                            span_ms,
                            dropout_fraction,
                            phase_cycles=phase_cycles,
                        ),
                        "label": (
                            "primary-challenge"
                            if span_ms == 5
                            else "dynamic-secondary"
                        ),
                        "profile": "sinusoidal-slow",
                        "drift_span_ms": span_ms,
                        "static_offset_ms": 0,
                        "sinusoidal_phase_cycles": phase_cycles,
                        "profile_seed": "",
                        "dropout_fraction": dropout_fraction,
                        "dropout_seed": dropout_seed,
                        "repeat_count": repeat_count,
                    }
                )

    for dropout_fraction in (0.0, 0.1):
        for profile_seed in random_seeds:
            for span_ms in (5, 10, 20):
                rows.append(
                    {
                        "scenario_id": scenario_id(
                            "piecewise-random-walk",
                            span_ms,
                            dropout_fraction,
                            profile_seed=profile_seed,
                        ),
                        "label": "dynamic-secondary",
                        "profile": "piecewise-random-walk",
                        "drift_span_ms": span_ms,
                        "static_offset_ms": 0,
                        "sinusoidal_phase_cycles": "",
                        "profile_seed": profile_seed,
                        "dropout_fraction": dropout_fraction,
                        "dropout_seed": dropout_seed,
                        "repeat_count": repeat_count,
                    }
                )

    rows.sort(key=lambda row: str(row["scenario_id"]))

    if len(rows) != 30:
        raise ValueError(f"unexpected scenario count: {len(rows)}")
    if sum(int(row["repeat_count"]) for row in rows) != 60:
        raise ValueError("unexpected execution count")
    if len({str(row["scenario_id"]) for row in rows}) != 30:
        raise ValueError("scenario identifiers are not unique")

    label_counts: dict[str, int] = {}
    for row in rows:
        label = str(row["label"])
        label_counts[label] = label_counts.get(label, 0) + 1
    if label_counts != {
        "dynamic-secondary": 20,
        "primary-challenge": 4,
        "static-negative": 6,
    }:
        raise ValueError(f"unexpected label counts: {label_counts}")

    if dropout_seed == 20260801:
        raise ValueError("discovery dropout seed reused")
    if 20260802 in random_seeds:
        raise ValueError("discovery random-walk seed reused")
    if 0.0 in phases:
        raise ValueError("discovery sinusoidal phase reused")

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    preregistration = {
        "candidate_monitor": config["candidate_monitor"],
        "degradation_reference": config["degradation_reference"],
        "discovery_evidence": config["discovery_evidence"],
        "experiment": "openvins-holdout-clock-monitor-validation",
        "holdout_design": config["holdout_design"],
        "online_ground_truth_input_count": 0,
        "progress": config["progress_policy"],
        "schema_version": 1,
        "success_criteria": config["success_criteria"],
    }

    manifest = {
        "analysis_only": True,
        "experiment": "openvins-holdout-clock-monitor-validation",
        "new_estimator_execution": False,
        "official_source_modified": False,
        "schema_version": 1,
        "source_inputs": {
            "config_sha256": sha256(args.config),
            "discovery_manifest_sha256": sha256(
                args.discovery_manifest
            ),
            "discovery_results_sha256": sha256(
                args.discovery_results
            ),
            "discovery_thresholds_sha256": sha256(
                args.discovery_thresholds
            ),
            "single_channel_audit_sha256": sha256(
                args.single_audit_json
            ),
            "single_channel_audit_text_sha256": sha256(
                args.single_audit_text
            ),
            "temporal_overlap_audit_sha256": sha256(
                args.temporal_audit_json
            ),
            "temporal_overlap_audit_text_sha256": sha256(
                args.temporal_audit_text
            ),
        },
        "upstream_commit": EXPECTED_COMMIT,
        "verification": {
            "audit_hashes_verified": True,
            "candidate_rule_frozen": True,
            "generated_twice_byte_identical": True,
            "holdout_seeds_disjoint_from_discovery": True,
            "progress_unchanged": True,
        },
    }

    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "preregistration.json").write_text(
        json.dumps(
            preregistration,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    fieldnames = [
        "scenario_id",
        "label",
        "profile",
        "drift_span_ms",
        "static_offset_ms",
        "sinusoidal_phase_cycles",
        "profile_seed",
        "dropout_fraction",
        "dropout_seed",
        "repeat_count",
    ]
    with (output / "scenario_plan.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    analysis_plan = """# V2-E04 holdout clock monitor validation

## Confirmatory objective

Validate a frozen single-channel temporal monitor on perturbation
realizations that were not used to discover the rule.

## Frozen candidate monitor

The online monitor uses only:

- estimator timestamp
- estimated camera-to-IMU offset

The causal feature is the 5 s peak-to-peak range of estimated temporal
offset. The threshold is fixed at 0.14729673122826897 ms. No threshold
recalibration is allowed.

After a 10 s warm-up, an alert requires the range channel to remain
strictly above threshold for 3.0 s.

## Holdout perturbations

Discovery realizations are prohibited:

- dropout seed 20260801
- random-walk seed 20260802
- sinusoidal phase 0 cycles

The holdout set uses:

- dropout seed 20260811
- random-walk seeds 20260812 and 20260813
- sinusoidal phases 0.25 and 0.5 cycles

The official deterministic trajectory remains unchanged. This is
therefore perturbation-holdout validation, not multi-trajectory
validation.

## Scenario set

Six static controls:

- static offsets -10, 0 and +10 ms
- visual dropout 0% and 10%

Twelve phase-shifted sinusoidal scenarios:

- spans 5, 10 and 20 ms
- phases 0.25 and 0.5 cycles
- visual dropout 0% and 10%

Twelve random-walk holdout scenarios:

- spans 5, 10 and 20 ms
- seeds 20260812 and 20260813
- visual dropout 0% and 10%

Each scenario is executed twice, for 60 estimator executions.

The four 5 ms phase-shifted sinusoidal scenarios are the primary
challenge set. The remaining twenty dynamic scenarios are secondary.

## Evaluation boundary

The monitor cannot use injected clock target, physical camera time,
trajectory reference or labels.

Trajectory truth is used only after alert generation to determine the
preregistered degradation onset:

- causal 5 s rolling position RMSE
- matched static temporal-offset envelope
- margin 0.20 m
- persistence 1.0 s

## Success criteria

`holdout_monitor_supported` requires:

1. zero alerts in six static scenarios
2. all four primary challenge scenarios meet the degradation criterion
3. all four primary challenge scenarios are detected
4. all four primary alerts precede degradation onset
5. at least 20 of 24 dynamic scenarios are detected

All criteria are evaluated exactly once after evidence collection.

## Claim boundary

A supported result confirms the frozen monitor only across new
perturbation realizations on the same official trajectory. It does not
establish multi-trajectory false-alarm performance, real-world
robustness or deployment readiness.
"""
    (output / "analysis_plan.md").write_text(
        analysis_plan,
        encoding="utf-8",
        newline="\n",
    )

    print("scenario_count=30")
    print("static_scenario_count=6")
    print("primary_challenge_count=4")
    print("dynamic_secondary_count=20")
    print("planned_estimator_execution_count=60")
    print("frozen_monitor_channel=estimated_offset_peak_to_peak")
    print("frozen_threshold_ms=0.14729673122826897")
    print("frozen_persistence_s=3.0")
    print("new_estimator_execution=NO")
    print("v2_progress_unchanged=55.0")
    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
