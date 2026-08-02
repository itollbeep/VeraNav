# OpenVINS reliability synthesis protocol

## Purpose

This final analysis consolidates the committed VeraNav OpenVINS
reliability experiments into one traceable result set. It does not run
the estimator or generate new raw measurements.

## Included experiment families

The synthesis reads:

- random visual dropout
- timed visual burst outages
- camera timestamp offsets with online temporal calibration
- camera timestamp offsets with fixed temporal calibration
- fixed-offset trace-level divergence diagnostics
- IMU white-noise and bias-random-walk degradation

Every input manifest and result file is hashed before synthesis. The
OpenVINS upstream commit and official-source modification flags must
remain consistent across all inputs.

## Cross-family comparability

The camera timestamp, fixed-calibration, divergence and IMU-noise
experiments share the same camera-measurement fingerprint. The paired
time-offset experiments also share the same IMU-measurement fingerprint
and physical reference trajectory.

The visual dropout families use the same official OpenVINS baseline but
apply different visual-loss mechanisms. Their global and local metrics
are retained separately.

## Output policy

The synthesis generates:

- a machine-readable manifest
- complete JSON results
- a compact CSV family summary
- a consolidated Markdown report
- four deterministic SVG figures

All outputs are generated twice and compared byte for byte. CSV uses LF
line endings only. SVG files are parsed after generation to confirm
well-formed XML.

## Interpretation boundary

The synthesis ranks the tested failure modes for one deterministic
official OpenVINS simulation trajectory and the fixed degradation ranges
used by VeraNav.

It does not establish universal OpenVINS reliability limits. Additional
trajectories, datasets, independent random seeds, sensor models and
real-world sequences are required for population-level conclusions.
