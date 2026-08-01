#!/usr/bin/env python3
"""Run the internal ESKF through the common adapter protocol."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from veranav.adapter import run_internal_eskf_adapter
from veranav.adapter_io import (
    read_position_trajectory_csv,
    write_position_trajectory_csv,
)
from veranav.experiment import ExperimentConfig
from veranav.simulation import CircularTrajectoryConfig
from veranav.trajectory import evaluate_position_trajectory


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    config = ExperimentConfig(
        trajectory=CircularTrajectoryConfig(
            duration_s=2.0,
            imu_dt=0.02,
            gnss_dt=0.2,
        )
    )
    adapter_run = run_internal_eskf_adapter(config, arguments.seed)
    output_dir = arguments.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    estimate_path = write_position_trajectory_csv(
        adapter_run.estimate,
        output_dir / "estimate.csv",
    )
    reference_path = write_position_trajectory_csv(
        adapter_run.reference,
        output_dir / "reference.csv",
    )
    estimate = read_position_trajectory_csv(estimate_path, source_name="estimate")
    reference = read_position_trajectory_csv(reference_path, source_name="reference")
    evaluation = evaluate_position_trajectory(reference, estimate)
    summary = {
        "schema_version": 1,
        "adapter": adapter_run.estimator_name,
        "seed": arguments.seed,
        "sample_count": evaluation.metrics.sample_count,
        "position_rmse_m": evaluation.metrics.position_rmse_m,
        "position_max_m": evaluation.metrics.position_max_m,
        "estimate_csv": estimate_path.name,
        "reference_csv": reference_path.name,
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"adapter={summary['adapter']}")
    print(f"sample_count={summary['sample_count']}")
    print(f"position_rmse_m={summary['position_rmse_m']:.6f}")
    print(f"position_max_m={summary['position_max_m']:.6f}")
    print(summary_path)


if __name__ == "__main__":
    main()
