# OpenVINS visual-observation dropout protocol

## Purpose

This experiment measures how the pinned OpenVINS v2.7 ROS-free
simulation baseline responds when complete camera feature sets become
unavailable.

## Injection boundary

The external GPL-linked runner mirrors the official simulation loop.
For a selected camera timestamp, it keeps the camera message time and
camera identifiers but replaces every camera feature vector with an
empty vector before calling `feed_measurement_simulation`.

This represents complete visual-observation loss while preserving the
IMU stream, camera clock and estimator execution schedule. Official
OpenVINS source files and the official configuration are not edited.

## Fixed scenarios

- baseline
- Bernoulli whole-frame observation loss with probabilities 0.10, 0.30
  and 0.50
- continuous whole-frame observation loss for 1 s and 3 s beginning
  30 s after the first processed camera frame

All random scenarios use seed `20260801`.

## Pairing and determinism

Every scenario is executed twice. The estimate trajectory, reference
trajectory and runner summary must be byte-identical across the two
executions. The reference trajectory must also be byte-identical across
all six scenarios.

This keeps the underlying trajectory and sensor realization fixed, so
reported changes are attributable to the configured visual-observation
loss.

## Metrics

The committed record reports:

- realized frame-loss fraction
- dropped observation count
- aligned position RMSE
- mean position error
- maximum position error
- RMSE and maximum-error changes relative to baseline
- baseline-normalized RMSE and maximum-error ratios

## Interpretation limit

This is a deterministic sensitivity sweep using one official simulator
configuration. It is not a Monte Carlo confidence study and does not
define a formal reliability boundary. Additional seeds, trajectories,
degradation start times and cross-estimator comparisons are required
for population-level conclusions.
