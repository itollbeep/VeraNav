# External estimator adapter protocol

## Purpose

VeraNav evaluates estimators through a common trajectory boundary rather than importing third-party estimator source code. External projects remain in separate checkouts with their original licenses. An adapter is responsible for running one estimator, converting its output into the common schema, and recording the exact upstream revision and command.

## Common trajectory schema

The V0.1 adapter boundary is a UTF-8 CSV file with exactly four columns:

```text
timestamp_s,north_m,east_m,down_m
```

Requirements:

- timestamps are finite, strictly increasing seconds
- positions are finite metres in a local NED frame
- at least two rows are required
- the adapter must not extrapolate missing trajectory segments
- evaluation uses reference timestamps inside the common time interval and linearly interpolates the estimate

The initial schema intentionally contains only position. Orientation, velocity, covariance, runtime, and failure events will be added through versioned schemas rather than silently changing V0.1.

## Execution contract

`CommandAdapterManifest` stores a tokenized command, a workspace-relative output path, and a timeout. Commands are executed with `shell=False`. Only `{workspace}` and `{output}` placeholders are accepted. The output path must remain inside the external workspace.

The common runner captures:

- exact command tokens
- stdout and stderr
- elapsed wall time
- output file path
- parsed common trajectory

A nonzero return code, timeout, missing output, or invalid CSV is an adapter failure. It is not converted into a navigation score.

## Internal reference adapter

The built-in ESKF is exposed through the same `AdapterRun` structure. This verifies that the adapter boundary can represent an estimator, a reference trajectory, deterministic CSV output, interpolation, and position metrics before an external system is connected.

Run the smoke example:

```bash
PYTHONPATH=src python scripts/run_adapter_smoke.py --output-dir /tmp/veranav-adapter --seed 0
```

## Planned external baselines

### KF-GINS

- upstream: `https://github.com/i2Nav-WHU/KF-GINS`
- family: loosely coupled GNSS/INS error-state EKF
- license: GPL-3.0
- integration rule: retain source in a separate checkout and pin an exact tested commit
- first target: upstream-provided GNSS/INS sample data and navigation-result export

### OpenVINS

- upstream: `https://github.com/rpng/open_vins`
- family: filter-based visual-inertial MSCKF
- license: GPL-3.0
- initial candidate: v2.7
- integration rule: retain source in a separate checkout and pin the exact tested commit
- first target: a supported public dataset with upstream evaluation output

The descriptors in `configs/baselines/` are metadata, not claims that the systems have already been reproduced.

## Reproducibility record required for each integrated baseline

Before a baseline status changes to `integrated`, the repository must record:

1. upstream repository URL and exact commit SHA
2. host OS, compiler, middleware, and dependency versions
3. build and run commands
4. dataset identity and checksum
5. coordinate-frame conversion
6. output parser version
7. successful smoke-test log
8. evaluation metrics and known limitations

## License boundary

KF-GINS and OpenVINS are GPL-licensed projects. VeraNav does not copy their source into its Apache-2.0 repository. Adapter code, manifests, commands, and independently generated evaluation outputs remain in VeraNav; upstream source and modifications remain governed by the upstream license.
