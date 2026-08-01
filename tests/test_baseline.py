"""Tests for external baseline descriptors."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from veranav.baseline import BaselineDescriptor, load_baseline_descriptor


class BaselineDescriptorTest(unittest.TestCase):
    def payload(self) -> dict:
        return {
            "schema_version": 1,
            "name": "Example",
            "estimator_family": "filter",
            "repository_url": "https://github.com/example/repository",
            "license_id": "GPL-3.0",
            "integration_status": "planned",
            "revision_policy": "Pin an exact commit.",
            "output_schema": "veranav-position-trajectory-v1",
            "candidate_revision": None,
        }

    def test_loads_repository_descriptors(self) -> None:
        root = Path(__file__).resolve().parents[1]
        kf = load_baseline_descriptor(root / "configs/baselines/kf_gins.json")
        ov = load_baseline_descriptor(root / "configs/baselines/openvins.json")
        self.assertEqual(kf.name, "KF-GINS")
        self.assertEqual(ov.name, "OpenVINS")
        self.assertEqual(ov.candidate_revision, "v2.7")
        self.assertEqual(kf.integration_status, "planned")

    def test_accepts_valid_descriptor(self) -> None:
        value = BaselineDescriptor(**self.payload())
        self.assertEqual(value.output_schema, "veranav-position-trajectory-v1")

    def test_rejects_invalid_values(self) -> None:
        for key, value in (
            ("schema_version", 2),
            ("name", ""),
            ("repository_url", "http://example.com/repository"),
            ("integration_status", "done"),
            ("output_schema", "other"),
        ):
            payload = self.payload()
            payload[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                BaselineDescriptor(**payload)

    def test_loader_requires_exact_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "descriptor.json"
            payload = self.payload()
            payload["unexpected"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "keys"):
                load_baseline_descriptor(path)


if __name__ == "__main__":
    unittest.main()
