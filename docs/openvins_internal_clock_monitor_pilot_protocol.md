# V2-E03 internal clock-drift monitor pilot protocol

## Problem

V2-E02 produced two early-warning-gap scenarios:

- slow sinusoidal 5 ms drift under clean vision
- slow sinusoidal 5 ms drift under 10% visual dropout

Both exceeded the matched static trajectory-error envelope while final
temporal residual remained below 0.5 ms, one-metre availability remained
1.0 and no sustained failure occurred.

The injected clock target and physical trajectory reference are not
available in deployment. V2-E03 therefore tests whether the history of
the estimated camera-to-IMU offset alone can provide an earlier warning.

## Online input boundary

The monitor may use only:

- estimator timestamp
- estimated camera-to-IMU offset

It may not use:

- injected time offset
- physical camera timestamp
- physical trajectory reference
- target-versus-estimated tracking error
- service labels

## Causal monitor

After a 10 s warm-up, three channels are evaluated over a causal 5 s
window:

1. RMS velocity of estimated temporal offset
2. RMS acceleration of estimated temporal offset
3. peak-to-peak estimated temporal-offset range

Each threshold is calibrated only from the six static controls. The
threshold is 1.10 times the largest post-warm-up static value, subject to
a fixed numerical floor.

An alert requires at least two channels above threshold continuously for
1 s.

## Evaluation signal

Trajectory truth is used only after monitor output is fixed.

Degradation onset is the first time the causal 5 s rolling position RMSE
exceeds the matched static temporal-offset envelope by 0.20 m
continuously for 1 s.

Lead time is:

`degradation onset - monitor alert time`

Positive lead time indicates an early warning.

## Primary success criteria

`monitor_supported` requires:

- zero false-positive static scenarios
- detection of both early-warning-gap scenarios
- positive lead time for both early-warning-gap scenarios
- detection of at least 18 of 22 remaining dynamic scenarios

`monitor_partial` permits one static false positive or one non-positive
early-warning lead time, provided both primary positive scenarios are
detected.

All other outcomes are `monitor_not_supported`.

## Research boundary

This pilot discovers an internal monitor on the same deterministic
trajectory used for V2-E02. It does not establish multi-trajectory false
alarm rate, real-world robustness or deployment readiness.
