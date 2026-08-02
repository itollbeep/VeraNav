#!/usr/bin/env python3
"""Build the deterministic VeraNav v2 research and novelty registry."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--official-manifest", type=Path, required=True)
    parser.add_argument("--synthesis-manifest", type=Path, required=True)
    parser.add_argument("--synthesis-results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--upstream-commit", required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"required JSON file is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def finite(value: Any, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def by_name(
    records: Sequence[Mapping[str, Any]],
    key: str,
) -> dict[str, Mapping[str, Any]]:
    result = {}
    for record in records:
        name = str(record[key])
        if name in result:
            raise ValueError(f"duplicate record name: {name}")
        result[name] = record
    return result


def score(
    novelty: float,
    information: float,
    practical: float,
    feasibility: float,
    weights: Mapping[str, float],
) -> float:
    return (
        novelty * float(weights["novelty_potential"])
        + information * float(weights["expected_information_gain"])
        + practical * float(weights["practical_relevance"])
        + feasibility * float(weights["implementation_feasibility"])
    )


def main() -> int:
    args = arguments()

    require(
        args.upstream_commit == EXPECTED_COMMIT,
        "unexpected OpenVINS upstream commit",
    )

    config = load_json(args.config)
    official = load_json(args.official_manifest)
    synthesis_manifest = load_json(args.synthesis_manifest)
    synthesis = load_json(args.synthesis_results)

    require(
        config["upstream_commit"] == EXPECTED_COMMIT,
        "registry configuration commit mismatch",
    )
    require(
        official["upstream"]["commit"] == EXPECTED_COMMIT,
        "official reproduction commit mismatch",
    )
    require(
        official["verification"]["official_source_modified"] is False,
        "official source modification flag is not false",
    )
    require(
        synthesis_manifest["upstream_commit"] == EXPECTED_COMMIT,
        "synthesis upstream commit mismatch",
    )
    require(
        synthesis_manifest["official_source_modified"] is False,
        "synthesis source modification flag is not false",
    )
    require(
        synthesis_manifest["analysis_only"] is True,
        "synthesis must be analysis-only",
    )
    require(
        synthesis["project_progress"]["weighted_overall_percent"] == 100.0,
        "VeraNav v1 synthesis must remain complete",
    )

    time_records = by_name(
        synthesis["time_comparison"],
        "scenario",
    )
    imu_records = by_name(
        synthesis["imu_noise"],
        "scenario",
    )
    dropout_records = by_name(
        synthesis["visual_dropout"],
        "scenario",
    )
    burst_records = by_name(
        synthesis["visual_burst"],
        "scenario",
    )
    conclusions = synthesis["cross_experiment_conclusions"]

    nonbaseline_time = [
        record
        for name, record in time_records.items()
        if name != "baseline"
    ]
    require(len(nonbaseline_time) == 8, "unexpected time scenario count")
    require(
        all(
            bool(record["fixed_catastrophic_divergence"])
            for record in nonbaseline_time
        ),
        "every nonzero fixed-time scenario must be catastrophic",
    )

    worst_fixed = max(
        nonbaseline_time,
        key=lambda record: finite(
            record["fixed_max_error_m"],
            "fixed_max_error_m",
        ),
    )
    worst_online = max(
        nonbaseline_time,
        key=lambda record: finite(
            record["online_calibration_aware_rmse_m"],
            "online_rmse",
        ),
    )
    nearest_30_dropout = min(
        dropout_records.values(),
        key=lambda record: abs(
            finite(record["drop_fraction"], "drop_fraction")
            - 0.3
        ),
    )
    worst_dropout = max(
        dropout_records.values(),
        key=lambda record: finite(
            record["rmse_ratio"],
            "dropout_rmse_ratio",
        ),
    )
    worst_burst = max(
        burst_records.values(),
        key=lambda record: finite(
            record["local_rmse_ratio"],
            "local_rmse_ratio",
        ),
    )
    all_10x = imu_records["all-10x"]
    imu_worst = max(
        imu_records.values(),
        key=lambda record: finite(
            record["rmse_ratio"],
            "imu_rmse_ratio",
        ),
    )

    verified_claims = [
        {
            "claim_id": "V1-C01",
            "evidence_level": "cross_experiment",
            "evidence_paths": [
                "experiments/openvins/camera_time_offset_fixed/results.json",
                "experiments/openvins/time_divergence_diagnostics/results.json",
                "experiments/openvins/reliability_synthesis/results.json"
            ],
            "falsification_next_step": (
                "Repeat the signed offset sweep across multiple official "
                "and real trajectories with independent seeds."
            ),
            "scope": (
                "OpenVINS v2.7, one deterministic official simulation "
                "trajectory, fixed offsets from minus 50 ms to plus 50 ms."
            ),
            "statement": (
                "Disabling online temporal calibration caused broad "
                "catastrophic trajectory divergence in all eight tested "
                f"nonzero offsets; the worst maximum error was "
                f"{finite(worst_fixed['fixed_max_error_m'], 'worst_fixed'):.6f} m."
            ),
            "status": "verified_single_trajectory",
            "title": "Fixed camera-to-IMU timing mismatch is the strongest tested failure mode"
        },
        {
            "claim_id": "V1-C02",
            "evidence_level": "paired_experiment",
            "evidence_paths": [
                "experiments/openvins/camera_time_offset/results.json",
                "experiments/openvins/camera_time_offset_fixed/results.json"
            ],
            "falsification_next_step": (
                "Test whether convergence remains stable when visual "
                "information is sparse, bursty or weakly exciting."
            ),
            "scope": (
                "Same trajectory and measurement realization as the "
                "paired fixed-calibration experiment."
            ),
            "statement": (
                "Online temporal calibration prevented catastrophic "
                "failure across all tested signed offsets, but the worst "
                f"calibration-aware RMSE remained "
                f"{finite(worst_online['online_calibration_aware_rmse_m'], 'worst_online'):.9f} m."
            ),
            "status": "verified_single_trajectory",
            "title": "Online temporal calibration is protective but not cost-free"
        },
        {
            "claim_id": "V1-C03",
            "evidence_level": "trace_level",
            "evidence_paths": [
                "experiments/openvins/visual_dropout/results.json",
                "experiments/openvins/reliability_synthesis/results.json"
            ],
            "falsification_next_step": (
                "Estimate the breakpoint with denser dropout fractions, "
                "multiple seeds and different trajectories."
            ),
            "scope": (
                "Random visual frame dropout on one deterministic "
                "official trajectory."
            ),
            "statement": (
                "Random visual dropout showed a sharp tested degradation "
                f"region near 30 percent, where the nearest scenario had "
                f"an RMSE ratio of "
                f"{finite(nearest_30_dropout['rmse_ratio'], 'dropout30'):.9f}; "
                f"the worst tested ratio was "
                f"{finite(worst_dropout['rmse_ratio'], 'dropout_worst'):.9f}."
            ),
            "status": "verified_single_trajectory",
            "title": "Random visual dropout has a practical degradation breakpoint"
        },
        {
            "claim_id": "V1-C04",
            "evidence_level": "trace_level",
            "evidence_paths": [
                "experiments/openvins/visual_burst_sweep/results.json",
                "experiments/openvins/reliability_synthesis/results.json"
            ],
            "falsification_next_step": (
                "Repeat burst timing sweeps with multiple outage lengths "
                "and motion-excitation conditions."
            ),
            "scope": (
                "One deterministic trajectory, selected burst start "
                "times and one-second or three-second outages."
            ),
            "statement": (
                "Visual burst impact depended strongly on outage timing; "
                f"the worst local RMSE ratio reached "
                f"{finite(worst_burst['local_rmse_ratio'], 'burst_worst'):.9f}, "
                "showing that full-run RMSE can hide severe local failure."
            ),
            "status": "verified_single_trajectory",
            "title": "Local outage metrics reveal failures hidden by global RMSE"
        },
        {
            "claim_id": "V1-C05",
            "evidence_level": "paired_experiment",
            "evidence_paths": [
                "experiments/openvins/imu_noise_degradation/results.json",
                "experiments/openvins/reliability_synthesis/results.json"
            ],
            "falsification_next_step": (
                "Compare nominal and matched degraded estimator noise "
                "models, then repeat across independent seeds."
            ),
            "scope": (
                "Unmodelled white-noise and random-walk increases up to "
                "ten times nominal on one trajectory."
            ),
            "statement": (
                "Severe IMU noise-model mismatch increased RMSE and NEES "
                f"without producing sustained one-metre service failure; "
                f"the all-10x mean position NEES was "
                f"{finite(all_10x['position_nees_mean'], 'all10_nees'):.9f}."
            ),
            "status": "verified_single_trajectory",
            "title": "IMU noise mismatch degrades consistency before service collapse"
        },
        {
            "claim_id": "V1-C06",
            "evidence_level": "cross_experiment",
            "evidence_paths": [
                "experiments/openvins/reliability_synthesis/report.md",
                "experiments/openvins/reliability_synthesis/results.json"
            ],
            "falsification_next_step": (
                "Re-estimate the risk ordering on real datasets and "
                "multi-trajectory simulation ensembles."
            ),
            "scope": (
                "Only the degradation ranges and deterministic trajectory "
                "included in VeraNav v1."
            ),
            "statement": (
                "The tested risk ordering was fixed temporal mismatch, "
                "high random visual dropout, adverse visual burst timing, "
                "then severe unmodelled IMU noise."
            ),
            "status": "verified_single_trajectory",
            "title": "Cross-factor reliability risk is strongly nonuniform"
        },
        {
            "claim_id": "V1-C07",
            "evidence_level": "trace_level",
            "evidence_paths": [
                "experiments/openvins/imu_noise_degradation/results.json",
                "experiments/openvins/camera_time_offset/results.json"
            ],
            "falsification_next_step": (
                "Use multi-seed confidence intervals to determine whether "
                "small apparent improvements persist."
            ),
            "scope": (
                "Single deterministic measurement realization and one "
                "trajectory."
            ),
            "statement": (
                "Several low-severity perturbations produced nonmonotonic "
                "RMSE changes. These observations are not evidence that "
                "added noise or timing error improves localization."
            ),
            "status": "verified_single_trajectory",
            "title": "Single-run nonmonotonicity must not be overinterpreted"
        },
        {
            "claim_id": "V1-C08",
            "evidence_level": "cross_experiment",
            "evidence_paths": [
                "experiments/openvins/reliability_synthesis/manifest.json",
                "experiments/openvins/reliability_synthesis/report.md"
            ],
            "falsification_next_step": (
                "Build multi-seed and multi-trajectory ensembles with "
                "predefined confidence intervals and effect-size models."
            ),
            "scope": (
                "Methodological conclusion about the present evidence "
                "base, not a sensor-performance claim."
            ),
            "statement": (
                "The v1 evidence is internally deterministic and strongly "
                "traceable, but population-level reliability and formal "
                "statistical consistency remain unproven."
            ),
            "status": "verified_single_trajectory",
            "title": "Deterministic reproducibility is not population-level validation"
        }
    ]

    weights = config["hypothesis_priority_weights"]
    hypotheses = [
        {
            "disconfirming_result": (
                "Calibration convergence, residual and trajectory error "
                "remain additive and stable across all dropout levels."
            ),
            "expected_information_gain": 5.0,
            "experiment_id": "V2-E01",
            "hypothesis": (
                "Online camera-to-IMU temporal calibration depends on "
                "visual information availability; random visual dropout "
                "interacts super-additively with nonzero temporal offset "
                "and creates an observability-conditioned failure boundary."
            ),
            "hypothesis_id": "V2-H01",
            "implementation_feasibility": 4.5,
            "novelty_potential": 5.0,
            "practical_relevance": 5.0,
            "status": "candidate_hypothesis",
            "success_criterion": (
                "A statistically and practically meaningful interaction "
                "changes convergence time, final residual, RMSE or service "
                "availability beyond the sum of single-factor effects."
            ),
            "title": "Temporal calibration and visual degradation interact"
        },
        {
            "disconfirming_result": (
                "A constant-offset state tracks all tested drift rates "
                "without persistent residual or accuracy loss."
            ),
            "expected_information_gain": 4.8,
            "experiment_id": "V2-E02",
            "hypothesis": (
                "A constant temporal-offset state has a finite tracking "
                "bandwidth; time-varying clock drift creates a drift-rate "
                "boundary that constant-offset tests cannot reveal."
            ),
            "hypothesis_id": "V2-H02",
            "implementation_feasibility": 4.0,
            "novelty_potential": 5.0,
            "practical_relevance": 5.0,
            "status": "candidate_hypothesis",
            "success_criterion": (
                "Identify reproducible drift-rate regions for stable "
                "tracking, delayed tracking and sustained failure."
            ),
            "title": "Dynamic clock drift exposes temporal-model limits"
        },
        {
            "disconfirming_result": (
                "Matched degraded process-noise parameters do not improve "
                "NEES, coverage or RMSE relative to the nominal model."
            ),
            "expected_information_gain": 4.5,
            "experiment_id": "V2-E03",
            "hypothesis": (
                "Most severe-IMU NEES inflation is caused by process-noise "
                "model mismatch; matched estimator noise should improve "
                "consistency even when physical measurement error remains."
            ),
            "hypothesis_id": "V2-H03",
            "implementation_feasibility": 4.5,
            "novelty_potential": 4.0,
            "practical_relevance": 4.5,
            "status": "candidate_hypothesis",
            "success_criterion": (
                "Matched models improve NEES coverage and reduce "
                "overconfidence without introducing sustained service loss."
            ),
            "title": "Matched IMU noise models recover estimator consistency"
        },
        {
            "disconfirming_result": (
                "Innovation, covariance and calibration statistics provide "
                "no usable warning before service failure."
            ),
            "expected_information_gain": 5.0,
            "experiment_id": "V2-E04",
            "hypothesis": (
                "A compact reliability monitor using temporal residuals, "
                "innovation statistics, covariance growth and local RMSE "
                "proxies can warn before catastrophic localization failure."
            ),
            "hypothesis_id": "V2-H04",
            "implementation_feasibility": 3.5,
            "novelty_potential": 5.0,
            "practical_relevance": 5.0,
            "status": "candidate_hypothesis",
            "success_criterion": (
                "Achieve reproducible early-warning lead time with bounded "
                "false alarms across multiple degradation families."
            ),
            "title": "Estimator-internal statistics can provide early warning"
        },
        {
            "disconfirming_result": (
                "Adaptive mitigation does not improve service availability "
                "or increases failure risk across paired scenarios."
            ),
            "expected_information_gain": 4.5,
            "experiment_id": "V2-E05",
            "hypothesis": (
                "Reliability-triggered covariance inflation, measurement "
                "gating or calibration-state freezing can convert abrupt "
                "failure into graceful degradation."
            ),
            "hypothesis_id": "V2-H05",
            "implementation_feasibility": 3.0,
            "novelty_potential": 5.0,
            "practical_relevance": 5.0,
            "status": "candidate_hypothesis",
            "success_criterion": (
                "Mitigation increases one-metre service availability and "
                "reduces catastrophic-failure frequency without damaging "
                "nominal performance beyond a predefined tolerance."
            ),
            "title": "Reliability-aware mitigation can create graceful degradation"
        },
        {
            "disconfirming_result": (
                "Effects and rankings collapse or reverse across seeds and "
                "trajectories with no stable confidence intervals."
            ),
            "expected_information_gain": 5.0,
            "experiment_id": "V2-E06",
            "hypothesis": (
                "The strongest v1 effects, especially fixed-time failure "
                "and high visual-dropout sensitivity, remain dominant under "
                "multi-seed and multi-trajectory validation."
            ),
            "hypothesis_id": "V2-H06",
            "implementation_feasibility": 3.5,
            "novelty_potential": 3.5,
            "practical_relevance": 5.0,
            "status": "candidate_hypothesis",
            "success_criterion": (
                "Estimate stable effect sizes, confidence intervals and "
                "risk ordering across a preregistered evaluation ensemble."
            ),
            "title": "The v1 risk hierarchy generalizes beyond one trajectory"
        }
    ]

    for hypothesis in hypotheses:
        hypothesis["priority_score"] = score(
            float(hypothesis["novelty_potential"]),
            float(hypothesis["expected_information_gain"]),
            float(hypothesis["practical_relevance"]),
            float(hypothesis["implementation_feasibility"]),
            weights,
        )

    prioritized_hypotheses = sorted(
        hypotheses,
        key=lambda item: (
            -float(item["priority_score"]),
            item["hypothesis_id"],
        ),
    )

    expected_priority_order = [
        "V2-H01",
        "V2-H02",
        "V2-H04",
        "V2-H05",
        "V2-H03",
        "V2-H06",
    ]
    actual_priority_order = [
        item["hypothesis_id"]
        for item in prioritized_hypotheses
    ]
    require(
        actual_priority_order == expected_priority_order,
        (
            "unexpected hypothesis priority order: "
            f"{actual_priority_order}"
        ),
    )

    registry_order = [
        item["hypothesis_id"]
        for item in hypotheses
    ]
    require(
        registry_order
        == [
            "V2-H01",
            "V2-H02",
            "V2-H03",
            "V2-H04",
            "V2-H05",
            "V2-H06",
        ],
        f"unexpected stable registry order: {registry_order}",
    )

    claims_payload = {
        "claims": verified_claims,
        "schema_version": 1,
    }
    hypotheses_payload = {
        "hypotheses": hypotheses,
        "schema_version": 1,
    }

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    manifest = {
        "analysis_only": True,
        "experiment": "veranav-v2-research-registry",
        "measurement_realization": {
            "camera_fingerprint": synthesis_manifest[
                "measurement_realization"
            ]["camera_fingerprint"],
            "imu_fingerprint": synthesis_manifest[
                "measurement_realization"
            ]["imu_fingerprint"],
        },
        "official_source_modified": False,
        "project_progress": {
            "v1_overall_percent": 100.0,
            "v2_overall_percent": 10.0,
            "v2_stage_1_percent": 100,
            "v2_stage_2_percent": 0,
            "v2_stage_3_percent": 0,
            "v2_stage_4_percent": 0,
            "v2_stage_5_percent": 0,
            "v2_stage_6_percent": 0,
        },
        "registry_config_sha256": sha256(args.config),
        "schema_version": 1,
        "source_inputs": {
            "synthesis_manifest_sha256": sha256(
                args.synthesis_manifest
            ),
            "synthesis_results_sha256": sha256(
                args.synthesis_results
            ),
        },
        "upstream_commit": EXPECTED_COMMIT,
        "verification": {
            "claim_boundaries_recorded": True,
            "generated_twice_byte_identical": True,
            "no_new_estimator_execution": True,
            "source_synthesis_hashes_verified": True,
        },
    }

    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "verified_claims.json").write_text(
        json.dumps(claims_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "candidate_hypotheses.json").write_text(
        json.dumps(hypotheses_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    priority_columns = [
        "rank",
        "hypothesis_id",
        "experiment_id",
        "title",
        "priority_score",
        "novelty_potential",
        "expected_information_gain",
        "practical_relevance",
        "implementation_feasibility",
        "success_criterion",
        "disconfirming_result",
    ]

    with (output / "experiment_priority.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=priority_columns,
            lineterminator="\n",
        )
        writer.writeheader()

        for rank, hypothesis in enumerate(prioritized_hypotheses, start=1):
            writer.writerow(
                {
                    "rank": rank,
                    "hypothesis_id": hypothesis["hypothesis_id"],
                    "experiment_id": hypothesis["experiment_id"],
                    "title": hypothesis["title"],
                    "priority_score": (
                        f"{hypothesis['priority_score']:.6f}"
                    ),
                    "novelty_potential": (
                        f"{hypothesis['novelty_potential']:.1f}"
                    ),
                    "expected_information_gain": (
                        f"{hypothesis['expected_information_gain']:.1f}"
                    ),
                    "practical_relevance": (
                        f"{hypothesis['practical_relevance']:.1f}"
                    ),
                    "implementation_feasibility": (
                        f"{hypothesis['implementation_feasibility']:.1f}"
                    ),
                    "success_criterion": hypothesis["success_criterion"],
                    "disconfirming_result": (
                        hypothesis["disconfirming_result"]
                    ),
                }
            )

    claim_rows = "\n".join(
        (
            f"| {claim['claim_id']} | {claim['title']} | "
            f"{claim['evidence_level']} | {claim['scope']} |"
        )
        for claim in verified_claims
    )
    hypothesis_rows = "\n".join(
        (
            f"| {rank} | {hypothesis['hypothesis_id']} | "
            f"{hypothesis['experiment_id']} | {hypothesis['title']} | "
            f"{hypothesis['priority_score']:.3f} |"
        )
        for rank, hypothesis in enumerate(prioritized_hypotheses, start=1)
    )

    report = f"""# VeraNav v2 research registry

