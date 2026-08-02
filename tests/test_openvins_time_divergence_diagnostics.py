"""Tests for OpenVINS fixed-time divergence diagnostics."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from veranav.openvins_time_divergence_diagnostics import (
    ErrorTraceDiagnostics,
    OpenVinsTimeDivergenceDiagnostics,
    TimeDivergenceScenario,
    load_openvins_time_divergence_diagnostics,
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


class OpenVinsTimeDivergenceDiagnosticsTest(unittest.TestCase):
    def trace(self, catastrophic: bool = False) -> dict:
        return {
            "availability_fraction": {"1": 0.9},
            "broad_trajectory_failure": catastrophic,
            "catastrophic_divergence": catastrophic,
            "final_error_m": 0.2 if not catastrophic else 200.0,
            "first_crossing_s": {
                "1": None if not catastrophic else 10.0,
                "10": None if not catastrophic else 12.0,
                "100": None if not catastrophic else 20.0,
                "1000": None,
            },
            "max_m": 0.3 if not catastrophic else 300.0,
            "max_time_s": 100.0,
            "mean_m": 0.1 if not catastrophic else 50.0,
            "median_m": 0.1 if not catastrophic else 20.0,
            "p90_m": 0.2 if not catastrophic else 100.0,
            "p95_m": 0.22 if not catastrophic else 150.0,
            "p99_m": 0.25 if not catastrophic else 250.0,
            "post_onset_fraction_above_1m": (
                0.0 if not catastrophic else 0.9
            ),
            "recovered_after_failure": False,
            "recovery_time_s": None,
            "rmse_m": 0.12 if not catastrophic else 80.0,
            "sustained_failure_onset_s": (
                None if not catastrophic else 10.0
            ),
            "top_1_percent_squared_error_share": 0.2,
            "top_5_percent_squared_error_share": 0.5,
        }

    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "analysis_config_sha256": digest,
            "analysis_only": True,
            "experiment": (
                "openvins-fixed-time-divergence-diagnostics"
            ),
            "input_artifacts": {},
            "inputs": {
                "fixed_manifest_sha256": digest,
                "fixed_results_sha256": digest,
                "online_manifest_sha256": digest,
                "online_results_sha256": digest,
            },
            "measurement_realization": {
                "camera_fingerprint": "a" * 16,
                "imu_fingerprint": "b" * 16,
            },
            "official_reproduction_manifest_sha256": digest,
            "official_source_modified": False,
            "schema_version": 1,
            "upstream_commit": COMMIT,
            "verification": {
                "fixed_online_physical_references_byte_identical": True,
                "input_artifact_hashes_verified": True,
                "no_new_estimator_execution": True,
                "paired_measurement_realization": True,
            },
        }
        results = {
            "experiment": (
                "openvins-fixed-time-divergence-diagnostics"
            ),
            "scenario_summary": {},
            "scenarios": [
                {
                    "duration_s": 300.0,
                    "fixed": self.trace(name != "baseline"),
                    "injected_offset_ms": (
                        0.0 if name == "baseline" else 5.0
                    ),
                    "online": self.trace(False),
                    "sample_count": 300,
                    "scenario": name,
                }
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

    def test_loads_valid_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            experiment = load_openvins_time_divergence_diagnostics(
                *self.write(Path(directory))
            )
        self.assertEqual(experiment.upstream_commit, COMMIT)
        self.assertEqual(len(experiment.scenarios), 9)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_openvins_time_divergence_diagnostics(
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
                load_openvins_time_divergence_diagnostics(
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
                load_openvins_time_divergence_diagnostics(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_estimator_rerun_flag(self) -> None:
        manifest, results = self.payloads()
        manifest["verification"]["no_new_estimator_execution"] = False

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))

            with self.assertRaises(ValueError):
                load_openvins_time_divergence_diagnostics(
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
                load_openvins_time_divergence_diagnostics(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_invalid_quantile_order(self) -> None:
        with self.assertRaises(ValueError):
            ErrorTraceDiagnostics(
                rmse_m=1.0,
                mean_m=1.0,
                median_m=1.0,
                p90_m=5.0,
                p95_m=4.0,
                p99_m=6.0,
                max_m=7.0,
                max_time_s=10.0,
                final_error_m=1.0,
                sustained_failure_onset_s=None,
                recovery_time_s=None,
                recovered_after_failure=False,
                post_onset_fraction_above_1m=0.0,
                top_1_percent_squared_error_share=0.1,
                top_5_percent_squared_error_share=0.3,
                broad_trajectory_failure=False,
                catastrophic_divergence=False,
            )

    def test_rejects_inconsistent_recovery(self) -> None:
        with self.assertRaises(ValueError):
            ErrorTraceDiagnostics(
                rmse_m=1.0,
                mean_m=1.0,
                median_m=1.0,
                p90_m=1.0,
                p95_m=1.0,
                p99_m=1.0,
                max_m=1.0,
                max_time_s=10.0,
                final_error_m=1.0,
                sustained_failure_onset_s=5.0,
                recovery_time_s=None,
                recovered_after_failure=True,
                post_onset_fraction_above_1m=0.5,
                top_1_percent_squared_error_share=0.1,
                top_5_percent_squared_error_share=0.3,
                broad_trajectory_failure=True,
                catastrophic_divergence=False,
            )

    def test_rejects_nonbaseline_zero_offset(self) -> None:
        trace = ErrorTraceDiagnostics(
            rmse_m=1.0,
            mean_m=1.0,
            median_m=1.0,
            p90_m=1.0,
            p95_m=1.0,
            p99_m=1.0,
            max_m=1.0,
            max_time_s=10.0,
            final_error_m=1.0,
            sustained_failure_onset_s=None,
            recovery_time_s=None,
            recovered_after_failure=False,
            post_onset_fraction_above_1m=0.0,
            top_1_percent_squared_error_share=0.1,
            top_5_percent_squared_error_share=0.3,
            broad_trajectory_failure=False,
            catastrophic_divergence=False,
        )

        with self.assertRaises(ValueError):
            TimeDivergenceScenario(
                scenario="pos-5ms",
                injected_offset_ms=0.0,
                sample_count=300,
                duration_s=300.0,
                fixed=trace,
                online=trace,
            )


if __name__ == "__main__":
    unittest.main()
