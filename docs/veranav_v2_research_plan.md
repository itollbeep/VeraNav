# VeraNav v2 research plan

## Objective

VeraNav v2 moves from isolated single-factor degradation experiments to
interaction mechanisms, dynamic faults, early warning and adaptive
mitigation.

The goal is not to increase the number of experiments mechanically. The
goal is to identify a small number of reproducible mechanisms that can
support a coherent paper contribution.

## Fixed stages and weights

| Stage | Weight | Goal |
|---|---:|---|
| 1. Research registry and preregistration | 10% | Preserve claims, boundaries and falsification plans |
| 2. Cross-factor interactions | 25% | Quantify temporal-calibration and visual-degradation coupling |
| 3. Dynamic clock drift | 20% | Identify limits of constant temporal-offset models |
| 4. Monitoring and adaptive mitigation | 25% | Detect and mitigate failure before service collapse |
| 5. Multi-seed and multi-trajectory validation | 15% | Estimate effect sizes, intervals and generalization |
| 6. Paper and benchmark packaging | 5% | Produce a coherent benchmark, paper and public artifact |

## First experiment: V2-E01

### Research question

Does visual information degradation reduce the observability and
tracking ability of online camera-to-IMU temporal calibration?

### Pilot factorial matrix

Time offsets:

- -20 ms
- 0 ms
- +20 ms

Random visual dropout:

- 0%
- 10%
- 30%
- 50%

Total scenarios: 12.

All scenarios use the same official trajectory, measurement seed and
online temporal-calibration implementation.

### Primary metrics

- temporal-calibration convergence time
- final temporal residual
- full-run position RMSE
- local position RMSE
- sustained one-metre failure onset
- one-metre service availability
- camera and IMU measurement fingerprints

### Interaction criterion

The interaction is not inferred from a visually nonparallel curve
alone. The joint condition must produce a practically meaningful change
beyond the sum of single-factor effects in at least one preregistered
primary metric.

### Expansion rule

If the pilot identifies a reproducible interaction:

- densify offsets around the transition
- add burst outages at multiple motion phases
- repeat across seeds and trajectories

If the pilot shows no interaction:

- retain the null result
- move to dynamic clock drift
- do not manufacture a contribution from noise

## Subsequent experiments

### V2-E02: dynamic clock drift

Inject linear and piecewise clock drift. Estimate stable tracking,
delayed tracking and failure regions.

### V2-E03: matched versus mismatched IMU models

Compare nominal estimator noise, matched degraded noise and adaptive
noise inflation under identical degraded measurements.

### V2-E04: early-warning monitor

Evaluate temporal residuals, innovation statistics, covariance growth
and local-error proxies for warning lead time and false alarms.

### V2-E05: adaptive mitigation

Test covariance inflation, measurement gating and calibration-state
freezing under paired faults.

### V2-E06: validation ensemble

Repeat the strongest effects across trajectories and independent seeds.
Report confidence intervals and effect sizes rather than isolated
single-run rankings.
