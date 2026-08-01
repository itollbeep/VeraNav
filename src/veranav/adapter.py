"""Estimator adapters for internal experiments and external commands."""

from __future__ import annotations

import math
import string
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from veranav.adapter_io import read_position_trajectory_csv
from veranav.experiment import (
    ExperimentConfig,
    ExperimentResult,
    run_synthetic_experiment,
)
from veranav.trajectory import PositionTrajectory

_ALLOWED_PLACEHOLDERS = {"workspace", "output"}


class AdapterExecutionError(RuntimeError):
    """Raised when an external estimator command cannot produce valid output."""


@dataclass(frozen=True, slots=True, eq=False)
class AdapterRun:
    """Common output from an estimator adapter."""

    estimator_name: str
    estimate: PositionTrajectory
    reference: PositionTrajectory | None

    def __post_init__(self) -> None:
        name = str(self.estimator_name).strip()
        if not name:
            raise ValueError("estimator_name must not be empty")
        if not isinstance(self.estimate, PositionTrajectory):
            raise TypeError("estimate must be a PositionTrajectory")
        if self.reference is not None and not isinstance(
            self.reference,
            PositionTrajectory,
        ):
            raise TypeError("reference must be a PositionTrajectory or None")
        object.__setattr__(self, "estimator_name", name)


@dataclass(frozen=True, slots=True, eq=False)
class CommandAdapterManifest:
    """Executable command manifest without shell interpolation."""

    name: str
    command: tuple[str, ...]
    output_path: str
    timeout_s: float = 600.0

    def __post_init__(self) -> None:
        name = str(self.name).strip()
        if not name:
            raise ValueError("name must not be empty")
        command = tuple(str(token) for token in self.command)
        if not command or any(not token for token in command):
            raise ValueError("command must contain nonempty tokens")
        formatter = string.Formatter()
        for token in command:
            for _, field_name, _, _ in formatter.parse(token):
                if field_name is not None and field_name not in _ALLOWED_PLACEHOLDERS:
                    raise ValueError(f"unsupported command placeholder: {field_name}")
        output_path = str(self.output_path).strip()
        if not output_path:
            raise ValueError("output_path must not be empty")
        if Path(output_path).is_absolute():
            raise ValueError("output_path must be relative to the workspace")
        if ".." in Path(output_path).parts:
            raise ValueError("output_path must not escape the workspace")
        timeout = float(self.timeout_s)
        if not math.isfinite(timeout) or timeout <= 0.0:
            raise ValueError("timeout_s must be finite and strictly positive")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "output_path", output_path)
        object.__setattr__(self, "timeout_s", timeout)


@dataclass(frozen=True, slots=True, eq=False)
class CommandAdapterExecution:
    """Captured external command execution and parsed trajectory."""

    run: AdapterRun
    command: tuple[str, ...]
    stdout: str
    stderr: str
    elapsed_s: float
    output_file: Path

    def __post_init__(self) -> None:
        if not isinstance(self.run, AdapterRun):
            raise TypeError("run must be an AdapterRun")
        command = tuple(str(token) for token in self.command)
        if not command:
            raise ValueError("command must not be empty")
        elapsed = float(self.elapsed_s)
        if not math.isfinite(elapsed) or elapsed < 0.0:
            raise ValueError("elapsed_s must be finite and nonnegative")
        output = Path(self.output_file)
        if not output.is_file():
            raise ValueError("output_file must exist")
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "stdout", str(self.stdout))
        object.__setattr__(self, "stderr", str(self.stderr))
        object.__setattr__(self, "elapsed_s", elapsed)
        object.__setattr__(self, "output_file", output)


def _states_to_trajectory(
    states: tuple,
    source_name: str,
) -> PositionTrajectory:
    timestamps = np.asarray([state.timestamp for state in states], dtype=np.float64)
    positions = np.asarray([state.position_n for state in states], dtype=np.float64)
    return PositionTrajectory(timestamps, positions, source_name)


def run_internal_eskf_adapter(
    config: ExperimentConfig,
    seed: int,
) -> AdapterRun:
    """Run the verified internal ESKF through the common adapter interface."""
    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    result: ExperimentResult = run_synthetic_experiment(config, seed)
    return AdapterRun(
        estimator_name="VeraNav internal ESKF",
        estimate=_states_to_trajectory(result.estimates, "veranav-internal-estimate"),
        reference=_states_to_trajectory(result.truth_states, "synthetic-reference"),
    )


def run_command_adapter(
    manifest: CommandAdapterManifest,
    workspace: str | Path,
) -> CommandAdapterExecution:
    """Run an external estimator command and parse its common-schema output."""
    if not isinstance(manifest, CommandAdapterManifest):
        raise TypeError("manifest must be a CommandAdapterManifest")
    workspace_path = Path(workspace).resolve()
    if not workspace_path.is_dir():
        raise ValueError("workspace must be an existing directory")
    output_file = (workspace_path / manifest.output_path).resolve()
    if workspace_path not in output_file.parents:
        raise ValueError("resolved output path must remain inside the workspace")
    if output_file.exists():
        raise ValueError("expected output path must not already exist")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    values = {"workspace": str(workspace_path), "output": str(output_file)}
    command = tuple(token.format_map(values) for token in manifest.command)
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=workspace_path,
            check=False,
            capture_output=True,
            text=True,
            timeout=manifest.timeout_s,
            shell=False,
        )
    except subprocess.TimeoutExpired as error:
        raise AdapterExecutionError(
            f"adapter command timed out after {manifest.timeout_s:.3f} seconds"
        ) from error
    except OSError as error:
        raise AdapterExecutionError("adapter command could not be started") from error
    elapsed = time.perf_counter() - start

    if completed.returncode != 0:
        raise AdapterExecutionError(
            f"adapter command failed with exit code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    if not output_file.is_file():
        raise AdapterExecutionError("adapter command did not create the expected output")
    try:
        trajectory = read_position_trajectory_csv(
            output_file,
            source_name=manifest.name,
        )
    except ValueError as error:
        raise AdapterExecutionError("adapter output is not a valid common trajectory") from error

    return CommandAdapterExecution(
        run=AdapterRun(manifest.name, trajectory, None),
        command=command,
        stdout=completed.stdout,
        stderr=completed.stderr,
        elapsed_s=elapsed,
        output_file=output_file,
    )


__all__ = [
    "AdapterExecutionError",
    "AdapterRun",
    "CommandAdapterExecution",
    "CommandAdapterManifest",
    "run_command_adapter",
    "run_internal_eskf_adapter",
]
