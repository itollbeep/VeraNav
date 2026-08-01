#!/usr/bin/env python3
"""Run a small deterministic VeraNav GNSS reliability-envelope demo."""

from __future__ import annotations

import argparse

from veranav.experiment import ExperimentConfig
from veranav.monte_carlo import FailureCriteria
from veranav.reliability import evaluate_reliability_envelope
from veranav.simulation import CircularTrajectoryConfig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=5)
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds must be at least one")

    config = ExperimentConfig(
        trajectory=CircularTrajectoryConfig(duration_s=6.0, imu_dt=0.05, gnss_dt=0.25)
    )
    envelope = evaluate_reliability_envelope(
        config,
        bias_magnitudes_m=[0.0, 2.0, 5.0, 10.0],
        outage_durations_s=[0.0, 1.0, 2.0, 4.0],
        seeds=range(args.seeds),
        fault_start_s=1.0,
        criteria=FailureCriteria(max_position_rmse_m=5.0, max_position_error_m=15.0),
    )

    print("outage_s,bias_m,divergence_rate,reliable")
    for cell in envelope.cells:
        print(
            f"{cell.outage_duration_s:.3f},"
            f"{cell.bias_magnitude_m:.3f},"
            f"{cell.summary.divergence_rate:.6f},"
            f"{str(cell.reliable).lower()}"
        )
    print("maximum_reliable_bias_by_outage:", envelope.maximum_reliable_bias_by_outage())


if __name__ == "__main__":
    main()
