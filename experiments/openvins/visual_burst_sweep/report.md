# OpenVINS visual-outage timing-sensitivity audit

## Purpose

The earlier fixed-window sweep found that a 3 s visual outage beginning
30 s after the first processed camera frame produced an overall RMSE
close to baseline. This audit tests whether that result is specific to
the outage location.

The same verified external OpenVINS runner is reused without
modification. One-second and three-second complete visual-observation
outages are injected at 30 s, 90 s, 150 s and 210 s. A no-degradation
baseline is included.

Every scenario is run twice. Estimate, reference and summary files must
be byte-identical across replays, and every scenario must use the same
byte-identical reference trajectory.

## Local metrics

For each outage, the audit reports:

- full-run RMSE and maximum error
- 10 s pre-outage RMSE
- outage RMSE
- 10 s post-outage RMSE
- RMSE and peak error over the outage plus 10 s post window
- matched baseline-window RMSE and peak ratios
- peak positive excess error over the matched local window
- positive excess-error integral through 30 s after outage end
- recovery time

Recovery is the first post-outage time at which the rolling 1 s RMSE of
positive error excess over baseline stays below
`0.004541064 m` for 3 s. Recovery is searched for 30 s.

## Results

| Scenario | Overall RMSE (m) | Local RMSE ratio | Local peak ratio | Peak excess (m) | Positive excess integral (m·s) | Recovery time (s) |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.045411 | 1.000 | 1.000 | 0.000000 | 0.000000 | baseline |
| burst-t030-d1 | 0.060054 | 2.119 | 1.604 | 0.021225 | 0.366245 | not recovered |
| burst-t030-d3 | 0.045415 | 3.066 | 4.805 | 0.081174 | 0.646357 | not recovered |
| burst-t090-d1 | 0.039565 | 0.983 | 1.109 | 0.011455 | 0.052434 | 0.100 |
| burst-t090-d3 | 0.042600 | 1.029 | 1.159 | 0.016384 | 0.132650 | 20.700 |
| burst-t150-d1 | 0.036980 | 0.950 | 0.922 | 0.002667 | 0.007327 | 0.100 |
| burst-t150-d3 | 0.040932 | 0.942 | 1.285 | 0.020831 | 0.013155 | 0.700 |
| burst-t210-d1 | 0.042551 | 1.195 | 1.057 | 0.011333 | 0.091907 | 13.900 |
| burst-t210-d3 | 0.041727 | 1.312 | 1.159 | 0.021992 | 0.162907 | 12.800 |

## Timing sensitivity

- 1 s outages: local RMSE ratio range 0.950–2.119; local peak ratio range 0.922–1.604.
- 3 s outages: local RMSE ratio range 0.942–3.066; local peak ratio range 1.159–4.805.

## Interpretation boundary

This audit isolates outage timing on one deterministic official
simulation trajectory. It can establish that sensitivity varies by
trajectory location, but it does not yet provide population-level
confidence intervals. Formal reliability boundaries require additional
trajectories, seeds and cross-estimator paired experiments.

Official OpenVINS source files remain unchanged. The GPL-linked runner,
raw trajectories and logs remain outside the Apache-2.0 repository.
