from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .geodesy import geodetic_to_ecef, geodetic_to_local_ned
from .trajectory import PositionTrajectory, evaluate_position_trajectory

FloatArray = NDArray[np.float64]
GPS_WEEK_SECONDS = 604800.0
DEFAULT_DUPLICATE_RADIUS_LIMIT_M = 5.0


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_nav_file(path: Path, label: str) -> FloatArray:
    if not path.is_file():
        raise FileNotFoundError(path)
    data = np.loadtxt(path, dtype=np.float64, usecols=(0, 1, 2, 3, 4), ndmin=2)
    if data.ndim != 2 or data.shape[1] != 5 or data.shape[0] < 2:
        raise ValueError(f"{label} must contain at least two navigation rows")
    if not np.all(np.isfinite(data)):
        raise ValueError(f"{label} contains non-finite values")
    weeks = data[:, 0]
    seconds_of_week = data[:, 1]
    latitude = data[:, 2]
    longitude = data[:, 3]
    if not np.all(np.abs(weeks - np.rint(weeks)) <= 1.0e-9):
        raise ValueError(f"{label} GPS week values must be integers")
    if np.any((seconds_of_week < 0.0) | (seconds_of_week >= GPS_WEEK_SECONDS)):
        raise ValueError(f"{label} contains invalid GPS seconds-of-week")
    if np.any((latitude < -90.0) | (latitude > 90.0)):
        raise ValueError(f"{label} contains invalid latitude")
    if np.any((longitude < -180.0) | (longitude > 180.0)):
        raise ValueError(f"{label} contains invalid longitude")
    return data


def normalize_kf_gins_time_axes(
    estimate: FloatArray,
    reference: FloatArray,
) -> tuple[FloatArray, FloatArray, dict[str, Any]]:
    """Normalize KF-GINS GPS week/SOW timestamps under explicit safe rules."""
    estimate_weeks = np.unique(np.rint(estimate[:, 0]).astype(np.int64))
    reference_weeks = np.unique(np.rint(reference[:, 0]).astype(np.int64))
    estimate_sow = estimate[:, 1]
    reference_sow = reference[:, 1]

    overlap_start = max(float(np.min(estimate_sow)), float(np.min(reference_sow)))
    overlap_end = min(float(np.max(estimate_sow)), float(np.max(reference_sow)))
    overlap_duration = overlap_end - overlap_start

    if (
        estimate_weeks.size == 1
        and int(estimate_weeks[0]) == 0
        and reference_weeks.size == 1
        and int(reference_weeks[0]) > 0
        and overlap_duration >= 0.0
    ):
        effective_estimate_week = int(reference_weeks[0])
        policy = "infer-zero-estimate-week-from-reference"
    elif (
        estimate_weeks.size == 1
        and reference_weeks.size == 1
        and int(estimate_weeks[0]) == int(reference_weeks[0])
    ):
        effective_estimate_week = int(estimate_weeks[0])
        policy = "gps-weeks-already-consistent"
    else:
        raise ValueError(
            "GPS week normalization is not safe: "
            f"estimate_weeks={estimate_weeks.tolist()}, "
            f"reference_weeks={reference_weeks.tolist()}, "
            f"sow_overlap_duration_s={overlap_duration:.9f}"
        )

    reference_week = int(reference_weeks[0])
    estimate_time = (
        (effective_estimate_week - reference_week) * GPS_WEEK_SECONDS + estimate_sow
    )
    reference_time = (
        (np.rint(reference[:, 0]).astype(np.int64) - reference_week)
        * GPS_WEEK_SECONDS
        + reference_sow
    )

    if np.any(np.diff(estimate_time) <= 0.0):
        index = int(np.flatnonzero(np.diff(estimate_time) <= 0.0)[0])
        raise ValueError(
            "estimate timestamps must be strictly increasing at rows "
            f"{index} and {index + 1}"
        )
    if np.any(np.diff(reference_time) < 0.0):
        index = int(np.flatnonzero(np.diff(reference_time) < 0.0)[0])
        raise ValueError(
            "reference timestamps decrease at rows "
            f"{index} and {index + 1}"
        )

    diagnostics: dict[str, Any] = {
        "policy": policy,
        "estimate_original_week": int(estimate_weeks[0]),
        "estimate_effective_week": effective_estimate_week,
        "reference_week": reference_week,
        "sow_overlap_start_s": overlap_start,
        "sow_overlap_end_s": overlap_end,
        "sow_overlap_duration_s": overlap_duration,
        "absolute_gps_time_offset_s": float(reference_week * GPS_WEEK_SECONDS),
    }
    return estimate_time, reference_time, diagnostics


