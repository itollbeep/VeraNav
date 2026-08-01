# OpenVINS visual-outage timing-sensitivity protocol

## Purpose

The fixed-window visual-dropout experiment found that a 3 s outage
starting 30 s after the first processed camera frame produced an
overall position RMSE close to baseline. This follow-up tests whether
that behavior depends on the trajectory segment in which the outage
occurs.

## Fixed design

The verified external OpenVINS v2.7 visual-dropout runner is reused
without recompilation or source changes.

Complete visual-observation outages are injected at elapsed times:

- 30 s
- 90 s
- 150 s
- 210 s

At each start time, two durations are tested:

- 1 s
- 3 s

A no-degradation baseline is included, giving nine scenarios. Every
scenario is executed twice.

## Injection boundary

During a selected outage, camera timestamps and camera identifiers are
preserved, while each camera feature vector is replaced with an empty
vector before `feed_measurement_simulation`. The IMU stream, simulator
trajectory and estimator schedule remain unchanged.

## Pairing requirements

The experiment is accepted only when:

- each scenario's two estimate trajectories are byte-identical
- each scenario's two reference trajectories are byte-identical
- each scenario's two degradation summaries are byte-identical
- all nine scenarios share the same byte-identical reference trajectory
- the runner source, CMake file and binary match the previously committed
  visual-dropout evidence

## Metrics

The audit reports full-run position error together with local metrics:

- 10 s pre-outage RMSE
- outage RMSE
- 10 s post-outage RMSE
- outage plus 10 s post-window RMSE and peak error
- ratios against the matched baseline time window
- peak positive error excess
- positive error-excess integral through 30 s after outage end
- recovery time

Recovery is defined as the first post-outage time at which the rolling
1 s RMSE of positive position-error excess over baseline stays below
10% of the full-run baseline RMSE for 3 s. Recovery is searched within
30 s after outage end.

## Interpretation boundary

This protocol isolates outage timing on one deterministic official
simulation trajectory. It can establish trajectory-location
sensitivity, but it is not a population-level reliability study.
Additional trajectories, seeds and cross-estimator paired experiments
remain necessary.
