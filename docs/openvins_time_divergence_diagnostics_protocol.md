# OpenVINS fixed-time divergence diagnostic protocol

## Purpose

The fixed temporal-calibration experiment produced position RMSE values
from several kilometres to more than 200 kilometres under nonzero
camera timestamp offsets. This protocol determines whether those values
represent persistent estimator divergence or isolated extreme samples.

No new OpenVINS execution is performed. The diagnostic reads the
committed fixed-calibration and online-calibration trajectory evidence.

## Input integrity

Before analysis, every estimate, reference, calibration and summary file
used by the diagnostic is checked against the SHA256 values committed in
the corresponding experiment manifest.

The fixed and online experiments must also retain:

- identical camera-measurement fingerprints
- identical IMU-measurement fingerprints
- byte-identical physical-time reference trajectories
- identical sample timelines

## Service and failure definitions

The project service threshold is 1 m position error.

A sustained failure begins when rolling 1 s position RMSE remains above
1 m for at least 3 continuous seconds.

Recovery occurs only when rolling 1 s RMSE remains at or below 1 m for
at least 5 continuous seconds after sustained failure begins.

The diagnostic records first crossings of:

- 1 m
- 10 m
- 100 m
- 1000 m

It also reports service availability below 0.1 m, 0.5 m, 1 m, 10 m and
100 m.

## Outlier-concentration diagnostics

For each trace, the diagnostic reports:

- median, p90, p95 and p99 position error
- maximum error and its time
- final error
- top 1% and top 5% shares of total squared error
- fraction of post-onset samples above 1 m

A trace is classified as broad trajectory failure when:

- sustained failure occurs
- p90 exceeds 1 m
- at least 50% of post-onset samples exceed 1 m

It is classified as catastrophic divergence when broad trajectory
failure is accompanied by a 100 m threshold crossing.

These are VeraNav engineering definitions for the present experiment,
not universal OpenVINS safety limits.

## Interpretation boundary

This diagnostic evaluates one deterministic official simulation
trajectory. It distinguishes persistent trace failure from isolated
outliers but does not establish population-level reliability. Additional
trajectories and sensor realizations remain necessary.