def consolidate_reference_timestamps(
    timestamps_s: FloatArray,
    geodetic_deg_m: FloatArray,
    radius_limit_m: float = DEFAULT_DUPLICATE_RADIUS_LIMIT_M,
) -> tuple[FloatArray, FloatArray, dict[str, Any]]:
    """Consolidate only consecutive equal reference timestamps with diagnostics."""
    if timestamps_s.ndim != 1 or timestamps_s.size < 2:
        raise ValueError("timestamps_s must be one-dimensional with at least two rows")
    if geodetic_deg_m.shape != (timestamps_s.size, 3):
        raise ValueError("geodetic_deg_m must have shape (n, 3)")
    if not math.isfinite(radius_limit_m) or radius_limit_m <= 0.0:
        raise ValueError("radius_limit_m must be finite and positive")

    differences = np.diff(timestamps_s)
    if np.any(differences < 0.0):
        index = int(np.flatnonzero(differences < 0.0)[0])
        raise ValueError(
            f"reference timestamps decrease at rows {index} and {index + 1}"
        )

    starts = np.concatenate(
        (
            np.array([0], dtype=np.int64),
            np.flatnonzero(differences != 0.0).astype(np.int64) + 1,
        )
    )
    counts = np.diff(
        np.concatenate((starts, np.array([timestamps_s.size], dtype=np.int64)))
    )
    unique_time = timestamps_s[starts]
    latitude = geodetic_deg_m[:, 0]
    longitude = geodetic_deg_m[:, 1]
    height = geodetic_deg_m[:, 2]

    consolidated_latitude = np.add.reduceat(latitude, starts) / counts
    consolidated_height = np.add.reduceat(height, starts) / counts
    longitude_rad = np.deg2rad(longitude)
    mean_sine = np.add.reduceat(np.sin(longitude_rad), starts) / counts
    mean_cosine = np.add.reduceat(np.cos(longitude_rad), starts) / counts
    consolidated_longitude = np.rad2deg(np.arctan2(mean_sine, mean_cosine))
    consolidated = np.column_stack(
        (consolidated_latitude, consolidated_longitude, consolidated_height)
    )

    duplicate_groups = np.flatnonzero(counts > 1)
    maximum_radius = 0.0
    for group_index in duplicate_groups:
        start = int(starts[group_index])
        stop = start + int(counts[group_index])
        group_ecef = geodetic_to_ecef(
            latitude[start:stop], longitude[start:stop], height[start:stop]
        )
        centroid = np.mean(group_ecef, axis=0)
        radius = float(np.max(np.linalg.norm(group_ecef - centroid, axis=1)))
        maximum_radius = max(maximum_radius, radius)

    if maximum_radius > radius_limit_m:
        raise ValueError(
            "reference duplicate timestamp group exceeds spatial radius limit: "
            f"{maximum_radius:.9f} m"
        )

    diagnostics: dict[str, Any] = {
        "policy": "mean-geodetic-with-circular-longitude",
        "raw_rows": int(timestamps_s.size),
        "unique_timestamps": int(unique_time.size),
        "duplicate_rows": int(timestamps_s.size - unique_time.size),
        "duplicate_groups": int(duplicate_groups.size),
        "maximum_group_size": int(np.max(counts)),
        "maximum_duplicate_position_radius_m": maximum_radius,
        "radius_limit_m": float(radius_limit_m),
    }
    return unique_time, consolidated, diagnostics


