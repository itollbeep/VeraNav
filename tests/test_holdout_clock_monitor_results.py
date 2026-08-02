"""Tests for V2-E04 holdout result model."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from veranav.holdout_clock_monitor_results import load_holdout_clock_monitor_results

PREREG = 'c793d14ac3359fa4555178aeb74a4e198b9531d2'
UPSTREAM = '93adc241390d13e99232652cf05cbe18a93c7bea'


class HoldoutClockMonitorResultsTest(unittest.TestCase):
    def write(self, root: Path, status: str = 'holdout_monitor_supported', rows: int = 30):
        progress = (
            {'v1_overall_percent': 100.0, 'v2_stage_4_percent': 40, 'v2_overall_percent': 65.0}
            if status == 'holdout_monitor_supported'
            else {'v1_overall_percent': 100.0, 'v2_stage_4_percent': 0, 'v2_overall_percent': 55.0}
        )
        results = {
            'dynamic_detected_count': 22,
            'experiment': 'openvins-holdout-clock-monitor-validation',
            'holdout_status': status,
            'preregistration_commit': PREREG,
            'primary_challenge_degradation_eligible_count': 4,
            'primary_challenge_detected_count': 4,
            'primary_challenge_positive_lead_count': 4,
            'progress': progress,
            'scenario_count': 30,
            'schema_version': 1,
            'static_false_positive_count': 0,
        }
        manifest = {
            'official_source_modified': False,
            'online_ground_truth_input_count': 0,
            'preregistration_modified': False,
            'schema_version': 1,
            'source_inputs': {'results_sha256': 'a' * 64},
            'upstream_commit': UPSTREAM,
            'verification': {
                'candidate_rule_frozen_before_execution': True,
                'deterministic_replay_verified': True,
                'holdout_seeds_disjoint_from_discovery': True,
                'importer_deterministic': True,
                'monitor_input_boundary_verified': True,
                'threshold_recalibration_performed': False,
            },
        }
        audit = {'scenario_count': 30, 'execution_count': 60}
        paths = [root / name for name in ('results.json', 'manifest.json', 'scenarios.csv', 'audit.json')]
        paths[0].write_text(json.dumps(results))
        paths[1].write_text(json.dumps(manifest))
        with paths[2].open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['scenario_id'])
            writer.writeheader()
            for index in range(rows):
                writer.writerow({'scenario_id': str(index)})
        paths[3].write_text(json.dumps(audit))
        return tuple(paths)

    def test_loads_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            result = load_holdout_clock_monitor_results(*self.write(Path(directory)))
        self.assertEqual(result.v2_overall_percent, 65.0)

    def test_loads_not_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            result = load_holdout_clock_monitor_results(*self.write(Path(directory), 'holdout_monitor_not_supported'))
        self.assertEqual(result.v2_stage_4_percent, 0)

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            load_holdout_clock_monitor_results('/a', '/b', '/c', '/d')

    def test_rejects_wrong_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory))
            payload = json.loads(paths[0].read_text())
            payload['schema_version'] = 2
            paths[0].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_results(*paths)

    def test_rejects_ground_truth_input(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory))
            payload = json.loads(paths[1].read_text())
            payload['online_ground_truth_input_count'] = 1
            paths[1].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_results(*paths)

    def test_rejects_source_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory))
            payload = json.loads(paths[1].read_text())
            payload['official_source_modified'] = True
            paths[1].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_results(*paths)

    def test_rejects_threshold_recalibration(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory))
            payload = json.loads(paths[1].read_text())
            payload['verification']['threshold_recalibration_performed'] = True
            paths[1].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_results(*paths)

    def test_rejects_wrong_row_count(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_results(*self.write(Path(directory), rows=29))

    def test_rejects_evidence_count(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory))
            payload = json.loads(paths[3].read_text())
            payload['execution_count'] = 59
            paths[3].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_results(*paths)

    def test_rejects_supported_progress_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.write(Path(directory))
            payload = json.loads(paths[0].read_text())
            payload['progress']['v2_overall_percent'] = 55.0
            paths[0].write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_holdout_clock_monitor_results(*paths)


if __name__ == '__main__':
    unittest.main()
