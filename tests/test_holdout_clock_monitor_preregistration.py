"""Tests for the V2-E04 holdout monitor preregistration."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from veranav.holdout_clock_monitor_preregistration import (
    load_holdout_clock_monitor_preregistration,
)


COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
DISCOVERY = "5fedca7333116a935f09c3089f0164965663eacb"


class HoldoutClockMonitorPreregistrationTest(unittest.TestCase):
    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "analysis_only": True,
            "experiment": "openvins-holdout-clock-monitor-validation",
            "new_estimator_execution": False,
            "official_source_modified": False,
            "schema_version": 1,
            "source_inputs": {
                "config_sha256": digest,
                "single_channel_audit_sha256": digest,
                "temporal_overlap_audit_sha256": digest,
            },
            "upstream_commit": COMMIT,
            "verification": {
                "audit_hashes_verified": True,
                "candidate_rule_frozen": True,
                "generated_twice_byte_identical": True,
                "holdout_seeds_disjoint_from_discovery": True,
                "progress_unchanged": True,
            },
        }
        prereg = {
            "candidate_monitor": {
                "channel": "estimated_offset_peak_to_peak",
                "monitor_window_s": 5.0,
                "persistence_s": 3.0,
                "threshold_ms": 0.14729673122826897,
                "warmup_s": 10.0,
            },
            "discovery_evidence": {
                "discovery_commit": DISCOVERY
            },
            "online_ground_truth_input_count": 0,
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
        primary_count: int = 4,
        secondary_count: int = 20,
    ) -> tuple[Path, Path, Path]:
        manifest, prereg = self.payloads()
        manifest_path = root / "manifest.json"
        prereg_path = root / "preregistration.json"
        plan_path = root / "scenario_plan.csv"

        manifest_path.write_text(json.dumps(manifest))
        prereg_path.write_text(json.dumps(prereg))

        rows = []
        for index in range(static_count):
            rows.append(
                {
                    "scenario_id": f"static-{index}",
                    "label": "static-negative",
                    "dropout_seed": "20260811",
                    "profile_seed": "",
                    "repeat_count": "2",
                }
            )
        for index in range(primary_count):
            rows.append(
                {
                    "scenario_id": f"primary-{index}",
                    "label": "primary-challenge",
                    "dropout_seed": "20260811",
                    "profile_seed": "",
                    "repeat_count": "2",
                }
            )
        for index in range(secondary_count):
            rows.append(
                {
                    "scenario_id": f"secondary-{index}",
                    "label": "dynamic-secondary",
                    "dropout_seed": "20260811",
                    "profile_seed": (
                        "20260812"
                        if index % 2 == 0
                        else "20260813"
                    ),
                    "repeat_count": "2",
                }
            )

        with plan_path.open("w", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=[
                    "scenario_id",
                    "label",
                    "dropout_seed",
                    "profile_seed",
                    "repeat_count",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

        return manifest_path, prereg_path, plan_path

    def test_loads_valid_preregistration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prereg = load_holdout_clock_monitor_preregistration(
                *self.write(Path(directory))
            )
        self.assertEqual(prereg.scenario_count, 30)
        self.assertEqual(prereg.execution_count, 60)
        self.assertEqual(prereg.primary_challenge_count, 4)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_holdout_clock_monitor_preregistration(
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
                load_holdout_clock_monitor_preregistration(*paths)

    def test_rejects_estimator_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["new_estimator_execution"] = True
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_preregistration(*paths)

    def test_rejects_source_modification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["official_source_modified"] = True
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_preregistration(*paths)

    def test_rejects_unfrozen_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["verification"]["candidate_rule_frozen"] = False
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_preregistration(*paths)

    def test_rejects_discovery_dropout_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            with paths[2].open("r", newline="") as stream:
                rows = list(csv.DictReader(stream))
            rows[0]["dropout_seed"] = "20260801"
            with paths[2].open("w", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "scenario_id",
                        "label",
                        "dropout_seed",
                        "profile_seed",
                        "repeat_count",
                    ],
                )
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_preregistration(*paths)

    def test_rejects_discovery_profile_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            with paths[2].open("r", newline="") as stream:
                rows = list(csv.DictReader(stream))
            rows[-1]["profile_seed"] = "20260802"
            with paths[2].open("w", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "scenario_id",
                        "label",
                        "dropout_seed",
                        "profile_seed",
                        "repeat_count",
                    ],
                )
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_preregistration(*paths)

    def test_rejects_wrong_label_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root, secondary_count=19)
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_preregistration(*paths)

    def test_rejects_progress_advance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            prereg = json.loads(paths[1].read_text())
            prereg["progress"]["v2_stage_4_percent"] = 40
            paths[1].write_text(json.dumps(prereg))
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_preregistration(*paths)


if __name__ == "__main__":
    unittest.main()
