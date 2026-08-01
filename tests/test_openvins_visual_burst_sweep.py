"""Tests for committed OpenVINS visual-outage timing evidence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from veranav.openvins_visual_burst_sweep import (
    OpenVinsVisualBurstSweep,
    VisualBurstScenarioResult,
    load_openvins_visual_burst_sweep,
)


COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
SCENARIOS = (
    "baseline",
    "burst-t030-d1",
    "burst-t030-d3",
    "burst-t090-d1",
    "burst-t090-d3",
    "burst-t150-d1",
    "burst-t150-d3",
    "burst-t210-d1",
    "burst-t210-d3",
)


class OpenVinsVisualBurstSweepTest(unittest.TestCase):
    def scenario(self, name: str) -> dict:
        baseline = name == "baseline"
        return {
            "baseline_local_window_peak_m": 0.2,
            "baseline_local_window_rmse_m": 0.1,
            "burst_duration_s": 0.0 if baseline else 1.0,
            "burst_start_s": 0.0 if baseline else 30.0,
            "degraded_frames": 0 if baseline else 10,
            "dropped_observations": 0 if baseline else 100,
            "integrated_positive_excess_m_s": (
                0.0 if baseline else 0.2
            ),
            "local_window_peak_m": 0.2 if baseline else 0.3,
            "local_window_peak_ratio": 1.0 if baseline else 1.5,
            "local_window_rmse_m": 0.1 if baseline else 0.15,
            "local_window_rmse_ratio": 1.0 if baseline else 1.5,
            "mode": "baseline" if baseline else "burst-frame-drop",
            "outage_rmse_m": 0.1 if baseline else 0.2,
            "overall_max_m": 0.2 if baseline else 0.3,
            "overall_rmse_m": 0.1 if baseline else 0.12,
            "peak_excess_error_m": 0.0 if baseline else 0.1,
            "post_window_rmse_m": 0.1 if baseline else 0.14,
            "pre_window_rmse_m": 0.1,
            "recovered_within_horizon": True,
            "recovery_time_s": 0.0 if baseline else 2.0,
            "sample_count": 300,
            "scenario": name,
        }

    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "experiment": (
                "openvins-visual-burst-timing-sensitivity"
            ),
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
            "experiment": (
                "openvins-visual-burst-timing-sensitivity"
            ),
            "recovery_definition": {},
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

    def test_loads_valid_sweep(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            experiment = load_openvins_visual_burst_sweep(
                *self.write(Path(directory))
            )
        self.assertEqual(experiment.upstream_commit, COMMIT)
        self.assertEqual(len(experiment.scenario_results), 9)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_openvins_visual_burst_sweep(
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
                load_openvins_visual_burst_sweep(
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
                load_openvins_visual_burst_sweep(
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
                load_openvins_visual_burst_sweep(
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
                load_openvins_visual_burst_sweep(
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
                load_openvins_visual_burst_sweep(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_negative_metric(self) -> None:
        with self.assertRaises(ValueError):
            VisualBurstScenarioResult(
                scenario="burst-t030-d1",
                mode="burst-frame-drop",
                burst_start_s=30.0,
                burst_duration_s=1.0,
                sample_count=300,
                degraded_frames=10,
                dropped_observations=100,
                overall_rmse_m=-1.0,
                overall_max_m=0.3,
                pre_window_rmse_m=0.1,
                outage_rmse_m=0.2,
                post_window_rmse_m=0.15,
                local_window_rmse_m=0.15,
                baseline_local_window_rmse_m=0.1,
                local_window_rmse_ratio=1.5,
                local_window_peak_m=0.3,
                baseline_local_window_peak_m=0.2,
                local_window_peak_ratio=1.5,
                peak_excess_error_m=0.1,
                integrated_positive_excess_m_s=0.2,
                recovery_time_s=2.0,
                recovered_within_horizon=True,
            )

    def test_rejects_inconsistent_recovery(self) -> None:
        with self.assertRaises(ValueError):
            VisualBurstScenarioResult(
                scenario="burst-t030-d1",
                mode="burst-frame-drop",
                burst_start_s=30.0,
                burst_duration_s=1.0,
                sample_count=300,
                degraded_frames=10,
                dropped_observations=100,
                overall_rmse_m=0.12,
                overall_max_m=0.3,
                pre_window_rmse_m=0.1,
                outage_rmse_m=0.2,
                post_window_rmse_m=0.15,
                local_window_rmse_m=0.15,
                baseline_local_window_rmse_m=0.1,
                local_window_rmse_ratio=1.5,
                local_window_peak_m=0.3,
                baseline_local_window_peak_m=0.2,
                local_window_peak_ratio=1.5,
                peak_excess_error_m=0.1,
                integrated_positive_excess_m_s=0.2,
                recovery_time_s=None,
                recovered_within_horizon=True,
            )


if __name__ == "__main__":
    unittest.main()
