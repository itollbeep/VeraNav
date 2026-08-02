# VeraNav research novelty ledger

## Purpose

This ledger is the long-term source for future paper contributions. It
must distinguish experimental findings from literature novelty and from
unverified hypotheses.

A result is not called a paper innovation merely because it is
interesting. It becomes a defensible innovation only after:

1. the effect is reproducible
2. the mechanism is investigated
3. competing explanations are tested
4. the result generalizes beyond one trajectory or seed
5. related literature is systematically checked
6. the contribution is implemented and compared against suitable
   baselines

## Current evidence classes

### Verified single-trajectory conclusions

The following results are supported by deterministic, hash-traceable
VeraNav v1 experiments:

1. Fixed camera-to-IMU timestamp mismatch is the strongest tested
   failure mode. All eight nonzero fixed-offset scenarios from 5 ms to
   50 ms were classified as catastrophic divergence.

2. Online temporal calibration prevents catastrophic failure across the
   same signed offset range, although large initial offsets still
   increase trajectory error.

3. Random visual dropout shows a sharp tested degradation region near
   30% frame loss.

4. Visual burst outages are strongly timing-dependent. Local metrics
   expose severe short failures that full-run RMSE can hide.

5. Severe unmodelled IMU noise increases RMSE and position NEES before
   the one-metre service definition is violated.

6. The tested reliability risk ordering is:
   fixed temporal mismatch, high random visual dropout, adverse visual
   burst timing, then severe unmodelled IMU noise.

7. Small apparent improvements under low-severity perturbations are
   single-run nonmonotonic observations and must not be interpreted as
   beneficial noise or beneficial timing error.

8. Deterministic reproducibility and evidence traceability are strong,
   but they do not establish population-level reliability.

The machine-readable version, exact evidence paths and falsification
steps are stored in:

`experiments/openvins/research_registry/verified_claims.json`

### Candidate paper-level innovations

The following are hypotheses, not established innovations:

1. Online temporal calibration has an observability-conditioned failure
   boundary under visual degradation.

2. Constant-offset temporal models have a finite bandwidth and fail
   under sufficiently rapid clock drift.

3. Matched degraded IMU noise models recover consistency even when
   physical sensor error remains elevated.

4. Estimator-internal temporal residual, innovation and covariance
   statistics can provide early warning before service failure.

5. Reliability-triggered mitigation can convert abrupt failure into
   graceful degradation.

6. The v1 risk hierarchy generalizes across trajectories and seeds.

Their preregistered success and disconfirming criteria are stored in:

`experiments/openvins/research_registry/candidate_hypotheses.json`

## Rules for future updates

Every new conclusion must record:

- a unique claim identifier
- experimental status
- exact metric and numerical result
- source commit and evidence path
- applicable trajectory, seed and configuration
- alternative explanations
- the next falsification experiment
- whether literature novelty has been checked

Negative and null results must also be retained. They prevent repeated
dead ends and improve the credibility of the final paper.
