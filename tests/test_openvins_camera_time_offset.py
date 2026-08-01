"""Tests for committed OpenVINS camera timestamp-offset evidence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from veranav.openvins_camera_time_offset import (
    CameraTimeOffsetScenarioResult,
    OpenVinsCameraTimeOffsetExperiment,
    load_openvins_camera_time_offset_experiment,
)


COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
SCENARIOS = (
    "baseline",
    "neg-50ms",
    "neg-20ms",
    "neg-10ms",
    "neg-5ms",
    "pos-5ms",
    "pos-10ms",
    "pos-20ms",
    "pos-50ms",
)


class OpenVinsCameraTimeOffsetTest(unittest.TestCase):
    def scenario(self, name: str) -> dict:
        baseline = name == "baseline"
        offset = 0.0 if baseline else 5.0
        return {
            "calibration_aware_max_m": 0.2,
            "calibration_aware_rmse_m": 0.1,
            "calibration_aware_rmse_ratio": (
                1.0 if baseline else 1.1
            ),
            "converged_within_run": True,
            "convergence_time_s": 0.0 if baseline else 20.0,
            "correction_error_ms": 0.0,
            "estimated_timestamp_correction_ms": offset,
            "final_calibration_residual_ms": 0.0,
            "final_estimated_cam_to_imu_ms": 2.0 - offset,
            "initial_estimated_cam_to_imu_ms": 2.0,
            "injected_offset_ms": offset,
            "nominal_clock_max_m": 0.2,
            "nominal_clock_rmse_m": 0.1,
            "nominal_clock_rmse_ratio": (
                1.0 if baseline else 1.2
            ),
            "physical_time_max_m": 0.2,
            "physical_time_rmse_m": 0.1,
            "sample_count": 300,
            "scenario": name,
            "tail_calibration_rmse_ms": 0.2,
            "target_cam_to_imu_ms": 2.0 - offset,
            "true_cam_to_imu_ms": 2.0,
        }

    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "experiment": "openvins-camera-timestamp-offset",
            "experiment_config_sha256": digest,
            "measurement_realization": {
                "camera_fingerprint": "a" * 16,
                "imu_fingerprint": "b" * 16,
            },
            "official_configuration_sha256": digest,
            "official_reproduction_manifest_sha256": digest,
            "official_source_modified": False,
            "online_time_calibration_enabled": True,
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
                "common_measurement_realization": True,
                "frame_mapping": (
                    "openvins-global-xyz-to-veranav-ned"
                ),
                "output_schema": "veranav-position-trajectory-v1",
                "physical_reference_trajectories_byte_identical": True,
            },
        }
        results = {
            "calibration_convergence_definition": {},
            "experiment": "openvins-camera-timestamp-offset",
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
            experiment = load_openvins_camera_time_offset_experiment(
                *self.write(Path(directory))
            )
        self.assertEqual(experiment.upstream_commit, COMMIT)
        self.assertEqual(len(experiment.scenario_results), 9)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_openvins_camera_time_offset_experiment(
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
                load_openvins_camera_time_offset_experiment(
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
                load_openvins_camera_time_offset_experiment(
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
                load_openvins_camera_time_offset_experiment(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_disabled_online_calibration(self) -> None:
        manifest, results = self.payloads()
        manifest["online_time_calibration_enabled"] = False

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))

            with self.assertRaises(ValueError):
                load_openvins_camera_time_offset_experiment(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_measurement_mismatch(self) -> None:
        manifest, results = self.payloads()
        manifest["verification"]["common_measurement_realization"] = False

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))

            with self.assertRaises(ValueError):
                load_openvins_camera_time_offset_experiment(
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
                load_openvins_camera_time_offset_experiment(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_inconsistent_convergence(self) -> None:
        with self.assertRaises(ValueError):
            CameraTimeOffsetScenarioResult(
                scenario="pos-5ms",
                injected_offset_ms=5.0,
                sample_count=300,
                true_cam_to_imu_ms=2.0,
                target_cam_to_imu_ms=-3.0,
                initial_estimated_cam_to_imu_ms=2.0,
                final_estimated_cam_to_imu_ms=-3.0,
                final_calibration_residual_ms=0.0,
                tail_calibration_rmse_ms=0.2,
                estimated_timestamp_correction_ms=5.0,
                correction_error_ms=0.0,
                converged_within_run=True,
                convergence_time_s=None,
                nominal_clock_rmse_m=0.1,
                nominal_clock_max_m=0.2,
                nominal_clock_rmse_ratio=1.2,
                calibration_aware_rmse_m=0.1,
                calibration_aware_max_m=0.2,
                calibration_aware_rmse_ratio=1.1,
                physical_time_rmse_m=0.1,
                physical_time_max_m=0.2,
            )


if __name__ == "__main__":
    unittest.main()
