"""Tests for the V2-E02 dynamic clock drift preregistration."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from veranav.dynamic_clock_drift_preregistration import (
    load_dynamic_clock_drift_preregistration,
)


COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
PARENT = "92ba1942801f1c8dcfbb0fe71225712e334e70d5"


class DynamicClockDriftPreregistrationTest(unittest.TestCase):
    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "analysis_only": True,
            "experiment": "openvins-dynamic-clock-drift-pilot",
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
            "design": {
                "drift_spans_ms": [5.0, 10.0, 20.0],
                "dynamic_profiles": [
                    "linear-positive",
                    "linear-negative",
                    "sinusoidal-slow",
                    "piecewise-random-walk",
                ],
                "estimator_execution_count": 60,
                "repeat_count_per_scenario": 2,
                "scenario_count": 30,
                "static_controls_ms": [-10.0, 0.0, 10.0],
                "visual_dropout_fractions": [0.0, 0.1],
            },
            "parent_evidence": {
                "commit": PARENT,
            },
            "progress": {
                "v1_overall_percent": 100.0,
                "v2_overall_percent": 35.0,
                "v2_stage_3_percent": 0,
            },
            "schema_version": 1,
        }
        return manifest, prereg

    def write(
        self,
        root: Path,
        scenario_count: int = 30,
        execution_count: int = 60,
    ) -> tuple[Path, Path, Path]:
        manifest, prereg = self.payloads()
        manifest_path = root / "manifest.json"
        prereg_path = root / "preregistration.json"
        plan_path = root / "scenario_plan.csv"

        manifest_path.write_text(json.dumps(manifest))
        prereg_path.write_text(json.dumps(prereg))

        repeats = [2] * scenario_count
        if scenario_count > 0:
            repeats[0] += execution_count - sum(repeats)

        with plan_path.open("w", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["repeat_count"],
            )
            writer.writeheader()
            for repeat in repeats:
                writer.writerow({"repeat_count": repeat})

        return manifest_path, prereg_path, plan_path

    def test_loads_valid_preregistration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prereg = load_dynamic_clock_drift_preregistration(
                *self.write(Path(directory))
            )
        self.assertEqual(prereg.scenario_count, 30)
        self.assertEqual(prereg.estimator_execution_count, 60)
        self.assertEqual(prereg.v2_overall_percent, 35.0)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_dynamic_clock_drift_preregistration(
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
                load_dynamic_clock_drift_preregistration(*paths)

    def test_rejects_estimator_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["new_estimator_execution"] = True
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_preregistration(*paths)

    def test_rejects_source_modification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["official_source_modified"] = True
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_preregistration(*paths)

    def test_rejects_failed_audit_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["verification"]["audit_hashes_verified"] = False
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_preregistration(*paths)

    def test_rejects_wrong_parent_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            prereg = json.loads(paths[1].read_text())
            prereg["parent_evidence"]["commit"] = "0" * 40
            paths[1].write_text(json.dumps(prereg))
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_preregistration(*paths)

    def test_rejects_wrong_scenario_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root, scenario_count=29, execution_count=60)
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_preregistration(*paths)

    def test_rejects_wrong_execution_total(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root, execution_count=59)
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_preregistration(*paths)

    def test_rejects_progress_advance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            prereg = json.loads(paths[1].read_text())
            prereg["progress"]["v2_stage_3_percent"] = 10
            paths[1].write_text(json.dumps(prereg))
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_preregistration(*paths)


if __name__ == "__main__":
    unittest.main()
