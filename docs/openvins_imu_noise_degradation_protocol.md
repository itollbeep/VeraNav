# OpenVINS IMU-noise degradation protocol

## Purpose

This experiment measures OpenVINS v2.7 robustness to IMU noise-model
mismatch. The estimator always uses the official nominal IMU noise
model. A separate simulator uses degraded IMU white-noise density and
bias random-walk parameters.

## Official noise mechanism

The official simulation model advances gyroscope and accelerometer
biases using random-walk standard deviation multiplied by the square
root of the IMU interval. Measurement white noise uses noise density
divided by the square root of the IMU interval.

The derived configurations change the four Kalibr IMU noise parameters
only:

- gyroscope noise density
- accelerometer noise density
- gyroscope random walk
- accelerometer random walk

Official OpenVINS source and configuration files remain unchanged.

## Fixed scenarios

The ten scenarios are:

- nominal baseline
- white noise at 2×, 5× and 10×
- bias random walk at 2×, 5× and 10×
- white noise and random walk together at 2×, 5× and 10×

All scenarios retain the official measurement seed `0`.

## Pairing

A nominal simulator and a degraded simulator run in lockstep for each
scenario.

The nominal simulator is used to verify the shared latent realization.
The degraded IMU stream is fed to the estimator, while the nominal
camera observations are fed unchanged.

The experiment is accepted only when:

- nominal and degraded camera measurements are exactly identical
- nominal IMU fingerprints are identical across every scenario
- event schedules and sample counts match
- every scenario is byte-identical across two executions
- all reference trajectories are byte-identical
- baseline nominal and degraded IMU streams are identical
- baseline position RMSE reproduces the committed OpenVINS baseline

## Metrics

The experiment reports:

- position RMSE, mean, p95 and maximum
- RMSE ratio to baseline
- service availability below 0.1 m, 0.5 m and 1 m
- sustained 1 m failure onset
- RMS difference between degraded and nominal IMU measurements
- mean position covariance trace
- position NEES mean, median and p95
- fraction of position NEES values below the 3D 95% upper threshold

Sustained service failure uses a 1 s rolling RMSE that remains above
1 m for 3 continuous seconds.

## Interpretation boundary

The estimator noise model is deliberately not retuned. The experiment
therefore measures robustness to unmodelled sensor degradation rather
than matched-model performance.

Position NEES is diagnostic on this single deterministic trajectory.
Formal consistency claims require an ensemble across multiple
independent trajectories and seeds.
