"""Tests for the V2-E01b replication preregistration."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from veranav.temporal_visual_replication import (
    load_temporal_visual_replication_preregistration,
)


COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
PARENT = "70c27e0957bd03eaa0a8a87f35d394d9b046241b"


class TemporalVisualReplicationPreregistrationTest(unittest.TestCase):
    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "analysis_only": True,
            "experiment": (
                "openvins-temporal-visual-interaction-replication"
            ),
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
                "analytical_cell_count": 125,
                "dropout_fractions": [0.0, 0.05, 0.1, 0.15, 0.2],
                "estimator_execution_count": 134,
                "offsets_ms": [-20.0, -10.0, 0.0, 10.0, 20.0],
                "physical_scenario_count": 105,
                "seeds": [
                    20260801,
                    20260802,
                    20260803,
                    20260804,
                    20260805,
                ],
            },
            "parent_result": {
                "commit": PARENT,
                "supported_flags": [
                    "local_rmse_supported",
                    "rmse_supported",
                ],
            },
            "progress": {
                "v1_overall_percent": 100.0,
                "v2_overall_percent": 20.0,
            },
            "replicated_support_criterion": {
                "minimum_seed_support_count": 4,
            },
            "schema_version": 1,
        }
        return manifest, prereg

    def write(
        self,
        root: Path,
        execution_total: int = 134,
    ) -> tuple[Path, Path, Path, Path]:
        manifest, prereg = self.payloads()
        manifest_path = root / "manifest.json"
        prereg_path = root / "preregistration.json"
        cells_path = root / "analysis_cells.csv"
        execution_path = root / "execution_plan.csv"

        manifest_path.write_text(json.dumps(manifest))
        prereg_path.write_text(json.dumps(prereg))

        with cells_path.open("w", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["id"],
            )
            writer.writeheader()
            for index in range(125):
                writer.writerow({"id": index})

        repeats = [1] * 105
        repeats[0] += execution_total - 105
        with execution_path.open("w", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["repeat_count"],
            )
            writer.writeheader()
            for repeat in repeats:
                writer.writerow({"repeat_count": repeat})

        return (
            manifest_path,
            prereg_path,
            cells_path,
            execution_path,
        )

    def test_loads_valid_preregistration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prereg = load_temporal_visual_replication_preregistration(
                *self.write(Path(directory))
            )
        self.assertEqual(prereg.analytical_cell_count, 125)
        self.assertEqual(prereg.estimator_execution_count, 134)
        self.assertEqual(prereg.v2_overall_percent, 20.0)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_temporal_visual_replication_preregistration(
                "/missing/a",
                "/missing/b",
                "/missing/c",
                "/missing/d",
            )

    def test_rejects_wrong_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["schema_version"] = 2
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_preregistration(*paths)

    def test_rejects_estimator_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["new_estimator_execution"] = True
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_preregistration(*paths)

    def test_rejects_source_modification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["official_source_modified"] = True
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_preregistration(*paths)

    def test_rejects_failed_audit_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest["verification"]["audit_hashes_verified"] = False
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_preregistration(*paths)

    def test_rejects_wrong_parent_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            prereg = json.loads(paths[1].read_text())
            prereg["parent_result"]["commit"] = "0" * 40
            paths[1].write_text(json.dumps(prereg))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_preregistration(*paths)

    def test_rejects_wrong_analysis_cell_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            lines = paths[2].read_text().splitlines()
            paths[2].write_text("\n".join(lines[:-1]) + "\n")
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_preregistration(*paths)

    def test_rejects_wrong_execution_total(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root, execution_total=133)
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_preregistration(*paths)

    def test_rejects_progress_advance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            prereg = json.loads(paths[1].read_text())
            prereg["progress"]["v2_overall_percent"] = 21.0
            paths[1].write_text(json.dumps(prereg))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_preregistration(*paths)


if __name__ == "__main__":
    unittest.main()
