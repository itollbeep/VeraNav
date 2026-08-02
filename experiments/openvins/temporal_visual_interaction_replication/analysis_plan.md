# V2-E01b temporal-visual interaction replication

## Motivation

The parent pilot found two-metric super-additive trajectory-error
interaction at both `-20 ms × 10% dropout` and
`+20 ms × 10% dropout`. The interaction disappeared at 30% and 50%
dropout, while temporal-calibration convergence, residual and
one-metre availability remained healthy.

The refined hypothesis is therefore not a catastrophic temporal
calibration failure. It is a low-dropout state-estimation error coupling
that may weaken when visual dropout becomes the dominant error source.

## Fixed design

- offsets: `[-20.0, -10.0, 0.0, 10.0, 20.0]`
- dropout fractions: `[0.0, 0.05, 0.1, 0.15, 0.2]`
- nested-dropout seeds: `[20260801, 20260802, 20260803, 20260804, 20260805]`
- analytical cells: `125`
- unique physical scenarios: `105`
- estimator executions: `134`

Zero-dropout anchors are deterministic and shared across seeds.
The complete canonical-seed matrix is executed twice. Each additional
seed is executed once at nonzero dropout, with the parent strongest cell
executed twice as a seed-specific determinism audit.

## Primary replicated criterion

For each joint offset-dropout cell, interaction contrasts are calculated
within seed using the seed-matched dropout-only result and the shared
deterministic offset-only anchor.

A cell is `replicated_supported` only when:

1. at least four of five seeds independently satisfy both global-RMSE
   and local-RMSE practical thresholds
2. mean global and local additive interactions are at least `0.01 m`
3. mean global and local interaction ratios are at least `1.25`
4. lower 95% confidence bounds for both additive interactions are
   greater than zero

## Secondary analyses

- paired positive-versus-negative offset differences
- low-dropout boundary between 5% and 20%
- nonmonotonic interaction peaks
- calibration convergence and residual as negative-control outcomes

## Claim boundary

The experiment remains one official simulation trajectory. Five dropout
seeds improve stochastic replication but do not establish
multi-trajectory or real-world generalization.
