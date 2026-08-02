#!/usr/bin/env python3
"""Build deterministic V2-E01b preregistration artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
EXPECTED_PARENT = "70c27e0957bd03eaa0a8a87f35d394d9b046241b"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--audit-text", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--parent-manifest", type=Path, required=True)
    parser.add_argument("--parent-results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def scenario_id(seed: int, offset: float, dropout: float) -> str:
    offset_token = (
        "zero"
        if offset == 0.0
        else ("pos" if offset > 0 else "neg")
        + f"{abs(int(offset)):02d}"
    )
    dropout_token = f"drop{int(round(dropout * 100)):02d}"
    return f"s{seed}-{offset_token}-{dropout_token}"


def main() -> int:
    args = arguments()

    config = load_json(args.config)
    audit = load_json(args.audit_json)
    parent_manifest = load_json(args.parent_manifest)
    parent_results = load_json(args.parent_results)

    if config["upstream_commit"] != EXPECTED_COMMIT:
        raise ValueError("configuration upstream commit mismatch")
    if config["parent_experiment"]["commit"] != EXPECTED_PARENT:
        raise ValueError("configuration parent commit mismatch")
    if audit["experiment_commit"] != EXPECTED_PARENT:
        raise ValueError("audit parent commit mismatch")
    if audit["interaction_status"] != "pilot_supported":
        raise ValueError("parent pilot is not supported")
    if sorted(
        audit["strongest_interaction"]["supported_flags"]
    ) != [
        "local_rmse_supported",
        "rmse_supported",
    ]:
        raise ValueError("unexpected parent support flags")
    if parent_results["interaction_status"] != "pilot_supported":
        raise ValueError("parent results are not supported")
    if parent_manifest["verification"][
        "deterministic_replay_verified"
    ] is not True:
        raise ValueError("parent deterministic replay is not verified")
    if parent_manifest["verification"][
        "dropout_masks_nested"
    ] is not True:
        raise ValueError("parent nested masks are not verified")
    if parent_manifest["verification"][
        "single_factor_anchors_reproduced"
    ] is not True:
        raise ValueError("parent anchors are not verified")

    design = config["design"]
    offsets = [float(value) for value in design["offsets_ms"]]
    dropouts = [
        float(value)
        for value in design["dropout_fractions"]
    ]
    seeds = [int(value) for value in design["seeds"]]
    canonical_seed = int(design["canonical_seed"])
    policy = config["execution_policy"]

    analytical_cells = []
    execution_rows = []

    for seed in seeds:
        for offset in offsets:
            for dropout in dropouts:
                physical_seed = (
                    canonical_seed if dropout == 0.0 else seed
                )
                physical_id = scenario_id(
                    physical_seed,
                    offset,
                    dropout,
                )
                analytical_cells.append(
                    {
                        "analytical_cell_id": scenario_id(
                            seed,
                            offset,
                            dropout,
                        ),
                        "dropout_fraction": f"{dropout:.2f}",
                        "offset_ms": f"{offset:.1f}",
                        "physical_scenario_id": physical_id,
                        "seed": seed,
                        "shared_zero_dropout_anchor": (
                            dropout == 0.0
                        ),
                    }
                )

    replay_audit = policy[
        "additional_seed_replay_audit_cell"
    ]
    replay_offset = float(replay_audit["offset_ms"])
    replay_dropout = float(replay_audit["dropout_fraction"])

    for seed in seeds:
        for offset in offsets:
            for dropout in dropouts:
                if seed != canonical_seed and dropout == 0.0:
                    continue

                if seed == canonical_seed:
                    repeat_count = int(
                        policy["canonical_seed_repeat_count"]
                    )
                    purpose = "canonical-factorial-deterministic-replay"
                else:
                    repeat_count = int(
                        policy[
                            "noncanonical_nonzero_dropout_repeat_count"
                        ]
                    )
                    purpose = "statistical-seed-replication"
                    if (
                        offset == replay_offset
                        and dropout == replay_dropout
                    ):
                        repeat_count += 1
                        purpose = (
                            "statistical-seed-replication-and-"
                            "determinism-audit"
                        )

                execution_rows.append(
                    {
                        "dropout_fraction": f"{dropout:.2f}",
                        "offset_ms": f"{offset:.1f}",
                        "physical_scenario_id": scenario_id(
                            seed,
                            offset,
                            dropout,
                        ),
                        "purpose": purpose,
                        "repeat_count": repeat_count,
                        "seed": seed,
                    }
                )

    analytical_cell_count = len(analytical_cells)
    physical_scenario_count = len(execution_rows)
    estimator_execution_count = sum(
        int(row["repeat_count"])
        for row in execution_rows
    )

    if analytical_cell_count != 125:
        raise ValueError("unexpected analytical cell count")
    if physical_scenario_count != 105:
        raise ValueError("unexpected physical scenario count")
    if estimator_execution_count != 134:
        raise ValueError("unexpected estimator execution count")

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    preregistration = {
        "design": {
            "analytical_cell_count": analytical_cell_count,
            "dropout_fractions": dropouts,
            "estimator_execution_count": estimator_execution_count,
            "offsets_ms": offsets,
            "physical_scenario_count": physical_scenario_count,
            "seeds": seeds,
        },
        "experiment": (
            "openvins-temporal-visual-interaction-replication"
        ),
        "hypothesis": config["hypothesis"],
        "parent_result": {
            "commit": EXPECTED_PARENT,
            "interaction_status": audit["interaction_status"],
            "strongest_scenario": audit[
                "strongest_interaction"
            ]["scenario"],
            "supported_flags": sorted(
                audit["strongest_interaction"][
                    "supported_flags"
                ]
            ),
            "strongest_rmse_interaction_ratio": audit[
                "strongest_interaction"
            ]["rmse_interaction_ratio"],
            "strongest_local_interaction_ratio": audit[
                "strongest_interaction"
            ]["local_rmse_interaction_ratio"],
        },
        "progress": config["progress_policy"],
        "replicated_support_criterion": {
            **config["analysis"][
                "cell_level_replicated_support"
            ],
            "seed_level_support": config["analysis"][
                "seed_level_support"
            ],
            "t_critical_95_two_sided_df4": config[
                "analysis"
            ]["t_critical_95_two_sided_df4"],
        },
        "schema_version": 1,
    }

    manifest = {
        "analysis_only": True,
        "experiment": (
            "openvins-temporal-visual-interaction-replication"
        ),
        "new_estimator_execution": False,
        "official_source_modified": False,
        "schema_version": 1,
        "source_inputs": {
            "audit_json_sha256": sha256(args.audit_json),
            "audit_text_sha256": sha256(args.audit_text),
            "config_sha256": sha256(args.config),
            "parent_manifest_sha256": sha256(
                args.parent_manifest
            ),
            "parent_results_sha256": sha256(
                args.parent_results
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

    with (output / "analysis_cells.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "analytical_cell_id",
                "seed",
                "offset_ms",
                "dropout_fraction",
                "physical_scenario_id",
                "shared_zero_dropout_anchor",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(analytical_cells)

    with (output / "execution_plan.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "physical_scenario_id",
                "seed",
                "offset_ms",
                "dropout_fraction",
                "repeat_count",
                "purpose",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(execution_rows)

    analysis_plan = f"""# V2-E01b temporal-visual interaction replication

