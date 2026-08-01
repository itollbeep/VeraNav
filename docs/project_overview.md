# VeraNav project overview

## Research question

Navigation estimators are often compared with nominal RMSE values. That comparison does not identify the degradation conditions under which an estimator becomes inconsistent or fails. VeraNav asks a more operational question:

> For a specified estimator, scenario, fault model, failure rule, and uncertainty requirement, where is the boundary between reliable and unreliable operation?

## What is standard

VeraNav deliberately implements standard state-estimation components in a transparent form:

- error-state Kalman filtering
- IMU mechanization
- covariance propagation
- GNSS position updates
- NIS and NEES
- Monte Carlo simulation

These components are not presented as new algorithms. Their role is to provide a controlled, inspectable estimator for validating the reliability framework.

## What differentiates VeraNav

### Paired degradation experiments

Each degraded run shares its random seed with a baseline run. IMU noise, GNSS noise, and initial perturbations are therefore paired. The resulting RMSE and maximum-error differences are not confounded by independently sampled noise realizations.

### Structured degradation coordinates

Faults are represented by explicit parameters such as start time, duration, direction, and magnitude. This makes a degradation experiment reproducible and allows the same coordinate to be applied to different estimators.

### Uncertainty-aware reliability decisions

Run failures are aggregated into Monte Carlo failure rates. Wilson intervals quantify binomial uncertainty. Paired bootstrap intervals quantify uncertainty in baseline-to-degraded metric differences.

### Adaptive boundary search

A uniformly dense degradation grid spends many evaluations far from the transition. VeraNav evaluates the ends of a fault range and bisects only when they bracket a reliable-to-unreliable transition. The result includes a lower reliable value, an upper unreliable value, and the unresolved bracket width.

### Deterministic evidence

One command writes machine-readable JSON, tabular CSV, a concise Markdown report, and deterministic SVG figures. Fixed seeds and stable serialization make the evidence suitable for regression testing and estimator-to-estimator comparison.

## Current evidence

V0.1 contains a synthetic circular trajectory, an internal ESKF, GNSS outage, and GNSS position bias. The committed quick study verifies that the framework can:

- reproduce sensor data and estimator results
- compare paired baseline and degraded runs
- calculate confidence intervals
- locate a reliability transition
- export the same report byte-for-byte
- render the same figures without a plotting dependency

This evidence demonstrates implementation correctness and workflow reproducibility. It does not establish real-world superiority.

## Claims that VeraNav does not make

VeraNav V0.1 does not claim:

- a new Kalman-filter derivation
- certified integrity monitoring
- field-validated failure probabilities
- platform-independent reliability limits
- superiority over existing navigation systems
- readiness for safety-critical deployment

## Research path

The framework becomes a stronger research contribution when the same protocol is applied to multiple estimator families and realistic degradations. Priority extensions are:

1. Add external estimator adapters without copying their source code.
2. Compare filter-based and optimization-based estimators with common scenarios.
3. Add time offset, calibration error, IMU drift, multipath-like bias, and intermittent measurement corruption.
4. Estimate two-dimensional and higher-dimensional reliability surfaces.
5. Validate boundary stability against larger seed sets and confidence-bound decision rules.
6. Replay public and collected datasets with reproducible fault injection.
7. Analyze recovery time, first-failure time, and failure-mode transitions.

## Mentor-facing summary

VeraNav should be described as:

> An estimator-agnostic framework for paired, uncertainty-aware reliability evaluation of multisensor navigation under structured degradation.

The internal ESKF is the first verified adapter, not the final research contribution. The principal contribution is the experiment protocol and the reliability-boundary representation.
