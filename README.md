# VeraNav
A reproducible framework for evaluating the reliability of navigation state estimators under sensor degradation and faults.


## Current Status

VeraNav is currently at the V0.1 scaffold stage. The repository contains the initial Python package, tests, and documentation boundaries.

No navigation estimator, sensor simulator, fault model, dataset, benchmark result, or production-ready component has been implemented yet.

## V0.1 Scope

The planned V0.1 scope includes deterministic trajectory and IMU simulation, GNSS position updates, GNSS outage and bias injection, a minimal ESKF, trajectory error metrics, NIS and NEES consistency metrics, deterministic Monte Carlo experiments, automated tests, and reproducible reports.

## Repository Structure

- `src/veranav/`: reusable package code
- `tests/`: automated tests
- `configs/`: experiment configurations
- `data/`: local-only data
- `docs/`: architecture and scientific conventions
- `experiments/`: experiment definitions
- `scripts/`: reproducible command-line entry points

## Development

Primary environment: Ubuntu 22.04 under WSL2 with Python 3.10.

Create the local virtual environment and run the validation commands with:

    python3 -m venv .venv
    PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
    PYTHONPATH=src .venv/bin/python -m compileall -q src tests

## Benchmark Results

No benchmark results currently exist. No performance, consistency, fault-detection, or recovery claim should be made before implementation and reproducible validation.
