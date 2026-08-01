# OpenVINS visual-observation dropout experiment

## Scope

This deterministic sensitivity sweep uses OpenVINS v2.7 commit
`93adc241390d13e99232652cf05cbe18a93c7bea`. Selected camera frames retain their timestamps but
receive empty feature sets, so the filter continues propagating while
visual observations are unavailable.

Six fixed scenarios are evaluated:

- no degradation
- Bernoulli whole-frame observation loss at 10%, 30% and 50%
- continuous whole-frame observation loss for 1 s and 3 s beginning
  30 s after the first processed camera frame

Each scenario is executed twice. Estimate, reference and summary files
must be byte-identical across replays. All six scenarios must also use
the same byte-identical reference trajectory.

## Results

| Scenario | Realized frame loss | Position RMSE (m) | RMSE ratio | Maximum error (m) | Maximum ratio |
|---|---:|---:|---:|---:|---:|
| baseline | 0.0000 | 0.045411 | 1.000 | 0.107145 | 1.000 |
| random-10 | 0.0962 | 0.064354 | 1.417 | 0.116396 | 1.086 |
| random-30 | 0.2944 | 0.169144 | 3.725 | 0.393840 | 3.676 |
| random-50 | 0.5053 | 0.185308 | 4.081 | 0.376489 | 3.514 |
| burst-1s | 0.0034 | 0.060054 | 1.322 | 0.135785 | 1.267 |
| burst-3s | 0.0103 | 0.045415 | 1.000 | 0.092663 | 0.865 |

## Interpretation boundary

This is a deterministic structured-degradation sweep on one official
OpenVINS simulation configuration. It establishes sensitivity and
engineering reproducibility, but it does not provide population-level
confidence intervals or a formal reliability boundary. Those require
additional seeds, trajectories and cross-estimator paired studies.

The GPL-linked degradation runner remains outside the Apache-2.0
VeraNav repository. Official OpenVINS source files are unchanged.
