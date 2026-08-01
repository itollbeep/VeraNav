#!/usr/bin/env python3
"""Run a paired degradation study and adaptive reliability-boundary search."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from veranav.boundary import ReliabilityRequirement, search_reliability_boundary
from veranav.comparison import compare_experiment_configs
from veranav.degradation import GnssDegradation
from veranav.experiment import ExperimentConfig
from veranav.monte_carlo import FailureCriteria
from veranav.report import StudyReport, write_study_report
from veranav.simulation import CircularTrajectoryConfig


def _positive_int(value: str) -> int:
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return result


def _seed_sequence(count: int) -> tuple[int, ...]:
    return tuple(range(count))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic VeraNav reliability study.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/reliability_study"),
    )
    parser.add_argument("--seeds", type=_positive_int, default=8)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--fault-start-s", type=float, default=1.0)
    parser.add_argument("--comparison-bias-m", type=float, default=8.0)
    parser.add_argument("--comparison-outage-s", type=float, default=2.0)
    parser.add_argument("--max-bias-m", type=float, default=12.0)
    parser.add_argument("--boundary-tolerance-m", type=float, default=0.5)
    args = parser.parse_args()

    if args.quick:
        trajectory = CircularTrajectoryConfig(
            duration_s=2.0,
            imu_dt=0.02,
            gnss_dt=0.2,
        )
        outage_levels = (0.0, 0.5, 1.0)
        bootstrap_resamples = 300
        max_iterations = 8
    else:
        trajectory = CircularTrajectoryConfig(
            duration_s=8.0,
            imu_dt=0.02,
            gnss_dt=0.2,
        )
        outage_levels = (0.0, 1.0, 2.0, 4.0)
        bootstrap_resamples = 2_000
        max_iterations = 12

    if not 0.0 <= args.fault_start_s <= trajectory.duration_s:
        parser.error("--fault-start-s must lie within the trajectory duration")
    if args.comparison_bias_m < 0.0 or args.comparison_outage_s < 0.0:
        parser.error("comparison degradation levels must be nonnegative")

    baseline = ExperimentConfig(trajectory=trajectory)
    remaining = trajectory.duration_s - args.fault_start_s + trajectory.imu_dt
    degraded = replace(
        baseline,
        degradation=GnssDegradation(
            outage_start_s=(
                args.fault_start_s if args.comparison_outage_s > 0.0 else None
            ),
            outage_duration_s=args.comparison_outage_s,
            bias_start_s=(
                args.fault_start_s if args.comparison_bias_m > 0.0 else None
            ),
            bias_duration_s=(remaining if args.comparison_bias_m > 0.0 else 0.0),
            bias_n=[args.comparison_bias_m, 0.0, 0.0],
        ),
    )
    seeds = _seed_sequence(args.seeds)
    criteria = FailureCriteria()
    comparison = compare_experiment_configs(
        baseline,
        degraded,
        seeds,
        criteria,
        bootstrap_resamples=bootstrap_resamples,
        bootstrap_seed=20260801,
    )
    boundary = search_reliability_boundary(
        baseline,
        outage_levels,
        seeds,
        fault_start_s=args.fault_start_s,
        max_bias_m=args.max_bias_m,
        tolerance_m=args.boundary_tolerance_m,
        max_iterations=max_iterations,
        criteria=criteria,
        requirement=ReliabilityRequirement(max_divergence_rate=0.0),
    )
    report = StudyReport(
        title="VeraNav Structured GNSS Degradation Reliability Study",
        comparison_name=(
            f"bias={args.comparison_bias_m:.3f} m, "
            f"outage={args.comparison_outage_s:.3f} s"
        ),
        comparison=comparison,
        boundary=boundary,
    )
    paths = write_study_report(report, args.output_dir)
    print(f"paired_rmse_difference_m={comparison.rmse_difference_interval_m.estimate:.6f}")
    print(f"baseline_failure_rate={comparison.baseline_failure_rate:.6f}")
    print(f"degraded_failure_rate={comparison.degraded_failure_rate:.6f}")
    print(f"boundary_midpoints_m={boundary.midpoint_boundary_m()}")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
