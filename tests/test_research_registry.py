"""Tests for the VeraNav v2 research registry."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from veranav.research_registry import (
    CandidateResearchHypothesis,
    VerifiedResearchClaim,
    load_research_registry,
)


COMMIT = "93adc241390d13e99232652cf05cbe18a93c7bea"
CLAIM_IDS = tuple(f"V1-C{index:02d}" for index in range(1, 9))
HYPOTHESIS_IDS = (
    "V2-H01",
    "V2-H02",
    "V2-H03",
    "V2-H04",
    "V2-H05",
    "V2-H06",
)


class ResearchRegistryTest(unittest.TestCase):
    def claim(self, claim_id: str) -> dict:
        return {
            "claim_id": claim_id,
            "evidence_level": "cross_experiment",
            "evidence_paths": ["experiments/example/results.json"],
            "falsification_next_step": "Repeat on another trajectory.",
            "scope": "One deterministic trajectory.",
            "statement": "Evidence-bound statement.",
            "status": "verified_single_trajectory",
            "title": "Verified title",
        }

    def hypothesis(self, hypothesis_id: str) -> dict:
        return {
            "disconfirming_result": "No measurable effect.",
            "expected_information_gain": 4.5,
            "experiment_id": f"V2-E{hypothesis_id[-2:]}",
            "hypothesis": "Testable hypothesis.",
            "hypothesis_id": hypothesis_id,
            "implementation_feasibility": 4.0,
            "novelty_potential": 4.5,
            "practical_relevance": 5.0,
            "priority_score": 4.5,
            "status": "candidate_hypothesis",
            "success_criterion": "A reproducible interaction.",
            "title": "Candidate title",
        }

    def payloads(self) -> tuple[dict, dict, dict]:
        digest = "a" * 64
        manifest = {
            "analysis_only": True,
            "experiment": "veranav-v2-research-registry",
            "measurement_realization": {
                "camera_fingerprint": "a" * 16,
                "imu_fingerprint": "b" * 16,
            },
            "official_source_modified": False,
            "project_progress": {
                "v1_overall_percent": 100.0,
                "v2_overall_percent": 10.0,
                "v2_stage_1_percent": 100,
                "v2_stage_2_percent": 0,
                "v2_stage_3_percent": 0,
                "v2_stage_4_percent": 0,
                "v2_stage_5_percent": 0,
                "v2_stage_6_percent": 0,
            },
            "registry_config_sha256": digest,
            "schema_version": 1,
            "source_inputs": {
                "synthesis_manifest_sha256": digest,
                "synthesis_results_sha256": digest,
            },
            "upstream_commit": COMMIT,
            "verification": {
                "claim_boundaries_recorded": True,
                "generated_twice_byte_identical": True,
                "no_new_estimator_execution": True,
                "source_synthesis_hashes_verified": True,
            },
        }
        claims = {
            "claims": [self.claim(value) for value in CLAIM_IDS],
            "schema_version": 1,
        }
        hypotheses = {
            "hypotheses": [
                self.hypothesis(value)
                for value in HYPOTHESIS_IDS
            ],
            "schema_version": 1,
        }
        return manifest, claims, hypotheses

    def write(self, root: Path) -> tuple[Path, Path, Path]:
        manifest, claims, hypotheses = self.payloads()
        manifest_path = root / "manifest.json"
        claims_path = root / "verified_claims.json"
        hypotheses_path = root / "candidate_hypotheses.json"
        manifest_path.write_text(json.dumps(manifest))
        claims_path.write_text(json.dumps(claims))
        hypotheses_path.write_text(json.dumps(hypotheses))
        return manifest_path, claims_path, hypotheses_path

    def test_loads_valid_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = load_research_registry(
                *self.write(Path(directory))
            )
        self.assertEqual(registry.upstream_commit, COMMIT)
        self.assertEqual(len(registry.verified_claims), 8)
        self.assertEqual(len(registry.candidate_hypotheses), 6)
        self.assertEqual(registry.v2_overall_percent, 10.0)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_research_registry(
                "/missing/manifest.json",
                "/missing/claims.json",
                "/missing/hypotheses.json",
            )

    def test_rejects_wrong_schema(self) -> None:
        manifest, claims, hypotheses = self.payloads()
        manifest["schema_version"] = 2

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "verified_claims.json").write_text(json.dumps(claims))
            (root / "candidate_hypotheses.json").write_text(
                json.dumps(hypotheses)
            )

            with self.assertRaises(ValueError):
                load_research_registry(
                    root / "manifest.json",
                    root / "verified_claims.json",
                    root / "candidate_hypotheses.json",
                )

    def test_rejects_source_modification(self) -> None:
        manifest, claims, hypotheses = self.payloads()
        manifest["official_source_modified"] = True

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "verified_claims.json").write_text(json.dumps(claims))
            (root / "candidate_hypotheses.json").write_text(
                json.dumps(hypotheses)
            )

            with self.assertRaises(ValueError):
                load_research_registry(
                    root / "manifest.json",
                    root / "verified_claims.json",
                    root / "candidate_hypotheses.json",
                )

    def test_rejects_estimator_execution(self) -> None:
        manifest, claims, hypotheses = self.payloads()
        manifest["verification"]["no_new_estimator_execution"] = False

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "verified_claims.json").write_text(json.dumps(claims))
            (root / "candidate_hypotheses.json").write_text(
                json.dumps(hypotheses)
            )

            with self.assertRaises(ValueError):
                load_research_registry(
                    root / "manifest.json",
                    root / "verified_claims.json",
                    root / "candidate_hypotheses.json",
                )

    def test_rejects_claim_order(self) -> None:
        manifest, claims, hypotheses = self.payloads()
        claims["claims"][0], claims["claims"][1] = (
            claims["claims"][1],
            claims["claims"][0],
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "verified_claims.json").write_text(json.dumps(claims))
            (root / "candidate_hypotheses.json").write_text(
                json.dumps(hypotheses)
            )

            with self.assertRaises(ValueError):
                load_research_registry(
                    root / "manifest.json",
                    root / "verified_claims.json",
                    root / "candidate_hypotheses.json",
                )

    def test_rejects_incomplete_v1(self) -> None:
        manifest, claims, hypotheses = self.payloads()
        manifest["project_progress"]["v1_overall_percent"] = 99.0

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "verified_claims.json").write_text(json.dumps(claims))
            (root / "candidate_hypotheses.json").write_text(
                json.dumps(hypotheses)
            )

            with self.assertRaises(ValueError):
                load_research_registry(
                    root / "manifest.json",
                    root / "verified_claims.json",
                    root / "candidate_hypotheses.json",
                )

    def test_rejects_invalid_claim_status(self) -> None:
        with self.assertRaises(ValueError):
            VerifiedResearchClaim(
                claim_id="V1-C01",
                title="Title",
                status="candidate_hypothesis",
                evidence_level="cross_experiment",
                statement="Statement",
                scope="Scope",
                evidence_paths=("path",),
                falsification_next_step="Repeat.",
            )

    def test_rejects_invalid_hypothesis_score(self) -> None:
        with self.assertRaises(ValueError):
            CandidateResearchHypothesis(
                hypothesis_id="V2-H01",
                title="Title",
                status="candidate_hypothesis",
                hypothesis="Hypothesis",
                experiment_id="V2-E01",
                novelty_potential=6.0,
                expected_information_gain=5.0,
                practical_relevance=5.0,
                implementation_feasibility=4.0,
                priority_score=5.0,
                success_criterion="Success",
                disconfirming_result="Disconfirming result",
            )

    def test_rejects_wrong_hypothesis_order(self) -> None:
        manifest, claims, hypotheses = self.payloads()
        hypotheses["hypotheses"][0], hypotheses["hypotheses"][1] = (
            hypotheses["hypotheses"][1],
            hypotheses["hypotheses"][0],
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "verified_claims.json").write_text(json.dumps(claims))
            (root / "candidate_hypotheses.json").write_text(
                json.dumps(hypotheses)
            )

            with self.assertRaises(ValueError):
                load_research_registry(
                    root / "manifest.json",
                    root / "verified_claims.json",
                    root / "candidate_hypotheses.json",
                )


if __name__ == "__main__":
    unittest.main()
