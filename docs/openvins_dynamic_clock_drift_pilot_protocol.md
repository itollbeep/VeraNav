# V2-E02 dynamic camera-to-IMU clock drift pilot protocol

## Research question

Can time-varying camera-to-IMU clock drift degrade trajectory accuracy
before final temporal residual, service availability or sustained
failure diagnostics indicate an abnormal condition?

## Evidence motivating the experiment

V2-E01b replicated four static temporal-offset and visual-dropout
interaction cells across five nested dropout seeds.

The replicated evidence also established stable negative controls across
105 physical scenarios:

- minimum one-metre availability: 1.0
- maximum temporal-calibration convergence time: 2.70 s
- maximum final absolute temporal residual: 0.0117 ms
- sustained service failures: 0

The next experiment therefore targets a possible diagnostic blind spot:
dynamic tracking error rather than static convergence failure.

## Fixed design

Static controls:

- -10 ms
- 0 ms
- +10 ms

Dynamic drift spans:

- 5 ms
- 10 ms
- 20 ms

A span is the complete bounded range. The 20 ms span is constrained to
[-10 ms, +10 ms].

Dynamic profiles:

- linear positive
- linear negative
- one-cycle slow sinusoid
- twelve-segment deterministic piecewise random walk

Visual conditions:

- no visual dropout
- 10% canonical visual dropout

Scenarios: 30

Repeats per scenario: 2

Estimator executions: 60

## Primary outcome groups

### Global trajectory error

- physical-time position RMSE
- additive increase relative to the matched zero-offset static control
- RMSE ratio relative to the matched zero-offset static control

### Local trajectory error

- maximum rolling 5 s RMSE
- additive increase relative to control
- local RMSE ratio relative to control

### Dynamic time tracking

- target-versus-estimated offset RMSE
- peak absolute tracking residual
- tracking lag estimated by bounded cross-correlation

A dynamic cell is supported when at least two of the three outcome
groups cross their preregistered practical thresholds.

## Pilot decision

The dynamic-drift pilot is supported when at least one profile has:

1. at least two supported drift spans
2. nondecreasing global position RMSE across 5, 10 and 20 ms spans

Null, nonmonotonic and profile-specific results are retained.

## Early-warning gap

A supported dynamic cell is labelled an early-warning gap when final
absolute temporal residual remains below 0.5 ms, one-metre availability
remains 1.0 and no sustained one-metre failure occurs.

## Visual-dropout boundary

The 10% condition is exploratory. It uses one canonical dropout mask and
cannot support a multi-seed dynamic-visual interaction claim.

## Claim boundary

This is a single-trajectory pilot. It identifies dynamic profiles for
later multi-seed and multi-trajectory validation and does not establish
a universal clock-drift failure boundary.
