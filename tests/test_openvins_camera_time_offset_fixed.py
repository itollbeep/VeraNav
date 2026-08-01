"""Tests for fixed versus online OpenVINS temporal calibration."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from veranav.openvins_camera_time_offset_fixed import (
    FixedTimeCalibrationScenarioResult,
    OpenVinsFixedTimeCalibrationComparison,
    load_openvins_fixed_time_calibration_comparison,
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


class OpenVinsFixedTimeCalibrationTest(unittest.TestCase):
    def scenario(self, name: str) -> dict:
        baseline = name == "baseline"
        offset = 0.0 if baseline else 5.0
        return {
            "fixed_final_calibration_residual_ms": offset,
            "fixed_nominal_max_m": 0.3,
            "fixed_nominal_rmse_m": 0.15,
            "fixed_physical_max_m": 0.3,
            "fixed_physical_rmse_m": 0.15,
            "fixed_rmse_ratio_to_fixed_baseline": (
                1.0 if baseline else 1.5
            ),
            "injected_offset_ms": offset,
            "online_calibration_aware_rmse_m": 0.1,
            "online_calibration_rmse_reduction_fraction": (
                0.0 if baseline else (1.0 / 3.0)
            ),
            "online_calibration_rmse_reduction_m": (
                0.0 if baseline else 0.05
            ),
            "online_convergence_time_s": 1.0,
            "online_final_calibration_residual_ms": 0.01,
            "online_nominal_rmse_m": 0.11,
            "online_to_fixed_rmse_ratio": (
                2.0 / 3.0
            ),
            "parameter_residual_reduction_fraction": (
                None if baseline else 0.998
            ),
            "sample_count": 300,
            "scenario": name,
        }

    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "configuration_change": (
                "calib_cam_timeoffset:true-to-false"
            ),
            "configurations": {
                "fixed_config_sha256": digest,
                "official_config_sha256": digest,
            },
            "experiment": (
                "openvins-camera-timestamp-offset-fixed-calibration"
            ),
            "experiment_config_sha256": digest,
            "measurement_realization": {
                "camera_fingerprint": "a" * 16,
                "imu_fingerprint": "b" * 16,
            },
            "official_reproduction_manifest_sha256": digest,
            "official_source_modified": False,
            "online_experiment_manifest_sha256": digest,
            "online_experiment_results_sha256": digest,
            "online_time_calibration_enabled": False,
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
                "fixed_calibrated_and_nominal_references_byte_identical": True,
                "frame_mapping": (
                    "openvins-global-xyz-to-veranav-ned"
                ),
                "online_fixed_physical_references_byte_identical": True,
                "output_schema": "veranav-position-trajectory-v1",
                "paired_online_fixed_measurement_realization": True,
            },
        }
        results = {
            "experiment": (
                "openvins-camera-timestamp-offset-fixed-calibration"
            ),
            "paired_online_experiment": (
                "openvins-camera-timestamp-offset"
            ),
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

    def test_loads_valid_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            experiment = (
                load_openvins_fixed_time_calibration_comparison(
                    *self.write(Path(directory))
                )
            )
        self.assertEqual(experiment.upstream_commit, COMMIT)
        self.assertEqual(len(experiment.scenario_results), 9)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_openvins_fixed_time_calibration_comparison(
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
                load_openvins_fixed_time_calibration_comparison(
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
                load_openvins_fixed_time_calibration_comparison(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_enabled_calibration(self) -> None:
        manifest, results = self.payloads()
        manifest["online_time_calibration_enabled"] = True

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))

            with self.assertRaises(ValueError):
                load_openvins_fixed_time_calibration_comparison(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_configuration_change(self) -> None:
        manifest, results = self.payloads()
        manifest["configuration_change"] = "other"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))

            with self.assertRaises(ValueError):
                load_openvins_fixed_time_calibration_comparison(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_measurement_mismatch(self) -> None:
        manifest, results = self.payloads()
        manifest["verification"][
            "paired_online_fixed_measurement_realization"
        ] = False

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))

            with self.assertRaises(ValueError):
                load_openvins_fixed_time_calibration_comparison(
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
                load_openvins_fixed_time_calibration_comparison(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_negative_metric(self) -> None:
        with self.assertRaises(ValueError):
            FixedTimeCalibrationScenarioResult(
                scenario="pos-5ms",
                injected_offset_ms=5.0,
                sample_count=300,
                fixed_final_calibration_residual_ms=5.0,
                fixed_nominal_rmse_m=-1.0,
                fixed_nominal_max_m=0.3,
                fixed_physical_rmse_m=0.15,
                fixed_physical_max_m=0.3,
                fixed_rmse_ratio_to_fixed_baseline=1.5,
                online_nominal_rmse_m=0.11,
                online_calibration_aware_rmse_m=0.1,
                online_final_calibration_residual_ms=0.01,
                online_convergence_time_s=1.0,
                online_calibration_rmse_reduction_m=0.05,
                online_calibration_rmse_reduction_fraction=1.0 / 3.0,
                online_to_fixed_rmse_ratio=2.0 / 3.0,
                parameter_residual_reduction_fraction=0.998,
            )


if __name__ == "__main__":
    unittest.main()
