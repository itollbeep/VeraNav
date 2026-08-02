# Changelog

All notable changes to VeraNav are documented in this file.

## 0.1.0 development milestone — 2026-08-01

### Added

- explicit NED, FRD, quaternion, perturbation, and error-state conventions
- quaternion and rotation utilities
- immutable nominal state and IMU samples
- midpoint nominal IMU propagation
- continuous ESKF error dynamics
- Van Loan covariance discretization
- GNSS position measurement and Joseph covariance update
- right-error injection and attitude covariance reset
- NIS and NEES consistency metrics
- deterministic circular trajectory, IMU, and GNSS simulation
- structured GNSS outage and position-bias degradation
- Monte Carlo failure analysis and fixed-grid reliability envelopes
- paired common-random-number comparison
- percentile bootstrap and Wilson confidence intervals
- adaptive reliability-boundary search
- deterministic JSON, CSV, Markdown, and SVG reports
- unit, numerical, reproducibility, and continuous-integration checks

### Scope

This milestone is a synthetic verification framework. It is not a real-world benchmark, integrity-certified navigation system, or safety-critical product.

## KF-GINS official demo reproduction

- Added WGS84 ECEF and anchor-centred NED conversion utilities.
- Added an audited KF-GINS result importer with safe zero-week inference.
- Added duplicate truth timestamp consolidation and spatial-radius rejection.
- Added deterministic JSON, CSV and Markdown reproduction evidence.
- Added geodesy and KF-GINS integration tests.

## OpenVINS v2.7 ROS-free baseline

- Pinned official OpenVINS v2.7 at `93adc241390d13e99232652cf05cbe18a93c7bea`.
- Built the ROS-free simulator in an isolated compatibility toolchain.
- Passed `test_sim_repeat`, `test_sim_meas`, and two independent
  `run_simulation` executions.
- Added strict committed evidence loading and validation.

## OpenVINS simulation adapter

- Added a deterministic external OpenVINS v2.7 position adapter.
- Recorded estimated and simulated reference trajectories in the
  VeraNav common schema.
- Added a strict import record, baseline metrics and validation tests.
- Kept GPL-linked source and binaries outside the Apache-2.0 repository.

## OpenVINS visual-observation dropout

- Added an external deterministic OpenVINS visual-observation loss
  runner.
- Evaluated baseline, three random whole-frame loss rates and two
  continuous visual outages.
- Added paired-reference verification, common-schema metrics and strict
  committed evidence validation.
- Preserved the official OpenVINS source tree and kept GPL-linked code
  outside the repository.

## OpenVINS visual-outage timing sensitivity

- Reused the verified OpenVINS visual-dropout runner without changes.
- Evaluated 1 s and 3 s complete visual outages at four trajectory
  locations.
- Added matched-window RMSE, peak-error, positive excess-area and
  recovery-time metrics.
- Required deterministic replay and byte-identical paired references.

## OpenVINS camera timestamp offsets

- Added a deterministic external camera timestamp-offset runner.
- Evaluated baseline and eight signed offsets from 5 ms to 50 ms.
- Verified common camera and IMU measurement realizations with
  fingerprints.
- Added nominal-clock, calibration-aware and physical-time errors.
- Added online temporal-calibration residual and convergence metrics.

## OpenVINS fixed time calibration comparison

- Derived an external OpenVINS configuration with temporal calibration
  disabled by one audited field change.
- Repeated the nine signed timestamp-offset scenarios twice.
- Enforced measurement fingerprints and physical references shared with
  the online-calibration experiment.
- Added per-scenario RMSE and temporal-parameter compensation metrics.

## OpenVINS fixed-time divergence diagnostics

- Added analysis-only diagnostics for the fixed temporal-calibration
  trajectories.
- Added first 1 m, 10 m, 100 m and 1000 m crossing times.
- Added sustained failure, recovery and service-availability metrics.
- Added error quantiles and top squared-error concentration measures.
- Added broad-failure and catastrophic-divergence classifications.

## OpenVINS IMU-noise degradation

- Added a GPL-isolated dual-simulator IMU-noise runner.
- Evaluated white noise, bias random walk and combined degradation at
  2×, 5× and 10× nominal magnitude.
- Preserved the official nominal estimator noise model.
- Verified common camera observations and nominal IMU realization.
- Added position covariance, NEES and service-availability metrics.
