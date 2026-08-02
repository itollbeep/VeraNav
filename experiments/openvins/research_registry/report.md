# VeraNav v2 research registry

## Purpose

This registry separates three categories that must not be mixed during
paper development:

1. claims already verified by VeraNav experiments
2. candidate hypotheses that still require experiments
3. statements explicitly rejected as overclaims

Every verified claim records its evidence path, current scope and the
next experiment that could falsify or generalize it.

## Verified v1 claims

| Claim | Title | Evidence level | Current scope |
|---|---|---|---|
| V1-C01 | Fixed camera-to-IMU timing mismatch is the strongest tested failure mode | cross_experiment | OpenVINS v2.7, one deterministic official simulation trajectory, fixed offsets from minus 50 ms to plus 50 ms. |
| V1-C02 | Online temporal calibration is protective but not cost-free | paired_experiment | Same trajectory and measurement realization as the paired fixed-calibration experiment. |
| V1-C03 | Random visual dropout has a practical degradation breakpoint | trace_level | Random visual frame dropout on one deterministic official trajectory. |
| V1-C04 | Local outage metrics reveal failures hidden by global RMSE | trace_level | One deterministic trajectory, selected burst start times and one-second or three-second outages. |
| V1-C05 | IMU noise mismatch degrades consistency before service collapse | paired_experiment | Unmodelled white-noise and random-walk increases up to ten times nominal on one trajectory. |
| V1-C06 | Cross-factor reliability risk is strongly nonuniform | cross_experiment | Only the degradation ranges and deterministic trajectory included in VeraNav v1. |
| V1-C07 | Single-run nonmonotonicity must not be overinterpreted | trace_level | Single deterministic measurement realization and one trajectory. |
| V1-C08 | Deterministic reproducibility is not population-level validation | cross_experiment | Methodological conclusion about the present evidence base, not a sensor-performance claim. |

## Candidate v2 hypotheses

| Rank | Hypothesis | Experiment | Title | Priority score |
|---:|---|---|---|---:|
| 1 | V2-H01 | V2-E01 | Temporal calibration and visual degradation interact | 4.925 |
| 2 | V2-H02 | V2-E02 | Dynamic clock drift exposes temporal-model limits | 4.790 |
| 3 | V2-H04 | V2-E04 | Estimator-internal statistics can provide early warning | 4.775 |
| 4 | V2-H05 | V2-E05 | Reliability-aware mitigation can create graceful degradation | 4.550 |
| 5 | V2-H03 | V2-E03 | Matched IMU noise models recover estimator consistency | 4.350 |
| 6 | V2-H06 | V2-E06 | The v1 risk hierarchy generalizes beyond one trajectory | 4.325 |

## First preregistered experiment

`V2-E01` tests the interaction between online temporal calibration and
random visual dropout.

Pilot matrix:

- time offsets: `-20 ms`, `0 ms`, `+20 ms`
- random visual dropout: `0%`, `10%`, `30%`, `50%`
- scenarios: `12`
- common official trajectory and measurement seed
- online temporal calibration enabled in every scenario

Primary outcomes:

- temporal-calibration convergence time
- final temporal residual
- full-run and local position RMSE
- sustained failure onset
- one-metre service availability

The central interaction claim will be accepted only if the joint effect
is practically larger than the sum of single-factor effects and is
reproducible under deterministic replay. It will remain provisional
until multi-seed and multi-trajectory validation.

## Progress

VeraNav v1 remains complete at `100.0%`.

VeraNav v2 stage 1, research registry and preregistration, is complete.
Under the fixed v2 stage weights, overall v2 progress is `10.0%`.
