"""Tests for internal and external estimator adapters."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from veranav.adapter import (
    AdapterExecutionError,
    AdapterRun,
    CommandAdapterManifest,
    run_command_adapter,
    run_internal_eskf_adapter,
)
from veranav.experiment import ExperimentConfig
from veranav.simulation import CircularTrajectoryConfig
from veranav.trajectory import PositionTrajectory, evaluate_position_trajectory


class InternalAdapterTest(unittest.TestCase):
    def test_internal_adapter_is_deterministic_and_evaluable(self) -> None:
        config = ExperimentConfig(
            trajectory=CircularTrajectoryConfig(
                duration_s=1.0,
                imu_dt=0.02,
                gnss_dt=0.2,
            )
        )
        first = run_internal_eskf_adapter(config, 7)
        second = run_internal_eskf_adapter(config, 7)
        np.testing.assert_array_equal(first.estimate.positions_n_m, second.estimate.positions_n_m)
        self.assertIsNotNone(first.reference)
        evaluation = evaluate_position_trajectory(first.reference, first.estimate)
        self.assertEqual(evaluation.metrics.sample_count, first.estimate.timestamps_s.size)
        self.assertGreaterEqual(evaluation.metrics.position_rmse_m, 0.0)

    def test_adapter_run_validation(self) -> None:
        trajectory = PositionTrajectory([0.0, 1.0], np.zeros((2, 3)), "x")
        with self.assertRaises(ValueError):
            AdapterRun("", trajectory, None)
        with self.assertRaises(TypeError):
            AdapterRun("x", "bad", None)
        with self.assertRaises(TypeError):
            run_internal_eskf_adapter("bad", 0)


class CommandAdapterTest(unittest.TestCase):
    def _writer_script(self, root: Path) -> Path:
        script = root / "writer.py"
        script.write_text(
            "from pathlib import Path\n"
            "import sys\n"
            "Path(sys.argv[1]).write_text(\n"
            "    \"timestamp_s,north_m,east_m,down_m\\n\"\n"
            "    \"0,0,0,0\\n\"\n"
            "    \"1,1,2,3\\n\",\n"
            "    encoding=\"utf-8\",\n"
            ")\n"
            "print(\"writer complete\")\n",
            encoding="utf-8",
        )
        return script

    def test_runs_command_without_shell_and_parses_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self._writer_script(root)
            manifest = CommandAdapterManifest(
                name="mock estimator",
                command=(sys.executable, str(script), "{output}"),
                output_path="results/trajectory.csv",
                timeout_s=5.0,
            )
            result = run_command_adapter(manifest, root)
            self.assertEqual(result.run.estimator_name, "mock estimator")
            self.assertEqual(result.run.estimate.positions_n_m[-1, 2], 3.0)
            self.assertIn("writer complete", result.stdout)
            self.assertTrue(result.output_file.is_file())
            self.assertEqual(result.command[-1], str(result.output_file))

    def test_rejects_nonzero_exit_missing_output_and_bad_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            failing = CommandAdapterManifest(
                "fail",
                (sys.executable, "-c", "import sys; sys.exit(3)"),
                "out.csv",
                5.0,
            )
            with self.assertRaisesRegex(AdapterExecutionError, "exit code 3"):
                run_command_adapter(failing, root)

            missing = CommandAdapterManifest(
                "missing",
                (sys.executable, "-c", "print('no output')"),
                "missing.csv",
                5.0,
            )
            with self.assertRaisesRegex(AdapterExecutionError, "did not create"):
                run_command_adapter(missing, root)

            bad = root / "bad.py"
            bad.write_text(
                "from pathlib import Path\nimport sys\nPath(sys.argv[1]).write_text('bad\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            invalid = CommandAdapterManifest(
                "invalid",
                (sys.executable, str(bad), "{output}"),
                "invalid.csv",
                5.0,
            )
            with self.assertRaisesRegex(AdapterExecutionError, "not a valid"):
                run_command_adapter(invalid, root)

    def test_timeout_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = CommandAdapterManifest(
                "slow",
                (sys.executable, "-c", "import time; time.sleep(1)"),
                "out.csv",
                0.05,
            )
            with self.assertRaisesRegex(AdapterExecutionError, "timed out"):
                run_command_adapter(manifest, directory)

    def test_manifest_rejects_unsafe_values(self) -> None:
        invalid_cases = (
            {"name": "", "command": ("x",), "output_path": "out.csv"},
            {"name": "x", "command": (), "output_path": "out.csv"},
            {"name": "x", "command": ("{unknown}",), "output_path": "out.csv"},
            {"name": "x", "command": ("x",), "output_path": "/tmp/out.csv"},
            {"name": "x", "command": ("x",), "output_path": "../out.csv"},
            {"name": "x", "command": ("x",), "output_path": "out.csv", "timeout_s": 0.0},
        )
        for arguments in invalid_cases:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                CommandAdapterManifest(**arguments)

    def test_rejects_missing_workspace_existing_output_and_invalid_manifest_type(self) -> None:
        manifest = CommandAdapterManifest("x", ("x",), "out.csv")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                run_command_adapter(manifest, root / "missing")
            (root / "out.csv").write_text("stale", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "already exist"):
                run_command_adapter(manifest, root)
            with self.assertRaises(TypeError):
                run_command_adapter("bad", directory)


if __name__ == "__main__":
    unittest.main()
