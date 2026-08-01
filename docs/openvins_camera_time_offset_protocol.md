# OpenVINS camera timestamp-offset protocol

## Purpose

This experiment measures OpenVINS v2.7 behavior under constant camera
timestamp bias while preserving the underlying camera observations,
IMU measurements and physical simulator trajectory.

The official `rpng_sim` configuration enables online camera-to-IMU
time-offset calibration. This experiment therefore measures both
service-level timestamp sensitivity and the estimator's online
calibration response.

## Sign convention

A positive injected offset means the camera measurement is reported
later than its physical acquisition time:

`reported_camera_time = physical_camera_time + injected_offset`

OpenVINS defines its temporal calibration as:

`imu_time = camera_time + camera_to_imu_offset`

The consistent calibration target is therefore:

`target_offset = true_offset - injected_offset`

## Fixed scenarios

The sweep contains nine scenarios:

- baseline
- -50 ms, -20 ms, -10 ms and -5 ms
- +5 ms, +10 ms, +20 ms and +50 ms

Every scenario uses seed `20260802` and is run twice.

## Buffering and injection boundary

The runner mirrors the official ROS-free simulation loop and keeps one
camera frame buffered. At the 10 Hz camera rate, this provides 100 ms
of IMU look-ahead, which is sufficient for the fixed ±50 ms sweep.

Only the timestamp passed to `feed_measurement_simulation` is changed.
Raw feature IDs, feature measurements, IMU values and physical camera
times are untouched.

## Pairing requirements

The experiment is accepted only when:

- each scenario's two estimate trajectories are byte-identical
- each scenario's three reference trajectories are byte-identical
- each scenario's calibration history and summary are byte-identical
- raw camera-measurement fingerprints match across all scenarios
- raw IMU-measurement fingerprints match across all scenarios
- physical-time reference trajectories are byte-identical across all
  scenarios
- the baseline nominal-clock RMSE reproduces the committed OpenVINS
  baseline within 1 nanometre

## Error views

Three position-error views are retained.

Nominal-clock error compares the estimate with ground truth at the
reported camera timestamp plus the simulator true camera-to-IMU
offset. This represents a downstream consumer that assumes the nominal
mapping.

Calibration-aware error compares the estimate with ground truth at the
reported camera timestamp plus the filter's current estimated temporal
calibration. This measures the internal state after OpenVINS online
compensation.

Physical-time error compares the estimate with ground truth at the
original physical camera acquisition time.

## Calibration metrics

The experiment records the full temporal calibration history and
reports:

- initial and final estimated camera-to-IMU offset
- offset target
- final signed calibration residual
- calibration residual RMSE over the final 20 s
- estimated timestamp correction
- correction error relative to the injected offset
- convergence time

Convergence is the first time the absolute calibration residual remains
within 1 ms for 10 continuous seconds.

## Interpretation boundary

This sweep uses one official deterministic trajectory with online time
calibration enabled. It does not represent fixed-calibration behavior.
A paired experiment with temporal calibration disabled is required to
separate raw estimator sensitivity from online calibration
compensation.
