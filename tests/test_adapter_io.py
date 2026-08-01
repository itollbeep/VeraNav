"""Tests for the common trajectory CSV schema."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from veranav.adapter_io import (
    COMMON_TRAJECTORY_COLUMNS,
    read_position_trajectory_csv,
    write_position_trajectory_csv,
)
from veranav.trajectory import PositionTrajectory


class AdapterIoTest(unittest.TestCase):
    def trajectory(self) -> PositionTrajectory:
        return PositionTrajectory(
            [0.0, 0.1, 0.2],
            [[1.0, 2.0, 3.0], [1.1, 2.1, 3.1], [1.2, 2.2, 3.2]],
            "source",
        )

    def test_round_trip_and_exact_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.csv"
            write_position_trajectory_csv(self.trajectory(), path)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], ",".join(COMMON_TRAJECTORY_COLUMNS))
            restored = read_position_trajectory_csv(path, source_name="restored")
            np.testing.assert_array_equal(restored.timestamps_s, self.trajectory().timestamps_s)
            np.testing.assert_array_equal(restored.positions_n_m, self.trajectory().positions_n_m)
            self.assertEqual(restored.source_name, "restored")

    def test_repeated_write_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.csv"
            second = Path(directory) / "second.csv"
            write_position_trajectory_csv(self.trajectory(), first)
            write_position_trajectory_csv(self.trajectory(), second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_writer_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "trajectory.csv"
            self.assertEqual(write_position_trajectory_csv(self.trajectory(), path), path)
            self.assertTrue(path.is_file())

    def test_rejects_wrong_header_and_too_few_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrong = root / "wrong.csv"
            wrong.write_text("time,n,e,d\n0,0,0,0\n1,0,0,0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "header"):
                read_position_trajectory_csv(wrong)
            short = root / "short.csv"
            short.write_text(
                "timestamp_s,north_m,east_m,down_m\n0,0,0,0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "at least two"):
                read_position_trajectory_csv(short)

    def test_rejects_non_numeric_and_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.csv"
            invalid.write_text(
                "timestamp_s,north_m,east_m,down_m\n0,0,0,0\n1,bad,0,0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "row 3"):
                read_position_trajectory_csv(invalid)
            with self.assertRaises(ValueError):
                read_position_trajectory_csv(Path(directory) / "missing.csv")

    def test_rejects_invalid_trajectory_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TypeError):
                write_position_trajectory_csv("bad", Path(directory) / "x.csv")


if __name__ == "__main__":
    unittest.main()
