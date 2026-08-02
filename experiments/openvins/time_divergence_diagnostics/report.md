# OpenVINS fixed-time divergence diagnostics

## Purpose

The fixed temporal-calibration experiment produced very large full-run
RMSE values under every nonzero camera timestamp offset. This analysis
determines whether those values represent persistent filter divergence
or are dominated by isolated outliers.

No estimator is rerun. The analysis uses the previously committed fixed
and online trajectory evidence after verifying every input artifact
against its committed SHA256 record.

## Failure definitions

Service failure threshold: `1 m`.

Sustained failure begins when the rolling 1 s position RMSE remains
above 1 m for 3 continuous seconds.

Recovery occurs only when the rolling 1 s RMSE remains at or below 1 m
for 5 continuous seconds after sustained failure begins.

A trace is classified as broad trajectory failure when:

- sustained failure occurs
- p90 position error exceeds 1 m
- at least 50% of samples after onset exceed 1 m

Catastrophic divergence additionally requires the trace to cross
100 m position error.

## Fixed-calibration results

| Scenario | Offset (ms) | RMSE (m) | p90 (m) | Maximum (m) | Sustained onset (s) | First 100 m crossing (s) | Availability ≤1 m | Post-onset fraction >1 m | Top 1% squared-error share | Recovery after onset (s) | Classification |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | 0.0 | 0.059 | 0.116 | 0.143 | none | none | 1.0000 | 0.0000 | 0.0566 | not applicable | not catastrophic |
| neg-50ms | -50.0 | 78648.117 | 144630.258 | 187995.959 | 1.90 | 14.90 | 0.0089 | 0.9976 | 0.0572 | not recovered | catastrophic |
| neg-20ms | -20.0 | 43239.349 | 82276.466 | 104777.926 | 3.10 | 26.50 | 0.0127 | 0.9979 | 0.0590 | not recovered | catastrophic |
| neg-10ms | -10.0 | 3620.022 | 5402.577 | 14036.081 | 8.10 | 31.40 | 0.0298 | 0.9979 | 0.1432 | not recovered | catastrophic |
| neg-5ms | -5.0 | 6341.919 | 11265.474 | 16835.816 | 13.20 | 35.30 | 0.0472 | 0.9978 | 0.0696 | not recovered | catastrophic |
| pos-5ms | 5.0 | 10174.163 | 18878.457 | 26673.438 | 13.70 | 35.40 | 0.0486 | 0.9982 | 0.0683 | not recovered | catastrophic |
| pos-10ms | 10.0 | 3212.576 | 5744.115 | 6047.624 | 10.00 | 35.20 | 0.0363 | 0.9979 | 0.0364 | not recovered | catastrophic |
| pos-20ms | 20.0 | 73766.184 | 138269.569 | 173048.905 | 4.50 | 17.80 | 0.0171 | 0.9983 | 0.0554 | not recovered | catastrophic |
| pos-50ms | 50.0 | 232422.804 | 422812.389 | 506181.949 | 1.10 | 8.90 | 0.0058 | 0.9979 | 0.0479 | not recovered | catastrophic |

## Summary

- Fixed nonbaseline scenarios classified as broad failure:
  `8` of `8`.
- Fixed nonbaseline scenarios classified as catastrophic divergence:
  `8` of `8`.
- Paired online-calibration scenarios classified as catastrophic:
  `0` of `8`.

Top 1% and top 5% squared-error shares are retained to quantify outlier
concentration. They must be interpreted together with p90, service
availability and the post-onset fraction. A large top-share alone does
not imply a single-point artifact when most post-onset samples remain
above the service threshold.

## Interpretation boundary

This diagnostic confirms trace-level behavior for one deterministic
OpenVINS simulation trajectory. The classification thresholds are
engineering definitions for this project, not universal OpenVINS safety
limits. Population-level reliability still requires additional
trajectories and sensor realizations.

Official OpenVINS source files are unchanged, and this analysis starts
no new estimator process.
