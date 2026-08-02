# VeraNav v2 experiment protocol

## Mandatory experiment structure

Every VeraNav v2 experiment must include:

1. a preregistered hypothesis
2. explicit success and disconfirming criteria
3. a paired or factorial design where feasible
4. common measurement realization checks
5. deterministic replay before statistical replication
6. trace-level and aggregate metrics
7. exact source, configuration and evidence hashes
8. a statement of the claim boundary
9. negative-result retention
10. a follow-up falsification experiment

## Evidence levels

### Level A: deterministic trace evidence

One trajectory and one seed, reproduced byte for byte.

Useful for implementation validation and mechanism discovery. It cannot
support population-level claims.

### Level B: paired multi-seed evidence

Multiple independent seeds under the same trajectory and configuration.

Useful for confidence intervals and paired effect estimates.

### Level C: multi-trajectory evidence

Multiple trajectories or datasets with independent measurement
realizations.

Required before general reliability conclusions.

### Level D: real-world external validity

Public or collected real sensor data with documented preprocessing and
failure labels.

Required for strong practical deployment claims.

## Innovation discipline

The repository must use the following terminology:

- verified conclusion: supported by current evidence
- candidate hypothesis: preregistered but unverified
- mechanism evidence: competing explanations tested
- generalized result: repeated across seeds and trajectories
- literature novelty: established only after systematic literature
  comparison
- paper contribution: implementation, evidence and literature novelty
  jointly support the claim

The terms novel, first or state of the art must not appear in technical
claims until the literature review and comparison are complete.
