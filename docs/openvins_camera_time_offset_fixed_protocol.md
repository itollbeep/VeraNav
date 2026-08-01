# OpenVINS fixed versus online time-calibration protocol

## Purpose

The online camera timestamp-offset sweep showed that OpenVINS temporal
calibration converged quickly, while large signed timestamp errors still
increased position error. This paired experiment repeats the same sweep
with online camera-to-IMU time calibration disabled.

The comparison separates raw timing sensitivity from online calibration
compensation.

## Configuration isolation

The official OpenVINS v2.7 configuration remains unchanged. An external
derived copy is created by changing exactly one field:

`calib_cam_timeoffset: true` to `calib_cam_timeoffset: false`

The script verifies that reversing this single substitution reproduces
the official configuration byte for byte.

## Fixed scenarios

The experiment repeats the exact Batch13 scenarios:

- baseline
- -50 ms, -20 ms, -10 ms and -5 ms
- +5 ms, +10 ms, +20 ms and +50 ms

Every scenario uses seed `20260802` and is executed twice.

## Pairing requirements

The experiment is accepted only when:

- each fixed-calibration scenario is byte-identical across two runs
- fixed calibration-aware and nominal-clock reference trajectories are
  byte-identical
- fixed and online experiments have identical raw camera fingerprints
- fixed and online experiments have identical raw IMU fingerprints
- fixed and online experiments have byte-identical physical reference
  trajectories
- the fixed temporal calibration value does not change during a run
- official OpenVINS source files remain unchanged

## Comparison metrics

For every signed offset, the committed result reports:

- fixed-calibration nominal-clock RMSE and maximum error
- fixed-calibration physical-time RMSE and maximum error
- paired online nominal-clock RMSE
- paired online calibration-aware RMSE
- online-to-fixed RMSE ratio
- signed RMSE reduction from online calibration
- RMSE reduction fraction
- fixed and online final temporal-parameter residuals
- parameter residual reduction fraction
- online calibration convergence time

A positive RMSE reduction means online calibration improved position
accuracy relative to the fixed-calibration run. A negative reduction
means the online result was worse for that deterministic scenario.

## Interpretation boundary

This paired comparison uses one deterministic official simulation
trajectory. It isolates online temporal-calibration compensation for the
tested trajectory but does not establish population-level timing
reliability. Additional trajectories and seeds remain necessary.
