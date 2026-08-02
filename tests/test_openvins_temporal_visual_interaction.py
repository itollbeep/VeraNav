"""Tests for temporal-calibration and visual-dropout interaction."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from veranav.openvins_temporal_visual_interaction import (
    TemporalVisualInteractionResult,
    TemporalVisualScenarioResult,
    load_temporal_visual_interaction,
)

COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
SCENARIOS = (
    "neg20-drop00", "neg20-drop10", "neg20-drop30", "neg20-drop50",
    "zero-drop00", "zero-drop10", "zero-drop30", "zero-drop50",
    "pos20-drop00", "pos20-drop10", "pos20-drop30", "pos20-drop50",
)
INTERACTIONS = (
    "neg20-drop10", "neg20-drop30", "neg20-drop50",
    "pos20-drop10", "pos20-drop30", "pos20-drop50",
)


class TemporalVisualInteractionTest(unittest.TestCase):
    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "experiment": (
                "openvins-temporal-calibration-visual-degradation-interaction"
            ),
            "experiment_config_sha256": digest,
            "measurement_realization": {
                "camera_fingerprint": "a" * 16,
                "imu_fingerprint": "b" * 16,
            },
            "official_source_modified": False,
            "runner": {
                "binary_sha256": digest,
                "cmake_sha256": digest,
                "source_sha256": digest,
            },
            "schema_version": 1,
            "upstream_commit": COMMIT,
            "verification": {
                "deterministic_replay_verified": True,
                "dropout_masks_equal_across_offsets": True,
                "dropout_masks_nested": True,
                "physical_references_byte_identical": True,
                "raw_measurement_fingerprints_identical": True,
                "single_factor_anchors_reproduced": True,
            },
        }
        scenarios = []
        for name in SCENARIOS:
            offset = -20.0 if name.startswith("neg20") else 20.0 if name.startswith("pos20") else 0.0
            probability = {"00": 0.0, "10": 0.1, "30": 0.3, "50": 0.5}[name[-2:]]
            scenarios.append(
                {
                    "convergence_time_s": 1.0,
                    "final_abs_residual_ms": 0.1,
                    "local_max_rmse_m": 0.2,
                    "offset_ms": offset,
                    "one_metre_availability": 1.0,
                    "position_rmse_m": 0.1,
                    "realized_dropout_fraction": probability,
                    "requested_dropout_fraction": probability,
                    "scenario": name,
                }
            )
        interactions = [
            {
                "criterion_supported": False,
                "local_rmse_interaction_ratio": 1.0,
                "rmse_interaction_ratio": 1.0,
                "scenario": name,
                "supported_metric_count": 0,
            }
            for name in INTERACTIONS
        ]
        results = {
            "experiment": (
                "openvins-temporal-calibration-visual-degradation-interaction"
            ),
            "interaction_status": "pilot_not_supported",
            "interactions": interactions,
            "project_progress": {
                "v1_overall_percent": 100.0,
                "v2_overall_percent": 20.0,
            },
            "schema_version": 1,
            "scenarios": scenarios,
        }
        return manifest, results

    def write(self, root: Path) -> tuple[Path, Path]:
        manifest, results = self.payloads()
        manifest_path = root / "manifest.json"
        results_path = root / "results.json"
        manifest_path.write_text(json.dumps(manifest))
        results_path.write_text(json.dumps(results))
        return manifest_path, results_path

    def test_loads_valid_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            experiment = load_temporal_visual_interaction(
                *self.write(Path(directory))
            )
        self.assertEqual(len(experiment.scenario_results), 12)
        self.assertEqual(len(experiment.interaction_results), 6)
        self.assertEqual(experiment.v2_overall_percent, 20.0)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_temporal_visual_interaction(
                "/missing/manifest.json",
                "/missing/results.json",
            )

    def test_rejects_wrong_schema(self) -> None:
        manifest, results = self.payloads()
        manifest["schema_version"] = 2
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))
            with self.assertRaises(ValueError):
                load_temporal_visual_interaction(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_source_modification(self) -> None:
        manifest, results = self.payloads()
        manifest["official_source_modified"] = True
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))
            with self.assertRaises(ValueError):
                load_temporal_visual_interaction(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_failed_anchor_verification(self) -> None:
        manifest, results = self.payloads()
        manifest["verification"]["single_factor_anchors_reproduced"] = False
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))
            with self.assertRaises(ValueError):
                load_temporal_visual_interaction(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_scenario_order(self) -> None:
        manifest, results = self.payloads()
        results["scenarios"][0], results["scenarios"][1] = (
            results["scenarios"][1],
            results["scenarios"][0],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))
            with self.assertRaises(ValueError):
                load_temporal_visual_interaction(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_interaction_order(self) -> None:
        manifest, results = self.payloads()
        results["interactions"][0], results["interactions"][1] = (
            results["interactions"][1],
            results["interactions"][0],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))
            with self.assertRaises(ValueError):
                load_temporal_visual_interaction(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_invalid_status(self) -> None:
        manifest, results = self.payloads()
        results["interaction_status"] = "verified_novel"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))
            with self.assertRaises(ValueError):
                load_temporal_visual_interaction(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_negative_metric(self) -> None:
        with self.assertRaises(ValueError):
            TemporalVisualScenarioResult(
                scenario="zero-drop00",
                offset_ms=0.0,
                requested_dropout_fraction=0.0,
                realized_dropout_fraction=0.0,
                position_rmse_m=-1.0,
                local_max_rmse_m=0.1,
                final_abs_residual_ms=0.1,
                one_metre_availability=1.0,
                convergence_time_s=0.0,
            )

    def test_rejects_interaction_flag_mismatch(self) -> None:
        with self.assertRaises(ValueError):
            TemporalVisualInteractionResult(
                scenario="neg20-drop10",
                rmse_interaction_ratio=1.0,
                local_rmse_interaction_ratio=1.0,
                supported_metric_count=2,
                criterion_supported=False,
            )


if __name__ == "__main__":
    unittest.main()
