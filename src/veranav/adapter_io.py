"""Deterministic I/O for the VeraNav common trajectory schema."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from veranav.trajectory import PositionTrajectory

COMMON_TRAJECTORY_COLUMNS = (
    "timestamp_s",
    "north_m",
    "east_m",
    "down_m",
)


def _path(value: str | Path, name: str) -> Path:
    path = Path(value)
    if not str(path):
        raise ValueError(f"{name} must not be empty")
    return path


def write_position_trajectory_csv(
    trajectory: PositionTrajectory,
    path: str | Path,
) -> Path:
    """Write the common NED position-trajectory CSV schema."""
    if not isinstance(trajectory, PositionTrajectory):
        raise TypeError("trajectory must be a PositionTrajectory")
    output = _path(path, "path")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(COMMON_TRAJECTORY_COLUMNS)
        for timestamp, position in zip(
            trajectory.timestamps_s,
            trajectory.positions_n_m,
            strict=True,
        ):
            writer.writerow(
                [
                    format(float(timestamp), ".17g"),
                    format(float(position[0]), ".17g"),
                    format(float(position[1]), ".17g"),
                    format(float(position[2]), ".17g"),
                ]
            )
    return output


def read_position_trajectory_csv(
    path: str | Path,
    *,
    source_name: str | None = None,
) -> PositionTrajectory:
    """Read and validate the common NED position-trajectory CSV schema."""
    input_path = _path(path, "path")
    if not input_path.is_file():
        raise ValueError(f"trajectory CSV does not exist: {input_path}")

    timestamps = []
    positions = []
    with input_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError("trajectory CSV is missing a header")
        if tuple(reader.fieldnames) != COMMON_TRAJECTORY_COLUMNS:
            raise ValueError(
                "trajectory CSV header must be exactly "
                + ",".join(COMMON_TRAJECTORY_COLUMNS)
            )
        for row_index, row in enumerate(reader, start=2):
            try:
                timestamps.append(float(row["timestamp_s"]))
                positions.append(
                    [
                        float(row["north_m"]),
                        float(row["east_m"]),
                        float(row["down_m"]),
                    ]
                )
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"trajectory CSV row {row_index} contains invalid numbers"
                ) from error

    if len(timestamps) < 2:
        raise ValueError("trajectory CSV must contain at least two data rows")
    name = input_path.stem if source_name is None else str(source_name)
    return PositionTrajectory(
        timestamps_s=np.asarray(timestamps, dtype=np.float64),
        positions_n_m=np.asarray(positions, dtype=np.float64),
        source_name=name,
    )


__all__ = [
    "COMMON_TRAJECTORY_COLUMNS",
    "read_position_trajectory_csv",
    "write_position_trajectory_csv",
]
