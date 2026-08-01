#!/usr/bin/env python3
"""Create a deterministic OpenVINS simulation-adapter record."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from veranav.adapter_io import read_position_trajectory_csv
from veranav.trajectory import evaluate_position_trajectory


EXPECTED_COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--estimate-a", type=Path, required=True)
    parser.add_argument("--reference-a", type=Path, required=True)
    parser.add_argument("--estimate-b", type=Path, required=True)
    parser.add_argument("--reference-b", type=Path, required=True)
    parser.add_argument("--run-log-a", type=Path, required=True)
    parser.add_argument("--run-log-b", type=Path, required=True)
    parser.add_argument("--adapter-source", type=Path, required=True)
    parser.add_argument("--adapter-cmake", type=Path, required=True)
    parser.add_argument("--adapter-binary", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--official-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--upstream-commit", required=True)
    return parser.parse_args()


def require_file(path: Path, name: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"{name} must be a nonempty file")


def main() -> int:
    args = arguments()

    if args.upstream_commit != EXPECTED_COMMIT:
        raise ValueError("unexpected OpenVINS upstream commit")

    input_paths = {
        "estimate_a": args.estimate_a,
        "reference_a": args.reference_a,
        "estimate_b": args.estimate_b,
        "reference_b": args.reference_b,
        "run_log_a": args.run_log_a,
        "run_log_b": args.run_log_b,
        "adapter_source": args.adapter_source,
        "adapter_cmake": args.adapter_cmake,
        "adapter_binary": args.adapter_binary,
        "config": args.config,
        "official_manifest": args.official_manifest,
    }
    for name, path in input_paths.items():
        require_file(path, name)

    if args.estimate_a.read_bytes() != args.estimate_b.read_bytes():
        raise ValueError("OpenVINS estimate outputs are not byte-identical")
    if args.reference_a.read_bytes() != args.reference_b.read_bytes():
        raise ValueError("OpenVINS reference outputs are not byte-identical")

    official = json.loads(
        args.official_manifest.read_text(encoding="utf-8")
    )
    if official["upstream"]["commit"] != EXPECTED_COMMIT:
        raise ValueError("official reproduction commit mismatch")
    if official["verification"]["official_source_modified"] is not False:
        raise ValueError("official source modification flag is not false")

    estimate = read_position_trajectory_csv(
        args.estimate_a,
        source_name="openvins-v2.7-estimate",
    )
    reference = read_position_trajectory_csv(
        args.reference_a,
        source_name="openvins-v2.7-reference",
    )
    evaluation = evaluate_position_trajectory(reference, estimate)
    values = evaluation.metrics

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    metrics = {
        "estimator": "OpenVINS",
        "metrics": {
            "end_time_s": values.end_time_s,
            "position_max_m": values.position_max_m,
            "position_mean_m": values.position_mean_m,
            "position_rmse_m": values.position_rmse_m,
            "sample_count": values.sample_count,
            "start_time_s": values.start_time_s,
        },
        "schema_version": 1,
    }

    manifest = {
        "adapter_build": {
            "binary_sha256": sha256(args.adapter_binary),
            "cmake_sha256": sha256(args.adapter_cmake),
            "source_sha256": sha256(args.adapter_source),
        },
        "adapter_source_location": "external-only",
        "configuration_sha256": sha256(args.config),
        "estimator": "OpenVINS",
        "frame_convention": {
            "mapping": "OpenVINS global x/y/z to VeraNav N/E/D",
            "reason": (
                "The OpenVINS simulator uses positive global z gravity; "
                "the synthetic global axes are recorded as NED."
            ),
        },
        "integration_scope": (
            "v2.7-ros-free-simulation-position-adapter"
        ),
        "official_reproduction_manifest_sha256": sha256(
            args.official_manifest
        ),
        "official_source_modified": False,
        "outputs": {
            "estimate_sha256": sha256(args.estimate_a),
            "reference_sha256": sha256(args.reference_a),
        },
        "release_tag": "v2.7",
        "schema_version": 1,
        "upstream_commit": EXPECTED_COMMIT,
        "verification": {
            "frame_mapping": (
                "openvins-global-xyz-to-veranav-ned"
            ),
            "output_schema": "veranav-position-trajectory-v1",
            "run_a": {
                "log_sha256": sha256(args.run_log_a),
                "status": "PASS",
            },
            "run_b": {
                "log_sha256": sha256(args.run_log_b),
                "status": "PASS",
            },
            "trajectory_outputs_byte_identical": True,
        },
    }

    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    readme = f"""# OpenVINS v2.7 simulation adapter baseline

- Upstream commit: `{EXPECTED_COMMIT}`
- Common aligned samples: `{values.sample_count}`
- Position RMSE: `{values.position_rmse_m:.9f} m`
- Position mean error: `{values.position_mean_m:.9f} m`
- Position maximum error: `{values.position_max_m:.9f} m`
- Deterministic estimate and reference CSV outputs: `PASS`
- Official OpenVINS source modified: `false`
- GPL-linked C++ adapter source location: external only

The adapter mirrors the official ROS-free simulation loop and records
the public OpenVINS state together with simulator ground truth. The
synthetic OpenVINS global x/y/z coordinates are mapped to VeraNav
north/east/down because the simulator uses positive global z gravity.
"""
    (output / "README.md").write_text(
        readme,
        encoding="utf-8",
        newline="\n",
    )

    print(f"sample_count={values.sample_count}")
    print(f"position_rmse_m={values.position_rmse_m:.9f}")
    print(f"position_mean_m={values.position_mean_m:.9f}")
    print(f"position_max_m={values.position_max_m:.9f}")
    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
