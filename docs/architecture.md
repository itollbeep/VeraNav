# VeraNav architecture

## Objective

VeraNav separates navigation estimation from reliability evaluation. The estimator produces states, covariances, innovations, and consistency statistics. The reliability layer controls degradation scenarios, paired random seeds, failure criteria, uncertainty intervals, adaptive boundary search, and evidence export.

This separation allows a future estimator adapter to replace the V0.1 ESKF without changing the study protocol.

## Data flow

```text
analytic truth
    |
    +-- simulated IMU --------------------+
    |                                     |
    +-- simulated GNSS --> degradation --> estimator --> run metrics
                                                  |
paired seeds: baseline ---------------------------+
paired seeds: degraded ---------------------------+
                                                  |
                                    paired differences and failures
                                                  |
                              bootstrap and Wilson confidence intervals
                                                  |
                                  adaptive reliability-boundary search
                                                  |
                                   JSON / CSV / Markdown / SVG reports
```

## Core modules

### Estimation

- `state.py`: immutable nominal navigation state
- `math.py`: quaternion and rotation primitives
- `imu.py`: nominal inertial propagation
- `linearization.py`: continuous 15-state error dynamics
- `covariance.py`: Van Loan discretization and covariance propagation
- `measurement.py`: GNSS position measurement model
- `update.py`: Joseph update, error injection, and reset
- `eskf.py`: composed propagation and measurement-update operations
- `consistency.py`: right-error vector and NEES

### Simulation and degradation

- `simulation.py`: analytic circular trajectory and deterministic sensor generation
- `degradation.py`: structured GNSS outage and position bias
- `experiment.py`: one complete synthetic estimator run

### Reliability evaluation

- `metrics.py`: RMSE, maximum error, NIS and NEES summaries
- `monte_carlo.py`: repeated experiments and failure classification
- `reliability.py`: fixed-grid reliability envelope
- `statistics.py`: confidence intervals and paired bootstrap
- `comparison.py`: common-random-number baseline/degraded comparison
- `boundary.py`: adaptive reliable-to-unreliable boundary search
- `report.py`: deterministic JSON, CSV, and Markdown output

### Entry points

- `scripts/run_reliability_demo.py`: compact fixed-grid demonstration
- `scripts/run_reliability_study.py`: paired comparison and adaptive boundary report
- `scripts/render_study_svg.py`: deterministic standard-library SVG rendering

## State and frame conventions

V0.1 uses:

- NED navigation coordinates
- FRD body coordinates
- `R_nb` and `q_nb` for body-to-navigation rotation
- Hamilton scalar-first quaternions
- right local attitude error
- 16 stored nominal parameters
- 15 error-state dimensions

The error-state ordering is:

```text
delta p_n, delta v_n, delta theta_b, delta b_a, delta b_g
```

The convention is fixed in `docs/scientific_conventions.md`. The propagation and update equations are fixed in `docs/eskf_model.md`.

## Adapter boundary

A future estimator adapter should consume a versioned scenario containing truth, IMU samples, GNSS measurements, degradation metadata, and random seeds. It should return at minimum:

- timestamps
- estimated states
- covariance or an explicit declaration that covariance is unavailable
- accepted and rejected measurement information
- estimator status and failure reason

The study layer should not reach into estimator-internal caches or tune an estimator differently for each random seed.

## Reproducibility boundary

A report is reproducible only when it records:

- scenario configuration
- degradation coordinates
- estimator identity and configuration
- seed sequence
- failure criteria
- confidence level
- bootstrap seed and resample count
- boundary tolerance and iteration limit
- software version

Generated outputs are deterministic for a fixed environment and recorded configuration. V0.1 pins NumPy and SciPy ranges in `pyproject.toml` and verifies stable serialization in tests.

## Current limitations

The circular trajectory and GNSS faults are controlled verification cases. They do not represent the full dynamics, multipath, non-line-of-sight behavior, vibration, clock effects, time synchronization errors, or calibration uncertainty of a real platform.

The reliability boundary is therefore an experimental boundary for the configured synthetic system, not a universal operating limit.
