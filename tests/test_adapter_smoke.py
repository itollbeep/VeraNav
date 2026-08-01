"""CLI smoke test for the common estimator adapter boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AdapterSmokeTest(unittest.TestCase):
    def test_cli_writes_repeatable_common_schema_outputs(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        script = repository / "scripts/run_adapter_smoke.py"
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(repository / "src")
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            for output in (first, second):
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(script),
                        "--output-dir",
                        output,
                        "--seed",
                        "3",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    env=environment,
                    timeout=30.0,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn("adapter=VeraNav internal ESKF", completed.stdout)
            for name in ("estimate.csv", "reference.csv", "summary.json"):
                self.assertEqual(
                    (Path(first) / name).read_bytes(),
                    (Path(second) / name).read_bytes(),
                )
            payload = json.loads((Path(first) / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["seed"], 3)
            self.assertGreater(payload["sample_count"], 2)


if __name__ == "__main__":
    unittest.main()
