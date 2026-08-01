from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from veranav.openvins import (
    OpenVinsReproductionEvidence,
    load_openvins_evidence,
)


class OpenVinsEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        digest = "a" * 64
        self.manifest = {
            "schema_version": 1,
            "estimator": "OpenVINS",
            "reproduction_scope": (
                "official-v2.7-ros-free-simulator"
            ),
            "upstream": {
                "release_tag": "v2.7",
                "commit": "b" * 40,
                "source_archive_sha256": digest,
            },
            "configuration": {
                "sha256": digest,
                "enable_ros": False,
                "official_configuration_modified": False,
            },
            "build": {
                "environment_profile": (
                    "official-era-opencv-4.5"
                ),
                "host_system_packages_modified": False,
            },
            "verification": {
                "test_sim_repeat": {
                    "status": "PASS",
                    "required_marker": (
                        "success! they all are the same!"
                    ),
                },
                "test_sim_meas": {"status": "PASS"},
                "run_simulation_a": {"status": "PASS"},
                "run_simulation_b": {"status": "PASS"},
                "official_source_modified": False,
            },
        }

    def write_manifest(self, root: Path) -> Path:
        path = root / "manifest.json"
        path.write_text(
            json.dumps(self.manifest),
            encoding="utf-8",
        )
        return path

    def test_loads_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = load_openvins_evidence(
                self.write_manifest(Path(directory))
            )

        self.assertEqual(evidence.release_tag, "v2.7")
        self.assertEqual(evidence.upstream_commit, "b" * 40)

    def test_rejects_wrong_release(self) -> None:
        self.manifest["upstream"]["release_tag"] = "master"

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                load_openvins_evidence(
                    self.write_manifest(Path(directory))
                )

    def test_rejects_failed_simulation(self) -> None:
        self.manifest["verification"]["run_simulation_b"][
            "status"
        ] = "FAIL"

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                load_openvins_evidence(
                    self.write_manifest(Path(directory))
                )

    def test_rejects_source_modification(self) -> None:
        self.manifest["verification"][
            "official_source_modified"
        ] = True

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                load_openvins_evidence(
                    self.write_manifest(Path(directory))
                )

    def test_rejects_invalid_hash(self) -> None:
        with self.assertRaises(ValueError):
            OpenVinsReproductionEvidence(
                release_tag="v2.7",
                upstream_commit="b" * 40,
                source_archive_sha256="bad",
                configuration_sha256="a" * 64,
                environment_profile="stable",
                repeatability_marker=(
                    "success! they all are the same!"
                ),
            )

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_openvins_evidence(
                "/missing/openvins-manifest.json"
            )


if __name__ == "__main__":
    unittest.main()
