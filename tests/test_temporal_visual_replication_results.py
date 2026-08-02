"""Tests for V2-E01b replication result validation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from veranav.temporal_visual_replication_results import (
    ReplicationCellSummary,
    load_temporal_visual_replication_results,
)

COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
OFFSETS = (-20.0, -10.0, 10.0, 20.0)
DROPOUTS = (0.05, 0.10, 0.15, 0.20)
SEEDS = (20260801, 20260802, 20260803, 20260804, 20260805)


class TemporalVisualReplicationResultsTest(unittest.TestCase):
    def payloads(self) -> tuple[dict, dict, dict]:
        digest = "a" * 64
        manifest = {
            "evidence_audit_sha256": digest,
            "experiment": "openvins-temporal-visual-interaction-replication",
            "official_source_modified": False,
            "preregistration_sha256": digest,
            "schema_version": 1,
            "upstream_commit": COMMIT,
            "verification": {
                "five_seed_masks_distinct": True,
                "masks_equal_across_offsets": True,
                "masks_nested_within_seed": True,
                "physical_references_byte_identical": True,
                "preregistration_preceded_execution": True,
                "raw_measurement_fingerprints_identical": True,
                "resume_safe_execution_complete": True,
            },
        }
        cells = []
        for offset in OFFSETS:
            for dropout in DROPOUTS:
                cells.append(
                    {
                        "dropout_fraction": dropout,
                        "global_additive_ci95_lower_m": 0.0,
                        "global_additive_mean_m": 0.0,
                        "global_ratio_mean": 1.0,
                        "local_additive_ci95_lower_m": 0.0,
                        "local_additive_mean_m": 0.0,
                        "local_ratio_mean": 1.0,
                        "offset_ms": offset,
                        "replicated_supported": False,
                        "seed_support_count": 0,
                    }
                )
        seed_rows = [
            {
                "dropout_fraction": dropout,
                "offset_ms": offset,
                "seed": seed,
            }
            for seed in SEEDS
            for offset in OFFSETS
            for dropout in DROPOUTS
        ]
        results = {
            "cell_summaries": cells,
            "project_progress": {
                "v1_overall_percent": 100.0,
                "v2_overall_percent": 35.0,
            },
            "replication_status": "replication_not_supported",
            "schema_version": 1,
            "seed_interactions": seed_rows,
            "supported_cell_count": 0,
        }
        audit = {
            "execution_count": 134,
            "five_seed_masks_distinct": True,
            "physical_scenario_count": 105,
        }
        return manifest, results, audit

    def write(self, root: Path) -> tuple[Path, Path, Path]:
        manifest, results, audit = self.payloads()
        paths = (root / "manifest.json", root / "results.json", root / "audit.json")
        for path, payload in zip(paths, (manifest, results, audit)):
            path.write_text(json.dumps(payload))
        return paths

    def test_loads_valid_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = load_temporal_visual_replication_results(*self.write(Path(directory)))
        self.assertEqual(result.physical_scenario_count, 105)
        self.assertEqual(result.estimator_execution_count, 134)
        self.assertEqual(result.v2_overall_percent, 35.0)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_temporal_visual_replication_results("/missing/a", "/missing/b", "/missing/c")

    def test_rejects_wrong_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            payload = json.loads(paths[0].read_text())
            payload["schema_version"] = 2
            paths[0].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_results(*paths)

    def test_rejects_source_modification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            payload = json.loads(paths[0].read_text())
            payload["official_source_modified"] = True
            paths[0].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_results(*paths)

    def test_rejects_failed_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            payload = json.loads(paths[0].read_text())
            payload["verification"]["masks_nested_within_seed"] = False
            paths[0].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_results(*paths)

    def test_rejects_wrong_cell_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            payload = json.loads(paths[1].read_text())
            payload["cell_summaries"][0], payload["cell_summaries"][1] = (
                payload["cell_summaries"][1], payload["cell_summaries"][0]
            )
            paths[1].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_results(*paths)

    def test_rejects_wrong_seed_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            payload = json.loads(paths[1].read_text())
            payload["seed_interactions"][0], payload["seed_interactions"][1] = (
                payload["seed_interactions"][1], payload["seed_interactions"][0]
            )
            paths[1].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_results(*paths)

    def test_rejects_supported_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            payload = json.loads(paths[1].read_text())
            payload["supported_cell_count"] = 1
            paths[1].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_results(*paths)

    def test_rejects_progress_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            payload = json.loads(paths[1].read_text())
            payload["project_progress"]["v2_overall_percent"] = 36.0
            paths[1].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_temporal_visual_replication_results(*paths)

    def test_rejects_invalid_cell_metric(self) -> None:
        with self.assertRaises(ValueError):
            ReplicationCellSummary(
                offset_ms=-20.0,
                dropout_fraction=0.05,
                seed_support_count=0,
                replicated_supported=False,
                global_additive_mean_m=float("nan"),
                global_additive_ci95_lower_m=0.0,
                global_ratio_mean=1.0,
                local_additive_mean_m=0.0,
                local_additive_ci95_lower_m=0.0,
                local_ratio_mean=1.0,
            )


if __name__ == "__main__":
    unittest.main()
