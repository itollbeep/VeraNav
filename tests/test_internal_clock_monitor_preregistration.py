"""Tests for the V2-E03 internal clock monitor preregistration."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from veranav.internal_clock_monitor_preregistration import (
    load_internal_clock_monitor_preregistration,
)


COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
PARENT = "52da5a0f8014e35911befd4db7c4fae7f762c061"


class InternalClockMonitorPreregistrationTest(unittest.TestCase):
    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "analysis_only": True,
            "experiment": "openvins-internal-clock-monitor-pilot",
            "new_estimator_execution": False,
            "official_source_modified": False,
            "schema_version": 1,
            "source_inputs": {
                "audit_json_sha256": digest,
                "audit_text_sha256": digest,
                "config_sha256": digest,
            },
            "upstream_commit": COMMIT,
            "verification": {
                "audit_hashes_verified": True,
                "generated_twice_byte_identical": True,
                "parent_evidence_verified": True,
                "progress_unchanged": True,
            },
        }
        prereg = {
            "monitor": {
                "alert_channel_count": 2,
                "alert_persistence_s": 1.0,
                "channels": [
                    "estimated_offset_velocity_rms",
                    "estimated_offset_acceleration_rms",
                    "estimated_offset_peak_to_peak",
                ],
                "monitor_window_s": 5.0,
                "warmup_s": 10.0,
            },
            "parent_evidence": {"commit": PARENT},
            "progress": {
                "v1_overall_percent": 100.0,
                "v2_overall_percent": 55.0,
                "v2_stage_4_percent": 0,
            },
            "schema_version": 1,
        }
        return manifest, prereg

    def write(
        self,
        root: Path,
        static_count: int = 6,
        positive_count: int = 2,
        dynamic_count: int = 22,
    ) -> tuple[Path, Path, Path]:
        manifest, prereg = self.payloads()
        manifest_path = root / "manifest.json"
        prereg_path = root / "preregistration.json"
        labels_path = root / "scenario_labels.csv"

        manifest_path.write_text(json.dumps(manifest))
        prereg_path.write_text(json.dumps(prereg))

        rows = []
        for index in range(static_count):
            rows.append(
                {
                    "scenario_id": f"static-{index}",
                    "label": "static-negative",
                }
            )
        positives = [
            "sinusoidalslow-span05-drop00",
            "sinusoidalslow-span05-drop10",
        ]
        for scenario_id in positives[:positive_count]:
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "label": "early-warning-positive",
                }
            )
        for index in range(dynamic_count):
            rows.append(
                {
                    "scenario_id": f"dynamic-{index}",
                    "label": "dynamic-secondary",
                }
            )

        with labels_path.open("w", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["scenario_id", "label"],
            )
            writer.writeheader()
            writer.writerows(rows)

        return manifest_path, prereg_path, labels_path

    def test_loads_valid_preregistration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prereg = load_internal_clock_monitor_preregistration(
                *self.write(Path(directory))
            )
        self.assertEqual(prereg.scenario_count, 30)
        self.assertEqual(prereg.early_warning_positive_count, 2)
        self.assertEqual(prereg.v2_overall_percent, 55.0)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_internal_clock_monitor_preregistration(
                "/missing/a",
                "/missing/b",
                "/missing/c",
            )

    def test_rejects_wrong_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["schema_version"] = 2
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_preregistration(*paths)

    def test_rejects_estimator_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["new_estimator_execution"] = True
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_preregistration(*paths)

    def test_rejects_source_modification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["official_source_modified"] = True
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_preregistration(*paths)

    def test_rejects_failed_parent_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["verification"]["parent_evidence_verified"] = False
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_preregistration(*paths)

    def test_rejects_wrong_parent_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            prereg = json.loads(paths[1].read_text())
            prereg["parent_evidence"]["commit"] = "0" * 40
            paths[1].write_text(json.dumps(prereg))
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_preregistration(*paths)

    def test_rejects_wrong_label_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root, dynamic_count=21)
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_preregistration(*paths)

    def test_rejects_wrong_positive_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            with paths[2].open("r", encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            rows[6]["scenario_id"] = "wrong-positive"
            with paths[2].open("w", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=["scenario_id", "label"],
                )
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_preregistration(*paths)

    def test_rejects_progress_advance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            prereg = json.loads(paths[1].read_text())
            prereg["progress"]["v2_stage_4_percent"] = 10
            paths[1].write_text(json.dumps(prereg))
            with self.assertRaises(ValueError):
                load_internal_clock_monitor_preregistration(*paths)


if __name__ == "__main__":
    unittest.main()
