# VeraNav V0.1 Architecture

VeraNav V0.1 is planned as a Python-first framework for evaluating navigation state estimators under controlled sensor degradation and fault scenarios.

## Planned Module Boundaries

### Trajectory generation

Produces deterministic ground-truth motion trajectories with explicit timestamps, coordinate frames, and physical units.

### IMU simulation

Generates synthetic accelerometer and gyroscope measurements from approved motion and sensor-error models.

### GNSS simulation

Generates position measurements and associated uncertainty information using approved coordinate-frame and noise conventions.

### Fault injection

Applies reproducible sensor degradation and fault scenarios without modifying the underlying estimator implementation.

### Minimal ESKF

Provides the initial error-state Kalman filter reference implementation after its state definition and mathematical conventions have been approved.

### Estimator interface

Defines a common boundary for supplying measurements and collecting state estimates, covariance information, innovations, and health indicators.

### Metrics

Computes trajectory accuracy and statistical consistency metrics, including trajectory error, NIS, and NEES.

### Experiment runner

Loads configuration, initializes deterministic random seeds, executes experiments, and records provenance.

### Reporting

Produces reproducible machine-readable results and human-readable summaries from completed experiments.

## Current Status

No estimator, simulator, fault model, metric implementation, or experiment runner has been implemented yet.

Before estimator implementation begins, the following scientific conventions must be explicitly reviewed and approved:

- navigation and sensor coordinate frames
- rotation-matrix direction
- quaternion ordering and multiplication convention
- state-vector ordering
- nominal-state and error-state definitions
- perturbation convention
- error-injection and reset convention
- covariance ordering and dimensions
- timestamp and synchronization conventions
- physical units

External estimators must remain in separate upstream repositories or run as independent processes. Their source code must not be copied into VeraNav without a compatible license and explicit approval.

Generated datasets, logs, plots, reports, caches, and experiment outputs are not source files and must not be committed unless explicitly approved.
