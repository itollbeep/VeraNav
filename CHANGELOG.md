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

## OpenVINS reliability synthesis

- Consolidated six committed OpenVINS reliability experiment families.
- Added a deterministic cross-experiment manifest, JSON result set and
  compact CSV summary.
- Added four dependency-free SVG figures for visual dropout, temporal
  calibration, divergence onset and IMU-noise consistency.
- Added the final VeraNav v1 progress and completion record.
- Marked all six fixed project stages complete.

## VeraNav v2 research registry

- Preserved eight evidence-bound VeraNav v1 conclusions.
- Added six preregistered v2 research hypotheses with explicit
  disconfirming criteria.
- Ranked the v2 experiments by novelty potential, information gain,
  practical relevance and feasibility.
- Preregistered a 12-scenario temporal-calibration and visual-dropout
  interaction pilot.
- Added fixed VeraNav v2 stage weights and progress tracking.


## Temporal-visual interaction pilot

- Added the 12-scenario `V2-E01` factorial interaction experiment.
- Used shared nested dropout masks across temporal offsets.
- Reproduced both committed v1 single-factor experiment families.
- Added additive and multiplicative interaction contrasts.
- Recorded pilot status `pilot_supported` in the novelty ledger.
- Advanced VeraNav v2 cross-factor stage to 40% and overall to 20.0%.


## V2-E01b replication preregistration

- Refined the mechanism from calibration failure to low-dropout
  trajectory-error coupling.
- Added a symmetric five-offset, five-dropout and five-seed design.
- Collapsed deterministic zero-dropout duplicates to 105 physical
  scenarios.
- Preregistered 134 estimator executions and a strict replicated
  two-metric criterion.
- Kept VeraNav v2 progress unchanged before new evidence is generated.


## V2-E01b five-seed replication result

- Executed 105 physical scenarios and 134 OpenVINS runs.
- Verified five distinct nested-dropout masks with identical raw
  camera, IMU and physical-reference evidence.
- Added 80 seed-level interactions and 16 preregistered cell summaries.
- Recorded replication status `replicated_supported` without suppressing null or
  antagonistic cells.
- Completed the VeraNav v2 cross-factor interaction stage and advanced
  v2 overall progress to 35.0%.


## V2-E02 dynamic clock drift preregistration

- Added bounded linear, sinusoidal and piecewise-random-walk clock drift
  profiles.
- Added matched static controls and clean versus 10% dropout conditions.
- Preregistered 30 scenarios and 60 estimator executions.
- Added dynamic tracking RMSE, lag and early-warning-gap outcomes.
- Kept VeraNav v2 progress unchanged until estimator evidence exists.

## V2-E02 dynamic clock drift result

- Executed 30 preregistered scenarios twice for 60 OpenVINS runs.
- Evaluated global, local and temporal-tracking degradation.
- Recorded pilot status `pilot_supported`.
- Recorded `2` early-warning-gap cells.
- Completed VeraNav v2 stage 3 and advanced overall v2 progress to 55.0%.


## V2-E03 internal clock monitor preregistration

- Defined two slow-sinusoidal early-warning positives.
- Restricted monitor inputs to estimator timestamps and estimated time
  offset.
- Added causal velocity, acceleration and range channels.
- Calibrated thresholds exclusively from six static controls.
- Added lead-time and static false-positive criteria.
- Kept VeraNav v2 progress unchanged before monitoring analysis.

## V2-E03 internal clock monitor result

- Evaluated the causal three-channel monitor on all 30 V2-E02 evidence
  scenarios.
- Calibrated thresholds only from six static controls.
- Recorded static false positives, primary early-warning lead times and
  secondary dynamic coverage.
- Result status: `monitor_not_supported`.
- Kept injected clock target and trajectory truth out of online monitor
  inputs.


## V2-E04 holdout clock monitor preregistration

- Preserved the negative V2-E03 monitor result.
- Froze the 5 s peak-to-peak feature, original threshold and 3 s
  persistence rule.
- Prohibited threshold recalibration.
- Added disjoint sinusoidal phases, random-walk seeds and dropout seed.
- Preregistered 30 holdout scenarios and 60 deterministic executions.
- Kept VeraNav v2 progress unchanged before validation.
