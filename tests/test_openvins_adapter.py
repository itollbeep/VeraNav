"""Tests for committed OpenVINS adapter records."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from veranav.openvins_adapter import (
    OpenVinsSimulationRecord,
    load_openvins_simulation_record,
)


COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"


class OpenVinsSimulationRecordTest(unittest.TestCase):
    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "adapter_build": {
                "binary_sha256": digest,
                "cmake_sha256": digest,
                "source_sha256": digest,
            },
            "adapter_source_location": "external-only",
            "configuration_sha256": digest,
            "estimator": "OpenVINS",
            "frame_convention": {
                "mapping": "OpenVINS global x/y/z to VeraNav N/E/D",
                "reason": "positive global z gravity",
            },
            "integration_scope": (
                "v2.7-ros-free-simulation-position-adapter"
            ),
            "official_reproduction_manifest_sha256": digest,
            "official_source_modified": False,
            "outputs": {
                "estimate_sha256": digest,
                "reference_sha256": digest,
            },
            "release_tag": "v2.7",
            "schema_version": 1,
            "upstream_commit": COMMIT,
            "verification": {
                "frame_mapping": (
                    "openvins-global-xyz-to-veranav-ned"
                ),
                "output_schema": "veranav-position-trajectory-v1",
                "run_a": {"log_sha256": digest, "status": "PASS"},
                "run_b": {"log_sha256": digest, "status": "PASS"},
                "trajectory_outputs_byte_identical": True,
            },
        }
        metrics = {
            "estimator": "OpenVINS",
            "metrics": {
                "end_time_s": 3.0,
                "position_max_m": 0.4,
                "position_mean_m": 0.2,
                "position_rmse_m": 0.25,
                "sample_count": 3,
                "start_time_s": 1.0,
            },
            "schema_version": 1,
        }
        return manifest, metrics

    def write(self, root: Path) -> tuple[Path, Path]:
        manifest, metrics = self.payloads()
        manifest_path = root / "manifest.json"
        metrics_path = root / "metrics.json"
        manifest_path.write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        metrics_path.write_text(
            json.dumps(metrics),
            encoding="utf-8",
        )
        return manifest_path, metrics_path

    def test_loads_valid_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory))
            record = load_openvins_simulation_record(*paths)
        self.assertEqual(record.upstream_commit, COMMIT)
        self.assertEqual(record.sample_count, 3)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_openvins_simulation_record(
                "/missing/manifest.json",
                "/missing/metrics.json",
            )

    def test_rejects_schema(self) -> None:
        manifest, metrics = self.payloads()
        manifest["schema_version"] = 2
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "metrics.json").write_text(json.dumps(metrics))
            with self.assertRaises(ValueError):
                load_openvins_simulation_record(
                    root / "manifest.json",
                    root / "metrics.json",
                )

    def test_rejects_wrong_commit(self) -> None:
        manifest, metrics = self.payloads()
        manifest["upstream_commit"] = "b" * 40
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "metrics.json").write_text(json.dumps(metrics))
            with self.assertRaises(ValueError):
                load_openvins_simulation_record(
                    root / "manifest.json",
                    root / "metrics.json",
                )

    def test_rejects_failed_run(self) -> None:
        manifest, metrics = self.payloads()
        manifest["verification"]["run_b"]["status"] = "FAIL"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "metrics.json").write_text(json.dumps(metrics))
            with self.assertRaises(ValueError):
                load_openvins_simulation_record(
                    root / "manifest.json",
                    root / "metrics.json",
                )

    def test_rejects_invalid_metric(self) -> None:
        with self.assertRaises(ValueError):
            OpenVinsSimulationRecord(
                upstream_commit=COMMIT,
                sample_count=3,
                start_time_s=1.0,
                end_time_s=3.0,
                position_rmse_m=-1.0,
                position_mean_m=0.2,
                position_max_m=0.4,
                estimate_sha256="a" * 64,
                reference_sha256="a" * 64,
                adapter_binary_sha256="a" * 64,
            )

    def test_rejects_source_modification(self) -> None:
        manifest, metrics = self.payloads()
        manifest["official_source_modified"] = True
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "metrics.json").write_text(json.dumps(metrics))
            with self.assertRaises(ValueError):
                load_openvins_simulation_record(
                    root / "manifest.json",
                    root / "metrics.json",
                )


if __name__ == "__main__":
    unittest.main()
