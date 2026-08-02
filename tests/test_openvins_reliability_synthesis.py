"""Tests for the final OpenVINS reliability synthesis."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from veranav.openvins_reliability_synthesis import (
    OpenVinsReliabilitySynthesis,
    ReliabilityFamilySummary,
    load_openvins_reliability_synthesis,
)


COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
FAMILIES = (
    "visual_dropout",
    "visual_burst",
    "camera_time_offset_online",
    "camera_time_offset_fixed",
    "time_divergence",
    "imu_noise",
)


class OpenVinsReliabilitySynthesisTest(unittest.TestCase):
    def payloads(self) -> tuple[dict, dict]:
        digest = "a" * 64
        manifest = {
            "analysis_only": True,
            "experiment": "openvins-reliability-synthesis",
            "figure_hashes": {},
            "input_hashes": {
                f"input_{index}": digest
                for index in range(12)
            },
            "measurement_realization": {
                "camera_fingerprint": "a" * 16,
                "imu_fingerprint": "b" * 16,
            },
            "official_reproduction_manifest_sha256": digest,
            "official_source_modified": False,
            "schema_version": 1,
            "synthesis_config_sha256": digest,
            "upstream_commit": COMMIT,
            "verification": {
                "figures_are_deterministic_svg": True,
                "generated_twice_byte_identical": True,
                "input_hashes_verified": True,
                "no_new_estimator_execution": True,
            },
        }
        results = {
            "cross_experiment_conclusions": {},
            "experiment": "openvins-reliability-synthesis",
            "family_summaries": [
                {
                    "conclusion": "Validated conclusion.",
                    "family": family,
                    "headline_metric": "metric",
                    "headline_value": float(index + 1),
                    "scenario_count": index + 1,
                }
                for index, family in enumerate(FAMILIES)
            ],
            "project_progress": {
                "stage_6_percent": 100,
                "weighted_overall_percent": 100.0,
            },
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

    def test_loads_valid_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            synthesis = load_openvins_reliability_synthesis(
                *self.write(Path(directory))
            )
        self.assertEqual(synthesis.upstream_commit, COMMIT)
        self.assertEqual(len(synthesis.family_summaries), 6)
        self.assertEqual(synthesis.weighted_overall_percent, 100.0)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_openvins_reliability_synthesis(
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
                load_openvins_reliability_synthesis(
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
                load_openvins_reliability_synthesis(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_estimator_execution(self) -> None:
        manifest, results = self.payloads()
        manifest["verification"]["no_new_estimator_execution"] = False

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))

            with self.assertRaises(ValueError):
                load_openvins_reliability_synthesis(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_nondeterministic_generation(self) -> None:
        manifest, results = self.payloads()
        manifest["verification"][
            "generated_twice_byte_identical"
        ] = False

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))

            with self.assertRaises(ValueError):
                load_openvins_reliability_synthesis(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_family_order(self) -> None:
        manifest, results = self.payloads()
        results["family_summaries"][0], results["family_summaries"][1] = (
            results["family_summaries"][1],
            results["family_summaries"][0],
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))

            with self.assertRaises(ValueError):
                load_openvins_reliability_synthesis(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_incomplete_progress(self) -> None:
        manifest, results = self.payloads()
        results["project_progress"]["stage_6_percent"] = 99

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "results.json").write_text(json.dumps(results))

            with self.assertRaises(ValueError):
                load_openvins_reliability_synthesis(
                    root / "manifest.json",
                    root / "results.json",
                )

    def test_rejects_negative_headline(self) -> None:
        with self.assertRaises(ValueError):
            ReliabilityFamilySummary(
                family="visual_dropout",
                scenario_count=6,
                headline_metric="ratio",
                headline_value=-1.0,
                conclusion="Invalid negative value.",
            )


if __name__ == "__main__":
    unittest.main()
