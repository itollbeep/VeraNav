#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from veranav.kf_gins import write_kf_gins_reproduction


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import and evaluate the KF-GINS official demonstration result."
    )
    parser.add_argument("--estimate", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--imu", required=True, type=Path)
    parser.add_argument("--gnss", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--upstream-commit", required=True)
    parser.add_argument("--source-archive-sha256", required=True)
    arguments = parser.parse_args()

    outputs = write_kf_gins_reproduction(
        estimate_file=arguments.estimate,
        reference_file=arguments.reference,
        imu_file=arguments.imu,
        gnss_file=arguments.gnss,
        config_file=arguments.config,
        output_dir=arguments.output_dir,
        upstream_commit=arguments.upstream_commit,
        source_archive_sha256=arguments.source_archive_sha256,
    )
    for name, path in outputs.items():
        print(f"{name}={path}")


if __name__ == "__main__":
    main()