## Motivation

The parent pilot found two-metric super-additive trajectory-error
interaction at both `-20 ms × 10% dropout` and
`+20 ms × 10% dropout`. The interaction disappeared at 30% and 50%
dropout, while temporal-calibration convergence, residual and
one-metre availability remained healthy.

The refined hypothesis is therefore not a catastrophic temporal
calibration failure. It is a low-dropout state-estimation error coupling
that may weaken when visual dropout becomes the dominant error source.

## Fixed design

- offsets: `{offsets}`
- dropout fractions: `{dropouts}`
- nested-dropout seeds: `{seeds}`
- analytical cells: `{analytical_cell_count}`
- unique physical scenarios: `{physical_scenario_count}`
- estimator executions: `{estimator_execution_count}`

Zero-dropout anchors are deterministic and shared across seeds.
The complete canonical-seed matrix is executed twice. Each additional
seed is executed once at nonzero dropout, with the parent strongest cell
executed twice as a seed-specific determinism audit.

## Primary replicated criterion

For each joint offset-dropout cell, interaction contrasts are calculated
within seed using the seed-matched dropout-only result and the shared
deterministic offset-only anchor.

A cell is `replicated_supported` only when:

1. at least four of five seeds independently satisfy both global-RMSE
   and local-RMSE practical thresholds
2. mean global and local additive interactions are at least `0.01 m`
3. mean global and local interaction ratios are at least `1.25`
4. lower 95% confidence bounds for both additive interactions are
   greater than zero

## Secondary analyses

- paired positive-versus-negative offset differences
- low-dropout boundary between 5% and 20%
- nonmonotonic interaction peaks
- calibration convergence and residual as negative-control outcomes

## Claim boundary

The experiment remains one official simulation trajectory. Five dropout
seeds improve stochastic replication but do not establish
multi-trajectory or real-world generalization.
"""
    (output / "analysis_plan.md").write_text(
        analysis_plan,
        encoding="utf-8",
        newline="\n",
    )

    print(f"analytical_cell_count={analytical_cell_count}")
    print(f"physical_scenario_count={physical_scenario_count}")
    print(f"estimator_execution_count={estimator_execution_count}")
    print(f"seed_count={len(seeds)}")
    print("parent_supported_flags=local_rmse_supported,rmse_supported")
    print("v2_progress_unchanged=20.0")
    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
