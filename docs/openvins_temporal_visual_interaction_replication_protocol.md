# V2-E01b temporal-visual interaction replication protocol

## Refined mechanism hypothesis

The V2-E01 pilot found super-additive global and local trajectory error
at both signed 20 ms offsets under approximately 10% random visual
dropout. Temporal-calibration convergence, final residual and one-metre
service availability did not cross their preregistered thresholds.

V2-E01b therefore tests a refined mechanism:

> Mild visual sparsity and temporal offset create a reproducible
> state-estimation error coupling while online temporal calibration
> remains converged.

A secondary hypothesis is that the interaction is nonmonotonic: it is
strongest at low dropout and becomes submultiplicative when visual loss
dominates total error.

## Design

Offsets:

- -20 ms
- -10 ms
- 0 ms
- +10 ms
- +20 ms

Dropout levels:

- 0%
- 5%
- 10%
- 15%
- 20%

Dropout seeds:

- 20260801
- 20260802
- 20260803
- 20260804
- 20260805

This defines 125 analytical cells.

Because a zero-dropout result does not depend on the dropout seed, the
five offset-only anchors are executed once and shared across seeds.
There are 105 unique physical scenarios.

The full canonical-seed matrix is executed twice. For each additional
seed, every nonzero-dropout cell is executed once and the parent
strongest cell, +20 ms with 10% dropout, is repeated twice. Total
estimator executions: 134.

## Mask and measurement controls

Within each seed:

- all dropout levels use one common per-frame uniform random sequence
- 5% dropped frames are a subset of 10%
- 10% are a subset of 15%
- 15% are a subset of 20%
- the same mask is used across all offsets

Across every scenario:

- physical camera measurements remain identical
- IMU measurements remain identical
- physical reference trajectories remain identical
- only timestamp offset and dropout mask change

## Seed-level interaction

For metric Y:

`I_add = Y(offset, dropout) - Y(offset, 0)
         - Y(0, dropout) + Y(0, 0)`

`I_ratio = Y(offset, dropout) × Y(0, 0)
           / [Y(offset, 0) × Y(0, dropout)]`

A seed supports the interaction only when both global and local RMSE
satisfy:

- additive interaction at least 0.01 m
- multiplicative interaction ratio at least 1.25

## Replicated cell criterion

A joint cell is supported only when:

1. at least four of five seeds satisfy the seed-level two-metric rule
2. mean global and local additive interactions are at least 0.01 m
3. mean global and local ratios are at least 1.25
4. lower 95% confidence limits for both additive interactions exceed
   zero

The experiment retains null, sign-changing and antagonistic effects.

## Claim boundary

Five dropout seeds establish stochastic replication on one official
trajectory. They do not establish multi-trajectory or real-world
generalization, and they do not establish literature novelty.
