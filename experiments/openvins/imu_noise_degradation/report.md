# OpenVINS IMU-noise degradation experiment

## Purpose

This deterministic experiment evaluates OpenVINS sensitivity to
unmodelled IMU noise degradation. The estimator always uses the official
nominal OpenVINS v2.7 IMU noise model. A separate simulator uses derived
noise parameters.

The experiment distinguishes:

- white-noise density degradation
- bias random-walk degradation
- simultaneous white-noise and random-walk degradation

Each category is evaluated at 2×, 5× and 10× nominal magnitude, with a
nominal baseline.

## Pairing

For every scenario, a nominal simulator and a degraded simulator are
advanced in lockstep with the same official trajectory and measurement
seed.

The experiment is accepted only when:

- nominal and degraded camera observations are exactly identical
- nominal IMU fingerprints are identical across all scenarios
- event schedules and sample counts are identical
- every scenario is byte-identical across two executions
- all reference trajectories are byte-identical
- the baseline reproduces the committed OpenVINS RMSE within 1 nm

Only the degraded IMU stream is fed to the estimator. Camera
observations remain nominal.

## Consistency

The runner records the marginal 3D position covariance and computes
position NEES for every output sample.

For a three-dimensional position error, the retained 95% upper
chi-square threshold is `7.814727903251179`. The report includes mean,
median and p95 NEES together with the fraction of samples below this
upper threshold.

A high fraction below the upper threshold does not by itself prove
consistency because this single deterministic trajectory does not
provide an ensemble. The values are retained as diagnostic evidence.

## Results

| Scenario | White scale | Random-walk scale | RMSE (m) | RMSE ratio | p95 (m) | Maximum (m) | Availability ≤1 m | Mean position NEES | NEES ≤95% upper | Sustained 1 m failure onset (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 1.0 | 1.0 | 0.045411 | 1.000 | 0.081014 | 0.107145 | 1.0000 | 0.373 | 1.0000 | none |
| white-2x | 2.0 | 1.0 | 0.050923 | 1.121 | 0.098751 | 0.126100 | 1.0000 | 0.482 | 1.0000 | none |
| white-5x | 5.0 | 1.0 | 0.089337 | 1.967 | 0.166587 | 0.215420 | 1.0000 | 1.516 | 0.9997 | none |
| white-10x | 10.0 | 1.0 | 0.189349 | 4.170 | 0.389050 | 0.582829 | 1.0000 | 5.812 | 0.7580 | none |
| randomwalk-2x | 1.0 | 2.0 | 0.041934 | 0.923 | 0.066299 | 0.082858 | 1.0000 | 0.437 | 1.0000 | none |
| randomwalk-5x | 1.0 | 5.0 | 0.072983 | 1.607 | 0.118994 | 0.140496 | 1.0000 | 0.987 | 1.0000 | none |
| randomwalk-10x | 1.0 | 10.0 | 0.180770 | 3.981 | 0.296028 | 0.324373 | 1.0000 | 4.745 | 0.7309 | none |
| all-2x | 2.0 | 2.0 | 0.036380 | 0.801 | 0.054256 | 0.085059 | 1.0000 | 0.397 | 1.0000 | none |
| all-5x | 5.0 | 5.0 | 0.090025 | 1.982 | 0.144981 | 0.192510 | 1.0000 | 1.978 | 0.9983 | none |
| all-10x | 10.0 | 10.0 | 0.205067 | 4.516 | 0.321369 | 0.408307 | 1.0000 | 10.351 | 0.5433 | none |

## Interpretation boundary

The experiment measures a single official deterministic simulation
trajectory and deliberately keeps the estimator noise model nominal.
It therefore evaluates robustness to noise-model mismatch, not the
best achievable result after retuning process noise.

Population-level reliability requires additional trajectories, seeds
and paired estimator configurations with matched degraded noise models.

Official OpenVINS source and configuration files remain unchanged. The
GPL-linked runner, derived simulator configurations, raw trajectories
and consistency traces remain outside the Apache-2.0 repository.
