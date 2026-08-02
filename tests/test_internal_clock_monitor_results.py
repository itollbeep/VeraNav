"""Tests for V2-E03 internal clock monitor result model."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from veranav.internal_clock_monitor_results import (
    load_internal_clock_monitor_results,
)


PARENT = "52da5a0f8014e35911befd4db7c4fae7f762c061"
PREREG = "6a9573b7b8406d092f0ee48b6cf7655b63290497"


class InternalClockMonitorResultsTest(unittest.TestCase):
    def write(
        self,
        root: Path,
        status: str = "monitor_supported",
        scenario_count: int = 30,
        threshold_count: int = 3,
    ) -> tuple[Path, Path, Path, Path]:
        progress = (
            {
                "v1_overall_percent": 100.0,
                "v2_stage_4_percent": 40,
                "v2_overall_percent": 65.0,
            }
            if status == "monitor_supported"
            else {
                "v1_overall_percent": 100.0,
                "v2_stage_4_percent": 0,
                "v2_overall_percent": 55.0,
            }
        )
        results = {
            "dynamic_secondary_detected_count": 20,
            "early_warning_positive_detected_count": 2,
            "early_warning_positive_positive_lead_count": 2,
            "experiment": "openvins-internal-clock-monitor-pilot",
            "monitor_status": status,
            "parent_commit": PARENT,
            "preregistration_commit": PREREG,
            "progress": progress,
            "scenario_count": 30,
            "schema_version": 1,
            "static_false_positive_count": 0,
        }
        manifest = {
            "experiment": "openvins-internal-clock-monitor-pilot",
            "new_estimator_execution": False,
            "official_source_modified": False,
            "online_ground_truth_input_count": 0,
            "parent_evidence_modified": False,
            "preregistration_modified": False,
            "schema_version": 1,
            "source_inputs": {"results_sha256": "a" * 64},
            "verification": {
                "deterministic_evidence_verified": True,
                "importer_deterministic": True,
                "monitor_input_boundary_verified": True,
                "preregistration_preceded_analysis": True,
                "static_only_threshold_calibration_verified": True,
            },
        }
        results_path = root / "results.json"
        manifest_path = root / "manifest.json"
        scenario_path = root / "scenarios.csv"
        threshold_path = root / "thresholds.csv"
        results_path.write_text(json.dumps(results))
        manifest_path.write_text(json.dumps(manifest))
        with scenario_path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["scenario_id"])
            writer.writeheader()
            for index in range(scenario_count):
                writer.writerow({"scenario_id": str(index)})
        with threshold_path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["channel"])
            writer.writeheader()
            for index in range(threshold_count):
                writer.writerow({"channel": str(index)})
        return results_path, manifest_path, scenario_path, threshold_path

    def test_loads_supported_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = load_internal_clock_monitor_results(
                *self.write(Path(directory))
            )
        self.assertEqual(result.status, "monitor_supported")
        self.assertEqual(result.v2_overall_percent, 65.0)

    def test_loads_not_supported_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = load_internal_clock_monitor_results(
                *self.write(Path(directory), status="monitor_not_supported")
            )
        self.assertEqual(result.v2_stage_4_percent, 0)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_internal_clock_monitor_results(
                "/missing/a",
                "/missing/b",
                "/missing/c",
                "/missing/d",
            )

    def test_rejects_wrong_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory))
            payload = json.loads(paths[0].read_text())
            payload["schema_version"] = 2
            paths[0].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_results(*paths)

    def test_rejects_ground_truth_online_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory))
            payload = json.loads(paths[1].read_text())
            payload["online_ground_truth_input_count"] = 1
            paths[1].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_results(*paths)

    def test_rejects_estimator_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory))
            payload = json.loads(paths[1].read_text())
            payload["new_estimator_execution"] = True
            paths[1].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_results(*paths)

    def test_rejects_parent_modification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory))
            payload = json.loads(paths[1].read_text())
            payload["parent_evidence_modified"] = True
            paths[1].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_results(*paths)

    def test_rejects_wrong_scenario_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory), scenario_count=29)
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_results(*paths)

    def test_rejects_wrong_threshold_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory), threshold_count=2)
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_results(*paths)

    def test_rejects_supported_progress_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory))
            payload = json.loads(paths[0].read_text())
            payload["progress"]["v2_overall_percent"] = 55.0
            paths[0].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_results(*paths)


if __name__ == "__main__":
    unittest.main()
