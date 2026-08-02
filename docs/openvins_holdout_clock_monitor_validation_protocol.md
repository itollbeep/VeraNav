# V2-E04 holdout clock monitor validation protocol

## Background

The preregistered V2-E03 three-channel monitor failed. A read-only
temporal audit showed that 26 of 27 misses never had two channels above
threshold simultaneously after warm-up.

A subsequent descriptive audit found strict duration separation for the
peak-to-peak channel on the discovery evidence:

- maximum static sustained exceedance: 0.0 s
- minimum primary-positive sustained exceedance: approximately 3.8 s

The candidate rule below is therefore a post-hoc discovery and must be
validated on holdout perturbation realizations.

## Frozen monitor

The monitor uses only estimator time and estimated camera-to-IMU offset.

- feature: causal 5 s peak-to-peak estimated-offset range
- threshold: 0.14729673122826897 ms
- warm-up: 10 s
- persistence: 3.0 s
- recalibration: prohibited

## Holdout construction

The official trajectory is unchanged, but perturbation realizations are
disjoint from discovery.

Discovery values that must not be reused:

- dropout seed 20260801
- random-walk seed 20260802
- sinusoidal phase 0 cycles

Holdout values:

- dropout seed 20260811
- random-walk seeds 20260812 and 20260813
- sinusoidal phases 0.25 and 0.5 cycles

The scenario plan contains 30 scenarios and 60 deterministic executions.

## Primary challenge set

Four slow-sinusoidal 5 ms scenarios:

- phases 0.25 and 0.5 cycles
- dropout 0% and 10%

## Success criteria

A result is supported only if:

- static false positives are 0/6
- all four primary challenges meet the degradation criterion
- all four primary challenges are detected
- all four alerts precede degradation
- at least 20/24 dynamic scenarios are detected

## Scope

This is perturbation-holdout validation on one official trajectory. It
does not replace multi-trajectory validation and cannot establish
deployment false-alarm rates.
