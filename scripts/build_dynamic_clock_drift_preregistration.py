#!/usr/bin/env python3
"""Build deterministic V2-E02 dynamic clock drift preregistration."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_PARENT = "92ba1942801f1c8dcfbb0fe71225712e334e70d5"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--audit-text", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--replication-results", type=Path, required=True)
    parser.add_argument("--replication-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def token(value: float) -> str:
    integer = int(round(abs(value)))
    return f"{integer:02d}"


def static_id(offset_ms: float, dropout: float) -> str:
    if offset_ms == 0.0:
        offset_token = "zero"
    elif offset_ms > 0.0:
        offset_token = f"pos{token(offset_ms)}"
    else:
        offset_token = f"neg{token(offset_ms)}"
    return (
        f"static-{offset_token}-drop"
        f"{int(round(dropout * 100)):02d}"
    )


def dynamic_id(
    profile: str,
    span_ms: float,
    dropout: float,
) -> str:
    profile_token = profile.replace("-", "")
    return (
        f"{profile_token}-span{token(span_ms)}-drop"
        f"{int(round(dropout * 100)):02d}"
    )


def main() -> int:
    args = arguments()

    config = load_json(args.config)
    audit = load_json(args.audit_json)
    replication_results = load_json(args.replication_results)
    replication_manifest = load_json(args.replication_manifest)

    if config["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("configuration upstream commit mismatch")
    if config["parent_evidence"]["commit"] != EXPECTED_PARENT:
        raise ValueError("configuration parent commit mismatch")
    if audit["experiment_commit"] != EXPECTED_PARENT:
        raise ValueError("audit parent commit mismatch")
    if audit["replication_status"] != "replicated_supported":
        raise ValueError("parent replication is not supported")
    if replication_results["replication_status"] != (
        "replicated_supported"
    ):
        raise ValueError("replication result is not supported")
    if replication_results["supported_cell_count"] != 4:
        raise ValueError("unexpected parent supported cell count")

    verification = replication_manifest["verification"]
    for key in (
        "five_seed_masks_distinct",
        "masks_equal_across_offsets",
        "masks_nested_within_seed",
        "physical_references_byte_identical",
        "raw_measurement_fingerprints_identical",
    ):
        if verification[key] is not True:
            raise ValueError(
                f"parent evidence verification failed: {key}"
            )

    design = config["design"]
    profiles = list(design["dynamic_profiles"])
    spans = [float(value) for value in design["drift_spans_ms"]]
    static_controls = [
        float(value)
        for value in design["static_controls_ms"]
    ]
    dropouts = [
        float(value)
        for value in design["visual_dropout_fractions"]
    ]
    repeat_count = int(design["repeat_count_per_scenario"])

    scenarios: list[dict[str, Any]] = []

    for dropout in dropouts:
        for offset in static_controls:
            scenarios.append(
                {
                    "dropout_fraction": f"{dropout:.2f}",
                    "drift_profile_seed": "",
                    "drift_span_ms": "0.0",
                    "profile": "static-control",
                    "repeat_count": repeat_count,
                    "scenario_id": static_id(offset, dropout),
                    "static_offset_ms": f"{offset:.1f}",
                }
            )

    for dropout in dropouts:
        for profile in profiles:
            for span in spans:
                scenarios.append(
                    {
                        "dropout_fraction": f"{dropout:.2f}",
                        "drift_profile_seed": (
                            design["drift_profile_seed"]
                            if profile == "piecewise-random-walk"
                            else ""
                        ),
                        "drift_span_ms": f"{span:.1f}",
                        "profile": profile,
                        "repeat_count": repeat_count,
                        "scenario_id": dynamic_id(
                            profile,
                            span,
                            dropout,
                        ),
                        "static_offset_ms": "0.0",
                    }
                )

    if len(scenarios) != 30:
        raise ValueError("unexpected scenario count")
    if sum(int(row["repeat_count"]) for row in scenarios) != 60:
        raise ValueError("unexpected estimator execution count")

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    preregistration = {
        "analysis": config["analysis"],
        "design": {
            "canonical_dropout_seed": int(
                design["canonical_dropout_seed"]
            ),
            "drift_profile_seed": int(
                design["drift_profile_seed"]
            ),
            "drift_spans_ms": spans,
            "dynamic_profiles": profiles,
            "estimator_execution_count": 60,
            "repeat_count_per_scenario": repeat_count,
            "scenario_count": 30,
            "static_controls_ms": static_controls,
            "visual_dropout_fractions": dropouts,
        },
        "experiment": "openvins-dynamic-clock-drift-pilot",
        "hypotheses": config["hypotheses"],
        "parent_evidence": config["parent_evidence"],
        "profile_definitions": config["profile_definitions"],
        "progress": config["progress_policy"],
        "schema_version": 1,
    }

    manifest = {
        "analysis_only": True,
        "experiment": "openvins-dynamic-clock-drift-pilot",
        "new_estimator_execution": False,
        "official_source_modified": False,
        "schema_version": 1,
        "source_inputs": {
            "audit_json_sha256": sha256(args.audit_json),
            "audit_text_sha256": sha256(args.audit_text),
            "config_sha256": sha256(args.config),
            "replication_manifest_sha256": sha256(
                args.replication_manifest
            ),
            "replication_results_sha256": sha256(
                args.replication_results
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

    with (output / "scenario_plan.csv").open(
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
                "static_offset_ms",
                "dropout_fraction",
                "drift_profile_seed",
                "repeat_count",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(scenarios)

    analysis_plan = f"""# V2-E02 dynamic camera-to-IMU clock drift pilot

