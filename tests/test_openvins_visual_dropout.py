"""Tests for committed OpenVINS visual-dropout evidence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from veranav.openvins_visual_dropout import (
    OpenVinsVisualDropoutExperiment,
    VisualDropoutScenarioResult,
    load_openvins_visual_dropout_experiment,
)


COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
SCENARIOS = (
    "baseline",
    "random-10",
    "random-30",
    "random-50",
    "burst-1s",
    "burst-3s",
)


class OpenVinsVisualDropoutTest(unittest.TestCase):
    def scenario(self, name: str) -> dict:
        baseline = name == "baseline"
        return {
            "degraded_frames": 0 if baseline else 10,
            "dropped_observations": 0 if baseline else 100,
            "max_delta_m": 0.0 if baseline else 0.1,
            "max_ratio": 1.0 if baseline else 1.5,
            "mode": (
                "baseline"
                if baseline
                else (
                    "bernoulli-frame-drop"
                    if name.startswith("random")
                    else "burst-frame-drop"
                )
            ),
            "position_max_m": 0.2 if baseline else 0.3,
            "position_mean_m": 0.1 if baseline else 0.15,
            "position_rmse_m": 0.12 if baseline else 0.18,
            "realized_frame_drop_fraction": (
                0.0 if baseline else 0.1
            ),
            "rmse_delta_m": 0.0 if baseline else 0.06,
            "rmse_ratio": 1.0 if baseline else 1.5,
            "sample_count": 300,
            "scenario": name,
            "total_frames": 300,
        }

    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "experiment": "openvins-visual-observation-dropout",
            "experiment_config_sha256": digest,
            "official_configuration_sha256": digest,
            "official_reproduction_manifest_sha256": digest,
            "official_source_modified": False,
            "release_tag": "v2.7",
            "runner": {
                "binary_sha256": digest,
                "cmake_sha256": digest,
                "source_sha256": digest,
            },
            "runner_source_location": "external-only",
            "scenario_artifacts": {},
            "schema_version": 1,
            "upstream_commit": COMMIT,
            "verification": {
                "all_scenario_replays_byte_identical": True,
                "frame_mapping": (
                    "openvins-global-xyz-to-veranav-ned"
                ),
                "output_schema": "veranav-position-trajectory-v1",
                "paired_reference_trajectories_byte_identical": True,
            },
        }
        results = {
            "experiment": "openvins-visual-observation-dropout",
            "scenarios": [
                self.scenario(name)
                for name in SCENARIOS
            ],
            "schema_version": 1,
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
            experiment = load_openvins_visual_dropout_experiment(
                *self.write(Path(directory))
            )
        self.assertEqual(experiment.upstream_commit, COMMIT)
        self.assertEqual(len(experiment.scenarios), 6)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_openvins_visual_dropout_experiment(
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
                load_openvins_visual_dropout_experiment(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_wrong_commit(self) -> None:
        manifest, results = self.payloads()
        manifest["upstream_commit"] = "b" * 40
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))
            with self.assertRaises(ValueError):
                load_openvins_visual_dropout_experiment(
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
                load_openvins_visual_dropout_experiment(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_reference_mismatch(self) -> None:
        manifest, results = self.payloads()
        manifest["verification"][
            "paired_reference_trajectories_byte_identical"
        ] = False
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))
            with self.assertRaises(ValueError):
                load_openvins_visual_dropout_experiment(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_scenario_order(self) -> None:
        manifest, results = self.payloads()
        results["scenarios"][1], results["scenarios"][2] = (
            results["scenarios"][2],
            results["scenarios"][1],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))
            with self.assertRaises(ValueError):
                load_openvins_visual_dropout_experiment(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_negative_metric(self) -> None:
        with self.assertRaises(ValueError):
            VisualDropoutScenarioResult(
                scenario="random-10",
                mode="bernoulli-frame-drop",
                sample_count=300,
                total_frames=300,
                degraded_frames=10,
                realized_frame_drop_fraction=0.1,
                dropped_observations=100,
                position_rmse_m=-1.0,
                position_mean_m=0.1,
                position_max_m=0.2,
                rmse_delta_m=0.1,
                rmse_ratio=1.5,
                max_delta_m=0.1,
                max_ratio=1.5,
            )


if __name__ == "__main__":
    unittest.main()
