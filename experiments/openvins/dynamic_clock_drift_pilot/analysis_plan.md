# V2-E02 dynamic camera-to-IMU clock drift pilot

## Motivation

V2-E01b replicated a global and local trajectory-error interaction under
bounded static temporal offsets and visual dropout. Across all 105
physical scenarios, online temporal calibration still converged,
one-metre availability remained 100%, final temporal residual remained
below 0.012 ms and no sustained service failure occurred.

The next question is whether time-varying clock error produces
trajectory degradation before these conventional terminal diagnostics
indicate failure.

## Fixed scenarios

Static controls:

- offsets: `[-10.0, 0.0, 10.0]` ms
- visual dropout: `[0.0, 0.1]`

Dynamic profiles:

- `linear-positive`
- `linear-negative`
- `sinusoidal-slow`
- `piecewise-random-walk`

Dynamic spans:

- `5.0 ms`
- `10.0 ms`
- `20.0 ms`

A span is the complete bounded range. A 20 ms span therefore remains
inside `[-10 ms, +10 ms]`, matching the static controls.

Total scenarios: `30`

Each scenario is executed twice.

Planned estimator executions: `60`

## Profile definitions

- linear-positive: starts at `-span/2` and ends at `+span/2`
- linear-negative: starts at `+span/2` and ends at `-span/2`
- sinusoidal-slow: one zero-mean cycle across the trajectory
- piecewise-random-walk: twelve deterministic mean-centred knots,
  scaled to the same bounded span and linearly interpolated

## Primary comparison

Every dynamic cell is compared with the zero-offset static control under
the same visual condition.

Three metric groups are preregistered:

1. global trajectory RMSE
2. maximum rolling local RMSE
3. dynamic temporal-tracking error and lag

A cell is supported when at least two metric groups cross their practical
thresholds.

The pilot is supported only when one profile has at least two supported
drift spans and its global RMSE is nondecreasing with span.

## Early-warning gap

A supported dynamic cell is classified as an early-warning gap when:

- final absolute temporal residual is below `0.5 ms`
- one-metre availability remains `1.0`
- no sustained failure occurs

This tests whether trajectory precision can degrade before terminal
calibration and service diagnostics become abnormal.

## Visual condition

The 10% visual-dropout condition uses the canonical nested mask from the
replicated interaction experiment. Its dynamic-drift interaction is
exploratory because only one dropout seed is used in this pilot.

## Claim boundary

This is one official deterministic trajectory and one dynamic-profile
realization. A supported pilot identifies dynamic profiles for later
multi-seed and multi-trajectory validation; it does not establish a
general clock-drift failure law.