## Motivation

V2-E01b replicated a global and local trajectory-error interaction under
bounded static temporal offsets and visual dropout. Across all 105
physical scenarios, online temporal calibration still converged,
one-metre availability remained 100%, final temporal residual remained
below 0.012 ms and no sustained service failure occurred.

The next question is whether time-varying clock error produces
trajectory degradation before these conventional terminal diagnostics
indicate failure.

## Fixed scenarios

Static controls:

- offsets: `{static_controls}` ms
- visual dropout: `{dropouts}`

Dynamic profiles:

- `{profiles[0]}`
- `{profiles[1]}`
- `{profiles[2]}`
- `{profiles[3]}`

Dynamic spans:

- `{spans[0]} ms`
- `{spans[1]} ms`
- `{spans[2]} ms`

A span is the complete bounded range. A 20 ms span therefore remains
inside `[-10 ms, +10 ms]`, matching the static controls.

Total scenarios: `30`

Each scenario is executed twice.

Planned estimator executions: `60`

## Profile definitions

- linear-positive: starts at `-span/2` and ends at `+span/2`
- linear-negative: starts at `+span/2` and ends at `-span/2`
- sinusoidal-slow: one zero-mean cycle across the trajectory
- piecewise-random-walk: twelve deterministic mean-centred knots,
  scaled to the same bounded span and linearly interpolated

## Primary comparison

Every dynamic cell is compared with the zero-offset static control under
the same visual condition.

Three metric groups are preregistered:

1. global trajectory RMSE
2. maximum rolling local RMSE
3. dynamic temporal-tracking error and lag

A cell is supported when at least two metric groups cross their practical
thresholds.

The pilot is supported only when one profile has at least two supported
drift spans and its global RMSE is nondecreasing with span.

## Early-warning gap

A supported dynamic cell is classified as an early-warning gap when:

- final absolute temporal residual is below `0.5 ms`
- one-metre availability remains `1.0`
- no sustained failure occurs

This tests whether trajectory precision can degrade before terminal
calibration and service diagnostics become abnormal.

## Visual condition

The 10% visual-dropout condition uses the canonical nested mask from the
replicated interaction experiment. Its dynamic-drift interaction is
exploratory because only one dropout seed is used in this pilot.

## Claim boundary

This is one official deterministic trajectory and one dynamic-profile
realization. A supported pilot identifies dynamic profiles for later
multi-seed and multi-trajectory validation; it does not establish a
general clock-drift failure law.
"""
    (output / "analysis_plan.md").write_text(
        analysis_plan,
        encoding="utf-8",
        newline="\n",
    )

    print(f"scenario_count={len(scenarios)}")
    print("static_control_count=6")
    print("dynamic_scenario_count=24")
    print("estimator_execution_count=60")
    print(f"dynamic_profile_count={len(profiles)}")
    print(f"drift_span_count={len(spans)}")
    print("visual_condition_count=2")
    print("v2_progress_unchanged=35.0")
    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
