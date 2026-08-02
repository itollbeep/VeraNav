# V2-E04 holdout clock monitor validation

## Confirmatory objective

Validate a frozen single-channel temporal monitor on perturbation
realizations that were not used to discover the rule.

## Frozen candidate monitor

The online monitor uses only:

- estimator timestamp
- estimated camera-to-IMU offset

The causal feature is the 5 s peak-to-peak range of estimated temporal
offset. The threshold is fixed at 0.14729673122826897 ms. No threshold
recalibration is allowed.

After a 10 s warm-up, an alert requires the range channel to remain
strictly above threshold for 3.0 s.

## Holdout perturbations

Discovery realizations are prohibited:

- dropout seed 20260801
- random-walk seed 20260802
- sinusoidal phase 0 cycles

The holdout set uses:

- dropout seed 20260811
- random-walk seeds 20260812 and 20260813
- sinusoidal phases 0.25 and 0.5 cycles

The official deterministic trajectory remains unchanged. This is
therefore perturbation-holdout validation, not multi-trajectory
validation.

## Scenario set

Six static controls:

- static offsets -10, 0 and +10 ms
- visual dropout 0% and 10%

Twelve phase-shifted sinusoidal scenarios:

- spans 5, 10 and 20 ms
- phases 0.25 and 0.5 cycles
- visual dropout 0% and 10%

Twelve random-walk holdout scenarios:

- spans 5, 10 and 20 ms
- seeds 20260812 and 20260813
- visual dropout 0% and 10%

Each scenario is executed twice, for 60 estimator executions.

The four 5 ms phase-shifted sinusoidal scenarios are the primary
challenge set. The remaining twenty dynamic scenarios are secondary.

## Evaluation boundary

The monitor cannot use injected clock target, physical camera time,
trajectory reference or labels.

Trajectory truth is used only after alert generation to determine the
preregistered degradation onset:

- causal 5 s rolling position RMSE
- matched static temporal-offset envelope
- margin 0.20 m
- persistence 1.0 s

## Success criteria

`holdout_monitor_supported` requires:

1. zero alerts in six static scenarios
2. all four primary challenge scenarios meet the degradation criterion
3. all four primary challenge scenarios are detected
4. all four primary alerts precede degradation onset
5. at least 20 of 24 dynamic scenarios are detected

All criteria are evaluated exactly once after evidence collection.

## Claim boundary

A supported result confirms the frozen monitor only across new
perturbation realizations on the same official trajectory. It does not
establish multi-trajectory false-alarm performance, real-world
robustness or deployment readiness.
