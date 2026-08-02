"""Tests for committed OpenVINS IMU-noise degradation evidence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from veranav.openvins_imu_noise_degradation import (
    ImuNoiseScenarioResult,
    OpenVinsImuNoiseExperiment,
    load_openvins_imu_noise_experiment,
)


COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
SCENARIOS = (
    "baseline",
    "white-2x",
    "white-5x",
    "white-10x",
    "randomwalk-2x",
    "randomwalk-5x",
    "randomwalk-10x",
    "all-2x",
    "all-5x",
    "all-10x",
)


class OpenVinsImuNoiseDegradationTest(unittest.TestCase):
    def scenario(self, name: str) -> dict:
        baseline = name == "baseline"
        return {
            "accelerometer_delta_rms_mps2": (
                0.0 if baseline else 0.1
            ),
            "availability_0_1m": 0.9,
            "availability_0_5m": 1.0,
            "availability_1m": 1.0,
            "covariance_trace_mean_m2": 0.01,
            "gyroscope_delta_rms_radps": (
                0.0 if baseline else 0.01
            ),
            "position_max_m": 0.2,
            "position_mean_m": 0.1,
            "position_nees_95_coverage": 0.95,
            "position_nees_mean": 3.0,
            "position_nees_median": 2.5,
            "position_nees_p95": 7.0,
            "position_p95_m": 0.15,
            "position_rmse_m": 0.11,
            "random_walk_scale": 1.0 if baseline else 2.0,
            "rmse_ratio": 1.0 if baseline else 1.2,
            "sample_count": 300,
            "scenario": name,
            "sustained_failure_onset_s": None,
            "white_noise_scale": 1.0 if baseline else 2.0,
        }

    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "estimator_uses_nominal_noise_model": True,
            "experiment": "openvins-imu-noise-degradation",
            "experiment_config_sha256": digest,
            "measurement_realization": {
                "camera_fingerprint": "a" * 16,
                "nominal_imu_fingerprint": "b" * 16,
            },
            "official_configuration_sha256": digest,
            "official_imu_configuration_sha256": digest,
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
            "scenario_configuration_hashes": {},
            "schema_version": 1,
            "upstream_commit": COMMIT,
            "verification": {
                "all_scenario_replays_byte_identical": True,
                "common_nominal_measurement_realization": True,
                "frame_mapping": (
                    "openvins-global-xyz-to-veranav-ned"
                ),
                "output_schema": "veranav-position-trajectory-v1",
                "position_covariance_positive_definite": True,
                "reference_trajectories_byte_identical": True,
            },
        }
        results = {
            "consistency_definition": {},
            "experiment": "openvins-imu-noise-degradation",
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
            experiment = load_openvins_imu_noise_experiment(
                *self.write(Path(directory))
            )
        self.assertEqual(experiment.upstream_commit, COMMIT)
        self.assertEqual(len(experiment.scenario_results), 10)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_openvins_imu_noise_experiment(
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
                load_openvins_imu_noise_experiment(
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
                load_openvins_imu_noise_experiment(
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
                load_openvins_imu_noise_experiment(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_non_nominal_estimator_model(self) -> None:
        manifest, results = self.payloads()
        manifest["estimator_uses_nominal_noise_model"] = False

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))

            with self.assertRaises(ValueError):
                load_openvins_imu_noise_experiment(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_covariance_failure(self) -> None:
        manifest, results = self.payloads()
        manifest["verification"][
            "position_covariance_positive_definite"
        ] = False

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))

            with self.assertRaises(ValueError):
                load_openvins_imu_noise_experiment(
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
                load_openvins_imu_noise_experiment(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_negative_metric(self) -> None:
        with self.assertRaises(ValueError):
            ImuNoiseScenarioResult(
                scenario="white-2x",
                white_noise_scale=2.0,
                random_walk_scale=1.0,
                sample_count=300,
                position_rmse_m=-1.0,
                position_mean_m=0.1,
                position_p95_m=0.15,
                position_max_m=0.2,
                rmse_ratio=1.2,
                availability_0_1m=0.9,
                availability_0_5m=1.0,
                availability_1m=1.0,
                sustained_failure_onset_s=None,
                position_nees_mean=3.0,
                position_nees_median=2.5,
                position_nees_p95=7.0,
                position_nees_95_coverage=0.95,
                covariance_trace_mean_m2=0.01,
                gyroscope_delta_rms_radps=0.01,
                accelerometer_delta_rms_mps2=0.1,
            )

    def test_rejects_invalid_baseline_delta(self) -> None:
        with self.assertRaises(ValueError):
            ImuNoiseScenarioResult(
                scenario="baseline",
                white_noise_scale=1.0,
                random_walk_scale=1.0,
                sample_count=300,
                position_rmse_m=0.1,
                position_mean_m=0.1,
                position_p95_m=0.15,
                position_max_m=0.2,
                rmse_ratio=1.0,
                availability_0_1m=0.9,
                availability_0_5m=1.0,
                availability_1m=1.0,
                sustained_failure_onset_s=None,
                position_nees_mean=3.0,
                position_nees_median=2.5,
                position_nees_p95=7.0,
                position_nees_95_coverage=0.95,
                covariance_trace_mean_m2=0.01,
                gyroscope_delta_rms_radps=0.01,
                accelerometer_delta_rms_mps2=0.0,
            )


if __name__ == "__main__":
    unittest.main()
