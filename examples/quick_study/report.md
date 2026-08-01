# VeraNav Structured GNSS Degradation Reliability Study

## Paired comparison

Scenario: bias=8.000 m, outage=2.000 s

Seeds: 8

Mean RMSE difference, degraded minus baseline: 0.089291 m [0.039772, 0.139996]

Mean maximum-error difference, degraded minus baseline: 0.026294 m [-0.010861, 0.095173]

Baseline failure rate: 0.000000

Degraded failure rate: 0.000000

## Adaptive reliability boundary

| Outage (s) | Status | Reliable lower bias (m) | Unreliable upper bias (m) | Width (m) | Evaluations |
|---:|:---|---:|---:|---:|---:|
| 0.000000 | bounded | 10.125000 | 10.500000 | 0.375000 | 7 |
| 0.500000 | all_reliable | 12.000000 | n/a | n/a | 2 |
| 1.000000 | all_reliable | 12.000000 | n/a | n/a | 2 |

## Reproducibility

All baseline and degraded runs use paired random seeds. Confidence intervals and boundary evaluations are deterministic for the recorded seed sequences.
