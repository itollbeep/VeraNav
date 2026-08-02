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


## V2-E01 temporal-visual interaction pilot

Status: `pilot_supported`

The preregistered pilot supports an interaction mechanism candidate under the tested single trajectory.

Strongest tested joint scenario: `pos20-drop10`

- supported preregistered metrics:
  `2`
- RMSE interaction ratio:
  `1.454099904`
- local RMSE interaction ratio:
  `1.822894047`
- RMSE additive interaction:
  `0.058445294 m`
- final residual excess:
  `0.000833205 ms`

Evidence:

- `experiments/openvins/temporal_visual_interaction/manifest.json`
- `experiments/openvins/temporal_visual_interaction/results.json`
- `experiments/openvins/temporal_visual_interaction/report.md`

Current claim boundary:

- one official deterministic trajectory
- one nested dropout realization
- online temporal calibration enabled
- offsets limited to ±20 ms
- dropout limited to 50%

This remains a mechanism-discovery pilot, not a generalized interaction,
universal failure boundary or established literature innovation.


## V2-E01b replication preregistration

The detailed V2-E01 audit changed the mechanism interpretation.

Both signed 20 ms offsets met the two-metric interaction criterion at
approximately 10% dropout:

- -20 ms: global ratio 1.299854, local ratio 1.912376
- +20 ms: global ratio 1.454100, local ratio 1.822894

At 30% and 50% dropout, all global and local interaction ratios were
below one and no joint cell met the criterion. Temporal-calibration
convergence, residual and one-metre service availability remained below
their practical failure thresholds.

The current candidate conclusion is therefore:

> Mild visual sparsity and temporal offset may produce a reproducible,
> nonmonotonic trajectory-error interaction without destabilizing the
> online temporal-calibration state.

This is preregistered for five-seed replication in `V2-E01b`. It is not
yet a verified generalized conclusion or paper-level innovation.

Evidence and design:

- `experiments/openvins/temporal_visual_interaction/results.json`
- `experiments/openvins/temporal_visual_interaction_replication/preregistration.json`
- `experiments/openvins/temporal_visual_interaction_replication/analysis_plan.md`


## V2-E01b five-seed replication result

Status: `replicated_supported`

Claim class: experimentally verified within one trajectory and five dropout seeds.

The preregistered low-dropout temporal–visual interaction replicated across five nested-dropout masks on the official trajectory.

- supported joint cells: `4`
- partially supported joint cells: `1`
- strongest offset: `-10 ms`
- strongest dropout: `10%`
- seed support: `5/5`
- mean global interaction ratio: `1.563546998`
- mean local interaction ratio: `1.880451699`
- global additive 95% CI lower bound: `0.003194761 m`
- local additive 95% CI lower bound: `0.028554745 m`

Exact evidence:

- `experiments/openvins/temporal_visual_interaction_replication/results_manifest.json`
- `experiments/openvins/temporal_visual_interaction_replication/results.json`
- `experiments/openvins/temporal_visual_interaction_replication/seed_interactions.csv`
- `experiments/openvins/temporal_visual_interaction_replication/cell_summary.csv`
- `experiments/openvins/temporal_visual_interaction_replication/report.md`

Scope:

- one official OpenVINS simulation trajectory
- five deterministic nested-dropout seeds
- offsets from -20 ms to +20 ms
- dropout from 5% to 20%
- online temporal calibration enabled

Counterclaim boundary:

Do not describe the result as multi-trajectory, real-world, universal or literature-novel.

Literature novelty remains unverified.


## V2-E02 dynamic clock drift preregistration

V2-E01b established a five-seed replicated interaction in global and
local trajectory error, but all 105 physical scenarios retained 100%
one-metre availability, converged online temporal calibration and no
sustained service failure.

The new mechanism question is whether a time-varying temporal offset can
degrade trajectory accuracy before terminal residual and service
diagnostics become abnormal.

V2-E02 preregisters four bounded drift profiles, three drift spans and
two visual conditions. The largest drift remains inside the existing
-10 ms to +10 ms static-control range.

A supported pilot identifies a dynamic tracking mechanism for later
multi-seed and multi-trajectory validation. It is not yet a generalized
clock-drift law or literature-level novelty claim.

Evidence and design:

