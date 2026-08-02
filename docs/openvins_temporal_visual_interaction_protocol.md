# OpenVINS temporal-calibration and visual-dropout interaction protocol

## Research question

Does random visual information loss reduce the observability and tracking
ability of online camera-to-IMU temporal calibration?

## Factorial pilot

The experiment combines three camera timestamp offsets with four random
visual-dropout levels:

- offsets: -20 ms, 0 ms and +20 ms
- dropout: 0%, 10%, 30% and 50%
- total scenarios: 12
- deterministic replays per scenario: 2

## Controls

All scenarios use the same official OpenVINS v2.7 trajectory, camera
measurements and IMU measurements.

A single per-frame uniform random sequence generates all dropout masks.
The 10% dropped-frame set must be a subset of the 30% set, and the 30%
set must be a subset of the 50% set. The same probability mask is used
for all three timestamp offsets.

The zero-dropout cells must reproduce the existing timestamp-offset
experiment. The zero-offset cells must reproduce the existing visual
dropout experiment.

## Primary outcomes

- physical-time position RMSE
- maximum rolling 5 s RMSE
- online temporal-calibration convergence time
- final absolute temporal residual
- temporal residual RMSE over the final 20 s
- one-metre service availability
- sustained one-metre failure onset

## Interaction contrasts

For an outcome Y, the additive interaction is:

`Y(offset, dropout) - Y(offset, 0) - Y(0, dropout) + Y(0, 0)`

For RMSE, the multiplicative interaction ratio is:

`Y(offset, dropout) × Y(0, 0) / [Y(offset, 0) × Y(0, dropout)]`

The pilot interaction criterion requires at least two preregistered
metrics to cross their practical thresholds in the same joint scenario.

## Interpretation boundary

A supported pilot identifies a mechanism candidate. It is not a
generalized interaction claim and does not establish literature novelty.
Multi-seed and multi-trajectory validation remains mandatory.
