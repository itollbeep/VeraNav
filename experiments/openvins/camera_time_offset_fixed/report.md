# OpenVINS fixed versus online time-calibration comparison

## Purpose

This paired experiment repeats the signed camera timestamp-offset sweep
with OpenVINS online camera-to-IMU time calibration disabled. It is
compared directly with the committed online-calibration experiment.

The fixed OpenVINS configuration is derived from the official v2.7
configuration by changing exactly one entry:

`calib_cam_timeoffset: true` to `calib_cam_timeoffset: false`

Official OpenVINS source files and the official configuration remain
unchanged.

## Pairing

The same nine scenarios and seed are used: baseline and ±5 ms, ±10 ms,
±20 ms and ±50 ms.

All fixed-calibration scenarios are run twice. Their raw camera and IMU
measurement fingerprints must match the online-calibration experiment.
Physical-time reference trajectories must be byte-identical between
online and fixed runs.

With temporal calibration fixed, the calibration-aware and nominal
reference trajectories must be byte-identical.

## Results

| Scenario | Injected offset (ms) | Fixed-calibration RMSE (m) | Online calibration-aware RMSE (m) | Online/fixed RMSE ratio | Online RMSE reduction fraction | Fixed parameter residual (ms) | Online parameter residual (ms) | Parameter residual reduction fraction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.0 | 0.059438 | 0.045412 | 0.764 | 0.236 | 0.000 | -0.004 | n/a |
| neg-50ms | -50.0 | 78648.117016 | 0.236079 | 0.000 | 1.000 | -50.000 | -0.010 | 1.000 |
| neg-20ms | -20.0 | 43239.349212 | 0.068386 | 0.000 | 1.000 | -20.000 | -0.005 | 1.000 |
| neg-10ms | -10.0 | 3620.021828 | 0.032615 | 0.000 | 1.000 | -10.000 | -0.005 | 0.999 |
| neg-5ms | -5.0 | 6341.918785 | 0.052268 | 0.000 | 1.000 | -5.000 | -0.004 | 0.999 |
| pos-5ms | 5.0 | 10174.163393 | 0.050611 | 0.000 | 1.000 | 5.000 | -0.004 | 0.999 |
| pos-10ms | 10.0 | 3212.576139 | 0.047967 | 0.000 | 1.000 | 10.000 | -0.006 | 0.999 |
| pos-20ms | 20.0 | 73766.183858 | 0.072959 | 0.000 | 1.000 | 20.000 | -0.007 | 1.000 |
| pos-50ms | 50.0 | 232422.804409 | 0.321500 | 0.000 | 1.000 | 50.000 | -0.006 | 1.000 |

A positive RMSE reduction fraction means online temporal calibration
reduced position RMSE relative to the paired fixed-calibration run. A
negative value means the online-calibration trajectory had higher RMSE
for that deterministic scenario.

Parameter residual reduction measures how much of the fixed temporal
mismatch was removed by online estimation. Baseline has no injected
mismatch, so that fraction is not defined.

## Interpretation boundary

This experiment separates online calibration compensation from fixed
temporal mismatch on one deterministic official simulation trajectory.
Non-monotonic position RMSE remains possible because filter update
history and trajectory dynamics are deterministic. Population-level
timing reliability requires additional trajectories and seeds.

The derived configuration, GPL-linked runner, raw trajectories and logs
remain outside the Apache-2.0 VeraNav repository.