def evaluate_kf_gins_files(
    estimate_file: Path,
    reference_file: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    estimate = _load_nav_file(estimate_file, "estimate")
    reference = _load_nav_file(reference_file, "reference")
    estimate_time, reference_time_raw, time_diagnostics = normalize_kf_gins_time_axes(
        estimate, reference
    )
    reference_time, reference_geodetic, duplicate_diagnostics = (
        consolidate_reference_timestamps(reference_time_raw, reference[:, 2:5])
    )

    overlap_start = max(float(estimate_time[0]), float(reference_time[0]))
    overlap_end = min(float(estimate_time[-1]), float(reference_time[-1]))
    if overlap_end <= overlap_start:
        raise ValueError("normalized estimate and reference trajectories do not overlap")
    overlap_mask = (reference_time >= overlap_start) & (reference_time <= overlap_end)
    if int(np.count_nonzero(overlap_mask)) < 2:
        raise ValueError("trajectory overlap contains fewer than two reference samples")

    anchor_geodetic = reference_geodetic[overlap_mask][0]
    anchor_latitude = float(anchor_geodetic[0])
    anchor_longitude = float(anchor_geodetic[1])
    anchor_height = float(anchor_geodetic[2])

    estimate_ned = geodetic_to_local_ned(
        estimate[:, 2:5], anchor_latitude, anchor_longitude, anchor_height
    )
    reference_ned = geodetic_to_local_ned(
        reference_geodetic, anchor_latitude, anchor_longitude, anchor_height
    )
    estimate_trajectory = PositionTrajectory(
        timestamps_s=estimate_time,
        positions_n_m=estimate_ned,
        source_name="KF-GINS estimate",
    )
    reference_trajectory = PositionTrajectory(
        timestamps_s=reference_time,
        positions_n_m=reference_ned,
        source_name="KF-GINS truth",
    )
    evaluation = evaluate_position_trajectory(reference_trajectory, estimate_trajectory)
    errors = evaluation.errors_n_m
    norms = np.linalg.norm(errors, axis=1)
    component_rmse = np.sqrt(np.mean(errors * errors, axis=0))
    component_mean = np.mean(errors, axis=0)
    component_maximum_absolute = np.max(np.abs(errors), axis=0)

    metrics: dict[str, Any] = {
        "sample_count": int(evaluation.metrics.sample_count),
        "start_time_s": float(evaluation.metrics.start_time_s),
        "end_time_s": float(evaluation.metrics.end_time_s),
        "duration_s": float(
            evaluation.metrics.end_time_s - evaluation.metrics.start_time_s
        ),
        "position_rmse_3d_m": float(evaluation.metrics.position_rmse_m),
        "position_mean_3d_m": float(evaluation.metrics.position_mean_m),
        "position_median_3d_m": float(np.median(norms)),
        "position_p95_3d_m": float(np.percentile(norms, 95.0)),
        "position_maximum_3d_m": float(evaluation.metrics.position_max_m),
        "north_rmse_m": float(component_rmse[0]),
        "east_rmse_m": float(component_rmse[1]),
        "down_rmse_m": float(component_rmse[2]),
        "north_mean_m": float(component_mean[0]),
        "east_mean_m": float(component_mean[1]),
        "down_mean_m": float(component_mean[2]),
        "north_maximum_absolute_m": float(component_maximum_absolute[0]),
        "east_maximum_absolute_m": float(component_maximum_absolute[1]),
        "down_maximum_absolute_m": float(component_maximum_absolute[2]),
    }
    evaluation_info: dict[str, Any] = {
        "anchor": {
            "latitude_deg": anchor_latitude,
            "longitude_deg": anchor_longitude,
            "height_m": anchor_height,
        },
        "time_normalization": time_diagnostics,
        "reference_timestamp_normalization": duplicate_diagnostics,
    }
    return evaluation_info, metrics


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_kf_gins_reproduction(
    estimate_file: Path,
    reference_file: Path,
    imu_file: Path,
    gnss_file: Path,
    config_file: Path,
    output_dir: Path,
    upstream_commit: str,
    source_archive_sha256: str,
) -> dict[str, Path]:
    """Evaluate official KF-GINS output and write compact deterministic evidence."""
    paths = {
        "estimate": Path(estimate_file),
        "reference": Path(reference_file),
        "imu": Path(imu_file),
        "gnss": Path(gnss_file),
        "config": Path(config_file),
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    commit = str(upstream_commit).strip()
    archive_hash = str(source_archive_sha256).strip().lower()
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ValueError("upstream_commit must be a lowercase 40-character SHA-1")
    if len(archive_hash) != 64 or any(
        character not in "0123456789abcdef" for character in archive_hash
    ):
        raise ValueError("source_archive_sha256 must be a lowercase SHA-256")

    evaluation_info, metrics = evaluate_kf_gins_files(
        paths["estimate"], paths["reference"]
    )
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "estimator": "KF-GINS",
        "upstream_repository": "https://github.com/i2Nav-WHU/KF-GINS",
        "upstream_commit": commit,
        "source_archive_sha256": archive_hash,
        "sources": {
            name: {
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
            for name, path in sorted(paths.items())
        },
        "time_normalization": evaluation_info["time_normalization"],
        "reference_timestamp_normalization": evaluation_info[
            "reference_timestamp_normalization"
        ],
        "evaluation_anchor": evaluation_info["anchor"],
    }

    manifest_path = output / "manifest.json"
    metrics_path = output / "metrics.json"
    csv_path = output / "metrics.csv"
    report_path = output / "report.md"
    _write_json(manifest_path, manifest)
    _write_json(metrics_path, metrics)

    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("metric", "value"))
        for name in sorted(metrics):
            writer.writerow((name, metrics[name]))

    report_path.write_text(
        "\n".join(
            (
                "# KF-GINS official demo reproduction",
                "",
                f"- Upstream commit: `{commit}`",
                f"- Evaluation samples: {metrics['sample_count']}",
                f"- Evaluation duration: {metrics['duration_s']:.6f} s",
                f"- 3D position RMSE: {metrics['position_rmse_3d_m']:.6f} m",
                f"- Mean 3D position error: {metrics['position_mean_3d_m']:.6f} m",
                f"- 95th percentile 3D error: {metrics['position_p95_3d_m']:.6f} m",
                f"- Maximum 3D position error: {metrics['position_maximum_3d_m']:.6f} m",
                "",
                "The official result stores GPS week as zero. VeraNav infers the unique nonzero reference week only when both trajectories have a valid seconds-of-week overlap. Consecutive duplicate truth timestamps are consolidated with an audited spatial-radius limit.",
                "",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    return {
        "manifest": manifest_path,
        "metrics": metrics_path,
        "csv": csv_path,
        "report": report_path,
    }
