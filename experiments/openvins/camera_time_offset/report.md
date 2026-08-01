# OpenVINS camera timestamp-offset experiment

## Purpose

This deterministic sweep evaluates constant camera timestamp biases
with the official OpenVINS v2.7 simulation configuration. The official
configuration enables online camera-to-IMU time-offset calibration.

Positive injection means that a camera measurement is reported later
than its physical acquisition time. For an injected offset `delta`, the
consistent camera-to-IMU calibration target is:

`target = true_camera_to_imu_offset - delta`

Nine scenarios are evaluated: baseline and ±5 ms, ±10 ms, ±20 ms and
±50 ms timestamp biases. Each scenario is executed twice.

## Pairing and determinism

The runner hashes the raw simulated camera observations and IMU
measurements before injecting the timestamp bias. All scenarios must
have identical camera and IMU fingerprints. Physical-time reference
trajectories must also be byte-identical across scenarios.

Estimate, reference, calibration and summary files must be
byte-identical across the two executions of each scenario.

## Error views

Three position-error views are retained:

- nominal-clock error: ground truth at the reported camera timestamp
  plus the simulator true camera-to-IMU offset
- calibration-aware error: ground truth at the reported camera
  timestamp plus the filter's current estimated camera-to-IMU offset
- physical-time error: ground truth at the original physical
  acquisition time

The nominal-clock view represents downstream use that assumes the
nominal time mapping. The calibration-aware view measures the internal
state after applying OpenVINS online temporal calibration.

## Results

| Scenario | Injected offset (ms) | Nominal-clock RMSE (m) | Calibration-aware RMSE (m) | Final estimated offset (ms) | Target offset (ms) | Final residual (ms) | Calibration convergence (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.0 | 0.045411 | 0.045412 | -0.004 | 0.000 | -0.004 | 0.500 |
| neg-50ms | -50.0 | 0.242168 | 0.236079 | 49.990 | 50.000 | -0.010 | 2.000 |
| neg-20ms | -20.0 | 0.071582 | 0.068386 | 19.995 | 20.000 | -0.005 | 0.500 |
| neg-10ms | -10.0 | 0.033675 | 0.032615 | 9.995 | 10.000 | -0.005 | 0.600 |
| neg-5ms | -5.0 | 0.052831 | 0.052268 | 4.996 | 5.000 | -0.004 | 0.600 |
| pos-5ms | 5.0 | 0.050933 | 0.050611 | -5.004 | -5.000 | -0.004 | 0.500 |
| pos-10ms | 10.0 | 0.048936 | 0.047967 | -10.006 | -10.000 | -0.006 | 0.500 |
| pos-20ms | 20.0 | 0.075598 | 0.072959 | -20.007 | -20.000 | -0.007 | 0.400 |
| pos-50ms | 50.0 | 0.326100 | 0.321500 | -50.006 | -50.000 | -0.006 | 1.600 |

Calibration convergence requires the absolute temporal calibration
residual to remain within 1 ms for 10 s. Tail calibration RMSE is
computed over the final 20 s.

## Interpretation boundary

This experiment measures one official deterministic simulation
trajectory with online temporal calibration enabled. It does not
represent fixed-calibration behavior and does not yet establish a
population-level timing reliability boundary. A paired follow-up with
online temporal calibration disabled is required to separate intrinsic
estimator sensitivity from calibration compensation.

Official OpenVINS source files remain unchanged. The GPL-linked runner,
raw trajectories and logs remain outside the Apache-2.0 repository.
