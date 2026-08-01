# VeraNav reliability study protocol

## Purpose

VeraNav evaluates when a navigation estimator remains reliable under structured sensor degradation, rather than reporting only a nominal trajectory error. The V0.1 protocol uses a deterministic synthetic inertial and GNSS experiment so that every result can be reproduced from the recorded configuration and random seeds.

## Paired experiment design

Baseline and degraded runs use identical random seeds. This pairs the simulated IMU noise, GNSS noise and initial-state perturbation across the two conditions. Run-level differences therefore isolate the degradation effect more directly than two independently sampled Monte Carlo groups.

The primary paired effects are:

- position RMSE difference, degraded minus baseline
- maximum position-error difference, degraded minus baseline
- baseline and degraded failure classifications
- degraded-only failures and apparent recoveries

Percentile bootstrap confidence intervals are calculated from the paired run differences with a fixed bootstrap seed.

## Reliability decision

A run fails when either its position RMSE or maximum position error exceeds the configured `FailureCriteria`. A degradation coordinate is classified from the Monte Carlo divergence rate. The decision may use either the observed divergence rate or the upper Wilson confidence bound.

The default V0.1 demonstration requires zero observed failed runs. This is intentionally strict but should not be interpreted as a certified integrity guarantee. Larger seed counts and a confidence-bound requirement are needed for stronger statistical claims.

## Adaptive boundary search

For each outage duration, VeraNav brackets the GNSS bias magnitude at which the Monte Carlo result changes from reliable to unreliable. It first evaluates zero bias and a configured maximum bias. If those endpoints bracket a transition, deterministic bisection continues until the bias interval is no wider than the requested tolerance or the iteration limit is reached.

Each reported boundary point includes:

- outage duration
- boundary status
- greatest evaluated reliable bias
- least evaluated unreliable bias
- bracket width
- every evaluated degradation coordinate
- observed divergence rate and Wilson interval

This adaptive search requires fewer experiments than a uniformly dense grid while retaining an explicit uncertainty bracket on the degradation coordinate.

## Reproducibility outputs

The study command writes:

- `study.json` with the complete paired and boundary results
- `paired_comparison.csv` with one row per seed
- `adaptive_boundary.csv` with one row per outage duration
- `report.md` with a concise human-readable summary

The JSON schema version is recorded in the file. Output ordering, bootstrap seeds and Monte Carlo seeds are deterministic.

## Current scope and limitations

V0.1 contains one synthetic circular trajectory, one ESKF implementation and structured GNSS outage and position-bias faults. The framework is designed so that future estimator adapters and degradation models can be evaluated with the same paired-seed and reliability-boundary protocol. Current results are verification experiments, not safety certification and not evidence of real-world performance.
