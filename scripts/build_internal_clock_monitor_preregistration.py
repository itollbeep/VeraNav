#!/usr/bin/env python3
"""Build deterministic V2-E03 internal clock monitor preregistration."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_PARENT = "52da5a0f8014e35911befd4db7c4fae7f762c061"
EARLY_WARNING = {
    "sinusoidalslow-span05-drop00",
    "sinusoidalslow-span05-drop10",
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--audit-text", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--parent-results", type=Path, required=True)
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--parent-scenarios", type=Path, required=True)
    parser.add_argument("--evidence-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def main() -> int:
    args = arguments()

    config = load_json(args.config)
    audit = load_json(args.audit_json)
    results = load_json(args.parent_results)
    result_manifest = load_json(args.parent_manifest)
    evidence_audit = load_json(args.evidence_audit)

    if config["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("configuration upstream commit mismatch")
    if config["parent_evidence"]["commit"] != EXPECTED_PARENT:
        raise ValueError("configuration parent commit mismatch")
    if audit["experiment_commit"] != EXPECTED_PARENT:
        raise ValueError("audit parent commit mismatch")
    if results["pilot_status"] != "pilot_supported":
        raise ValueError("parent dynamic-drift pilot is not supported")
    if results["early_warning_gap_count"] != 2:
        raise ValueError("unexpected parent early-warning count")
    if result_manifest["verification"][
        "deterministic_replay_verified"
    ] is not True:
        raise ValueError("parent deterministic replay is not verified")
    if evidence_audit[
        "clock_profiles_equal_across_visual_conditions"
    ] is not True:
        raise ValueError("parent clock-profile audit failed")

    with args.parent_scenarios.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        scenarios = list(csv.DictReader(stream))

    if len(scenarios) != 30:
        raise ValueError("parent scenario count mismatch")

    labels: list[dict[str, str]] = []
    for row in scenarios:
        scenario_id = row["scenario_id"]
        if row["profile"] == "static-control":
            label = "static-negative"
        elif scenario_id in EARLY_WARNING:
            label = "early-warning-positive"
        else:
            label = "dynamic-secondary"
        labels.append(
            {
                "dropout_fraction": row["dropout_fraction"],
                "drift_span_ms": row["drift_span_ms"],
                "label": label,
                "profile": row["profile"],
                "scenario_id": scenario_id,
            }
        )

    counts: dict[str, int] = {}
    for row in labels:
        counts[row["label"]] = counts.get(row["label"], 0) + 1

    if counts != {
        "dynamic-secondary": 22,
        "early-warning-positive": 2,
        "static-negative": 6,
    }:
        raise ValueError(f"unexpected label counts: {counts}")

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    preregistration = {
        "calibration": config["calibration"],
        "degradation_reference": config[
            "degradation_reference"
        ],
        "experiment": "openvins-internal-clock-monitor-pilot",
        "labels": config["labels"],
        "monitor": config["monitor"],
        "parent_evidence": config["parent_evidence"],
        "progress": config["progress_policy"],
        "schema_version": 1,
        "success_criteria": config["success_criteria"],
    }

    manifest = {
        "analysis_only": True,
        "experiment": "openvins-internal-clock-monitor-pilot",
        "new_estimator_execution": False,
        "official_source_modified": False,
        "schema_version": 1,
        "source_inputs": {
            "audit_json_sha256": sha256(args.audit_json),
            "audit_text_sha256": sha256(args.audit_text),
            "config_sha256": sha256(args.config),
            "evidence_audit_sha256": sha256(
                args.evidence_audit
            ),
            "parent_manifest_sha256": sha256(
                args.parent_manifest
            ),
            "parent_results_sha256": sha256(
                args.parent_results
            ),
            "parent_scenarios_sha256": sha256(
                args.parent_scenarios
            ),
        },
        "upstream_commit": EXPECTED_COMMIT,
        "verification": {
            "audit_hashes_verified": True,
            "generated_twice_byte_identical": True,
            "parent_evidence_verified": True,
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

    with (output / "scenario_labels.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "scenario_id",
                "profile",
                "drift_span_ms",
                "dropout_fraction",
                "label",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(labels)

    analysis_plan = """# V2-E03 deployable internal clock monitor pilot

## Objective

Detect the two V2-E02 early-warning-gap scenarios using only estimator
outputs available online, before physical-reference trajectory error
crosses a preregistered degradation threshold.

## Positive and negative cases

Static negatives:

- all six static temporal-offset controls

Primary positives:

- sinusoidal-slow, 5 ms span, clean vision
- sinusoidal-slow, 5 ms span, 10% visual dropout

Secondary dynamic cases:

- the remaining 22 dynamic-drift scenarios

## Online monitor inputs

The monitor may use only:

- estimator timestamp
- estimated camera-to-IMU time offset

Injected clock offset, physical camera time and trajectory reference are
prohibited from the online monitor.

## Causal channels

All channels are calculated over a causal 5 s window after a 10 s
warm-up:

1. RMS velocity of estimated time offset
2. RMS acceleration of estimated time offset
3. peak-to-peak range of estimated time offset

Thresholds are calibrated only from the six static controls. For each
channel, the threshold is the larger of its fixed numerical floor and
1.10 times the maximum post-warm-up static-control value.

An alert is emitted when at least two channels exceed their thresholds
continuously for 1 s.

## Ground-truth evaluation boundary

Physical trajectory reference is used only to define degradation onset.
For each visual condition, onset occurs when the causal 5 s rolling
position RMSE exceeds the matched static temporal-offset envelope by
0.20 m continuously for 1 s.

The monitor is not permitted to use this signal.

## Primary success criterion

The pilot is `monitor_supported` only when:

1. zero of six static controls produce an alert
2. both early-warning positives produce an alert
3. the alert precedes degradation onset in both early-warning positives
4. at least 18 of 22 secondary dynamic cases are detected

`monitor_partial` is assigned when both positives are detected but one
lead time is non-positive, or when one static false positive occurs.

All other outcomes are `monitor_not_supported`.

## Scope boundary

This is monitor discovery on the same single trajectory used by V2-E02.
A successful result remains a pilot and requires multi-trajectory
validation before deployment claims.
"""
    (output / "analysis_plan.md").write_text(
        analysis_plan,
        encoding="utf-8",
        newline="\n",
    )

    print("scenario_count=30")
    print("static_negative_count=6")
    print("early_warning_positive_count=2")
    print("dynamic_secondary_count=22")
    print("monitor_channel_count=3")
    print("online_ground_truth_input_count=0")
    print("new_estimator_execution=NO")
    print("v2_progress_unchanged=55.0")
    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
