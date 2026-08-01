from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from veranav.kf_gins import (
    consolidate_reference_timestamps,
    evaluate_kf_gins_files,
    normalize_kf_gins_time_axes,
    write_kf_gins_reproduction,
)


class KfGinsTest(unittest.TestCase):
    def _nav(self, weeks: list[float], times: list[float]) -> np.ndarray:
        count = len(times)
        return np.column_stack(
            (
                np.asarray(weeks, dtype=np.float64),
                np.asarray(times, dtype=np.float64),
                30.0 + np.arange(count) * 1.0e-6,
                114.0 + np.arange(count) * 1.0e-6,
                20.0 + np.arange(count) * 0.01,
            )
        )

    def _write_nav(self, path: Path, data: np.ndarray) -> None:
        np.savetxt(path, data, fmt="%.12f")

    def test_zero_estimate_week_is_inferred(self) -> None:
        estimate = self._nav([0, 0, 0], [100.0, 101.0, 102.0])
        reference = self._nav([2017, 2017, 2017], [99.0, 101.0, 103.0])
        estimate_time, reference_time, diagnostics = normalize_kf_gins_time_axes(
            estimate, reference
        )
        self.assertEqual(diagnostics["policy"], "infer-zero-estimate-week-from-reference")
        self.assertEqual(diagnostics["estimate_effective_week"], 2017)
        np.testing.assert_allclose(estimate_time, estimate[:, 1])
        np.testing.assert_allclose(reference_time, reference[:, 1])

    def test_matching_week_is_preserved(self) -> None:
        estimate = self._nav([2017, 2017], [100.0, 101.0])
        reference = self._nav([2017, 2017], [100.0, 101.0])
        _, _, diagnostics = normalize_kf_gins_time_axes(estimate, reference)
        self.assertEqual(diagnostics["policy"], "gps-weeks-already-consistent")

    def test_unsafe_week_mismatch_is_rejected(self) -> None:
        estimate = self._nav([2016, 2016], [100.0, 101.0])
        reference = self._nav([2017, 2017], [100.0, 101.0])
        with self.assertRaises(ValueError):
            normalize_kf_gins_time_axes(estimate, reference)

    def test_duplicate_timestamps_are_consolidated(self) -> None:
        timestamps = np.array([1.0, 2.0, 2.0, 3.0])
        geodetic = np.array(
            [
                [30.0, 114.0, 20.0],
                [30.0, 114.0, 20.0],
                [30.0, 114.0, 20.0],
                [30.0, 114.0, 20.0],
            ]
        )
        unique, consolidated, diagnostics = consolidate_reference_timestamps(
            timestamps, geodetic
        )
        np.testing.assert_array_equal(unique, np.array([1.0, 2.0, 3.0]))
        self.assertEqual(consolidated.shape, (3, 3))
        self.assertEqual(diagnostics["duplicate_rows"], 1)
        self.assertEqual(diagnostics["duplicate_groups"], 1)
        self.assertEqual(diagnostics["maximum_group_size"], 2)

    def test_descending_reference_is_rejected(self) -> None:
        timestamps = np.array([1.0, 3.0, 2.0])
        geodetic = np.tile(np.array([[30.0, 114.0, 20.0]]), (3, 1))
        with self.assertRaises(ValueError):
            consolidate_reference_timestamps(timestamps, geodetic)

    def test_large_duplicate_spread_is_rejected(self) -> None:
        timestamps = np.array([1.0, 2.0, 2.0, 3.0])
        geodetic = np.array(
            [
                [30.0, 114.0, 20.0],
                [30.0, 114.0, 20.0],
                [30.01, 114.0, 20.0],
                [30.0, 114.0, 20.0],
            ]
        )
        with self.assertRaises(ValueError):
            consolidate_reference_timestamps(timestamps, geodetic, radius_limit_m=5.0)

    def test_end_to_end_evaluation_is_finite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            estimate = self._nav([0, 0, 0], [100.0, 101.0, 102.0])
            reference = self._nav([2017, 2017, 2017], [100.0, 101.0, 102.0])
            estimate_path = root / "estimate.nav"
            reference_path = root / "reference.nav"
            self._write_nav(estimate_path, estimate)
            self._write_nav(reference_path, reference)
            info, metrics = evaluate_kf_gins_files(estimate_path, reference_path)
            self.assertEqual(metrics["sample_count"], 3)
            self.assertGreaterEqual(metrics["position_rmse_3d_m"], 0.0)
            self.assertEqual(
                info["time_normalization"]["estimate_effective_week"], 2017
            )

    def test_writer_creates_four_deterministic_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            estimate = self._nav([0, 0, 0], [100.0, 101.0, 102.0])
            reference = self._nav([2017, 2017, 2017], [100.0, 101.0, 102.0])
            files = {}
            for name in ("estimate", "reference", "imu", "gnss", "config"):
                path = root / f"{name}.txt"
                if name == "estimate":
                    self._write_nav(path, estimate)
                elif name == "reference":
                    self._write_nav(path, reference)
                else:
                    path.write_text("test\n", encoding="utf-8")
                files[name] = path
            first = root / "first"
            second = root / "second"
            arguments = dict(
                estimate_file=files["estimate"],
                reference_file=files["reference"],
                imu_file=files["imu"],
                gnss_file=files["gnss"],
                config_file=files["config"],
                upstream_commit="a" * 40,
                source_archive_sha256="b" * 64,
            )
            first_outputs = write_kf_gins_reproduction(output_dir=first, **arguments)
            second_outputs = write_kf_gins_reproduction(output_dir=second, **arguments)
            self.assertEqual(set(first_outputs), {"manifest", "metrics", "csv", "report"})
            for name in first_outputs:
                self.assertEqual(
                    first_outputs[name].read_bytes(), second_outputs[name].read_bytes()
                )

    def test_manifest_records_source_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            estimate = self._nav([0, 0], [100.0, 101.0])
            reference = self._nav([2017, 2017], [100.0, 101.0])
            paths = {}
            for name in ("estimate", "reference", "imu", "gnss", "config"):
                path = root / name
                if name == "estimate":
                    self._write_nav(path, estimate)
                elif name == "reference":
                    self._write_nav(path, reference)
                else:
                    path.write_text(name, encoding="utf-8")
                paths[name] = path
            output = root / "output"
            write_kf_gins_reproduction(
                estimate_file=paths["estimate"],
                reference_file=paths["reference"],
                imu_file=paths["imu"],
                gnss_file=paths["gnss"],
                config_file=paths["config"],
                output_dir=output,
                upstream_commit="c" * 40,
                source_archive_sha256="d" * 64,
            )
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["upstream_commit"], "c" * 40)
            self.assertEqual(len(manifest["sources"]["estimate"]["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