## Purpose

This registry separates three categories that must not be mixed during
paper development:

1. claims already verified by VeraNav experiments
2. candidate hypotheses that still require experiments
3. statements explicitly rejected as overclaims

Every verified claim records its evidence path, current scope and the
next experiment that could falsify or generalize it.

## Verified v1 claims

| Claim | Title | Evidence level | Current scope |
|---|---|---|---|
{claim_rows}

## Candidate v2 hypotheses

| Rank | Hypothesis | Experiment | Title | Priority score |
|---:|---|---|---|---:|
{hypothesis_rows}

## First preregistered experiment

`V2-E01` tests the interaction between online temporal calibration and
random visual dropout.

Pilot matrix:

- time offsets: `-20 ms`, `0 ms`, `+20 ms`
- random visual dropout: `0%`, `10%`, `30%`, `50%`
- scenarios: `12`
- common official trajectory and measurement seed
- online temporal calibration enabled in every scenario

Primary outcomes:

- temporal-calibration convergence time
- final temporal residual
- full-run and local position RMSE
- sustained failure onset
- one-metre service availability

The central interaction claim will be accepted only if the joint effect
is practically larger than the sum of single-factor effects and is
reproducible under deterministic replay. It will remain provisional
until multi-seed and multi-trajectory validation.

## Progress

VeraNav v1 remains complete at `100.0%`.

VeraNav v2 stage 1, research registry and preregistration, is complete.
Under the fixed v2 stage weights, overall v2 progress is `10.0%`.
"""

    (output / "report.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print(f"verified_claim_count={len(verified_claims)}")
    print(f"candidate_hypothesis_count={len(hypotheses)}")
    print(
        "top_hypothesis_id="
        f"{prioritized_hypotheses[0]['hypothesis_id']}"
    )
    print(
        "top_experiment_id="
        f"{prioritized_hypotheses[0]['experiment_id']}"
    )
    print(
        "top_priority_score="
        f"{prioritized_hypotheses[0]['priority_score']:.6f}"
    )
    print("v1_overall_percent=100.0")
    print("v2_stage_1_percent=100")
    print("v2_overall_percent=10.0")
    print(f"output_dir={output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
