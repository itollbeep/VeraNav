"""Tests for committed V2-E02 dynamic clock drift results."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from veranav.dynamic_clock_drift_results import (
    load_dynamic_clock_drift_results,
)

COMMIT = '93adc241390d13e99232652cf05cbe18a93c7bea'


class DynamicClockDriftResultsTest(unittest.TestCase):
    def write(self, root: Path, status: str = 'pilot_supported') -> tuple[Path, Path, Path]:
        audit = {
            'scenario_count': 30,
            'execution_count': 60,
            'schema_version': 1,
        }
        audit_path = root / 'audit.json'
        audit_path.write_text(json.dumps(audit))
        results = {
            'dynamic_cell_count': 24,
            'early_warning_gap_count': 5,
            'estimator_execution_count': 60,
            'pilot_status': status,
            'profile_summary_count': 8,
            'progress': {
                'v1_overall_percent': 100.0,
                'v2_stage_3_percent': 100,
                'v2_overall_percent': 55.0,
            },
            'scenario_count': 30,
            'schema_version': 1,
            'supported_dynamic_cell_count': 7,
        }
        results_path = root / 'results.json'
        results_path.write_text(json.dumps(results))
        results_hash = hashlib.sha256(results_path.read_bytes()).hexdigest()
        audit_hash = hashlib.sha256(audit_path.read_bytes()).hexdigest()
        manifest = {
            'experiment': 'openvins-dynamic-clock-drift-pilot',
            'official_source_modified': False,
            'preregistration_modified': False,
            'results_sha256': results_hash,
            'schema_version': 1,
            'source_inputs': {'evidence_audit_sha256': audit_hash},
            'upstream_commit': COMMIT,
            'verification': {
                'deterministic_replay_verified': True,
                'evidence_audit_verified': True,
                'importer_deterministic': True,
                'preregistration_preceded_execution': True,
            },
        }
        manifest_path = root / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest))
        return manifest_path, results_path, audit_path

    def test_loads_valid_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = load_dynamic_clock_drift_results(*self.write(Path(directory)))
        self.assertEqual(result.scenario_count, 30)
        self.assertEqual(result.v2_overall_percent, 55.0)

    def test_all_statuses(self) -> None:
        for status in ('pilot_supported', 'pilot_partial_support', 'pilot_not_supported'):
            with tempfile.TemporaryDirectory() as directory:
                result = load_dynamic_clock_drift_results(*self.write(Path(directory), status))
            self.assertEqual(result.pilot_status, status)

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_dynamic_clock_drift_results('/missing/a', '/missing/b', '/missing/c')

    def test_rejects_wrong_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest['schema_version'] = 2
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_results(*paths)

    def test_rejects_source_modification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest['official_source_modified'] = True
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_results(*paths)

    def test_rejects_preregistration_modification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest['preregistration_modified'] = True
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_results(*paths)

    def test_rejects_failed_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            manifest = json.loads(paths[0].read_text())
            manifest['verification']['evidence_audit_verified'] = False
            paths[0].write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_results(*paths)

    def test_rejects_bad_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            results = json.loads(paths[1].read_text())
            results['scenario_count'] = 29
            paths[1].write_text(json.dumps(results))
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_results(*paths)

    def test_rejects_audit_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            paths[2].write_text('{}')
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_results(*paths)

    def test_rejects_progress_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write(root)
            results = json.loads(paths[1].read_text())
            results['progress']['v2_overall_percent'] = 54.0
            paths[1].write_text(json.dumps(results))
            with self.assertRaises(ValueError):
                load_dynamic_clock_drift_results(*paths)


if __name__ == '__main__':
    unittest.main()
