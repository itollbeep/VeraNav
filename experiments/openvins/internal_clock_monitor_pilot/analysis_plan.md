# V2-E03 deployable internal clock monitor pilot

## Objective

Detect the two V2-E02 early-warning-gap scenarios using only estimator
outputs available online, before physical-reference trajectory error
crosses a preregistered degradation threshold.

## Positive and negative cases

Static negatives:

- all six static temporal-offset controls

Primary positives:

- sinusoidal-slow, 5 ms span, clean vision
- sinusoidal-slow, 5 ms span, 10% visual dropout

Secondary dynamic cases:

- the remaining 22 dynamic-drift scenarios

## Online monitor inputs

The monitor may use only:

- estimator timestamp
- estimated camera-to-IMU time offset

Injected clock offset, physical camera time and trajectory reference are
prohibited from the online monitor.

## Causal channels

All channels are calculated over a causal 5 s window after a 10 s
warm-up:

1. RMS velocity of estimated time offset
2. RMS acceleration of estimated time offset
3. peak-to-peak range of estimated time offset

Thresholds are calibrated only from the six static controls. For each
channel, the threshold is the larger of its fixed numerical floor and
1.10 times the maximum post-warm-up static-control value.

An alert is emitted when at least two channels exceed their thresholds
continuously for 1 s.

## Ground-truth evaluation boundary

Physical trajectory reference is used only to define degradation onset.
For each visual condition, onset occurs when the causal 5 s rolling
position RMSE exceeds the matched static temporal-offset envelope by
0.20 m continuously for 1 s.

The monitor is not permitted to use this signal.

## Primary success criterion

The pilot is `monitor_supported` only when:

1. zero of six static controls produce an alert
2. both early-warning positives produce an alert
3. the alert precedes degradation onset in both early-warning positives
4. at least 18 of 22 secondary dynamic cases are detected

`monitor_partial` is assigned when both positives are detected but one
lead time is non-positive, or when one static false positive occurs.

All other outcomes are `monitor_not_supported`.

## Scope boundary

This is monitor discovery on the same single trajectory used by V2-E02.
A successful result remains a pilot and requires multi-trajectory
validation before deployment claims.