- `experiments/openvins/dynamic_clock_drift_pilot/preregistration.json`
- `experiments/openvins/dynamic_clock_drift_pilot/scenario_plan.csv`
- `experiments/openvins/dynamic_clock_drift_pilot/analysis_plan.md`

## V2-E02 dynamic clock drift pilot result

Verified status: `pilot_supported`.

The preregistered pilot completed 30 scenarios and 60 deterministic
OpenVINS executions. Confirmatory clean-vision profile support was found
for `4` profile(s): `linear-positive, linear-negative, sinusoidal-slow, piecewise-random-walk`.

The strongest observed cell was `linear-negative` with a
`20.0 ms` bounded span and
`0.0` visual dropout. Its global RMSE ratio
was `8505.102855`, local RMSE ratio was
`15899.569934`, and dynamic temporal-tracking RMSE was
`8.917996 ms`.

Supported dynamic cells: `24`.
Early-warning-gap cells: `2`.

Claim boundary: Single official deterministic trajectory, one deterministic profile realization and one exploratory visual-dropout mask. No multi-trajectory, real-world or literature-level generalization is claimed.

Evidence:

- `experiments/openvins/dynamic_clock_drift_pilot/results.json`
- `experiments/openvins/dynamic_clock_drift_pilot/dynamic_cells.csv`
- `experiments/openvins/dynamic_clock_drift_pilot/profile_summary.csv`
- `/home/itoll/GitHub/VeraNavExternal/OpenVINSStable/dynamic-clock-drift/evidence`


## V2-E03 internal clock monitor preregistration

V2-E02 identified two slow-sinusoidal 5 ms early-warning gaps. Their
trajectory error exceeded the matched static envelope, but final
temporal residual, one-metre availability and sustained-failure
diagnostics remained nominal.

The ground-truth clock target and physical trajectory cannot serve as
online monitors. V2-E03 preregisters a causal monitor using only the
estimated camera-to-IMU offset history.

The monitor combines estimated-offset velocity RMS, acceleration RMS and
peak-to-peak range. Thresholds are calibrated exclusively from six
static controls, and the monitor is evaluated against all 30 V2-E02
scenarios.

A successful pilot remains a single-trajectory monitor candidate and
requires independent trajectory validation.

Evidence and design:

- `experiments/openvins/internal_clock_monitor_pilot/preregistration.json`
- `experiments/openvins/internal_clock_monitor_pilot/scenario_labels.csv`
- `experiments/openvins/internal_clock_monitor_pilot/analysis_plan.md`

## V2-E03 internal clock monitor result

The preregistered monitor status is `monitor_not_supported`.

- static false-positive scenarios:
  `0/6`
- primary early-warning positives detected:
  `0/2`
- primary positives with positive lead time:
  `0/2`
- secondary dynamic scenarios detected:
  `3/22`

The monitor uses only estimator timestamp and estimated camera-to-IMU
offset history. Trajectory truth is restricted to post-hoc degradation
onset evaluation.

This remains a single-trajectory monitor result. It is not a deployment
false-alarm claim and does not establish multi-trajectory robustness.

Evidence:

- `experiments/openvins/internal_clock_monitor_pilot/results.json`
- `experiments/openvins/internal_clock_monitor_pilot/scenario_monitor_results.csv`
- `experiments/openvins/internal_clock_monitor_pilot/thresholds.csv`


## V2-E04 holdout clock monitor preregistration

V2-E03 rejected the preregistered three-channel synchronous monitor. A
read-only temporal audit showed that the dominant failure was absent
post-warm-up channel overlap rather than insufficient persistence.

A descriptive single-channel audit identified a candidate monitor based
on sustained peak-to-peak estimated time-offset range. Because this rule
was discovered after observing V2-E03, it is not counted as confirmatory
evidence.

V2-E04 freezes the candidate rule and validates it on new sinusoidal
phases, random-walk seeds and dropout seed. The official trajectory is
unchanged, so the result remains perturbation-holdout evidence rather
than multi-trajectory validation.

Evidence and design:

- `experiments/openvins/holdout_clock_monitor_validation/preregistration.json`
- `experiments/openvins/holdout_clock_monitor_validation/scenario_plan.csv`
- `experiments/openvins/holdout_clock_monitor_validation/analysis_plan.md`
