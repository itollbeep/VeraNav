# OpenVINS v2.7 official ROS-free reproduction

## Scope

This baseline pins the official OpenVINS `v2.7`
release at commit `93adc241390d13e99232652cf05cbe18a93c7bea`. It builds the upstream
ROS-free simulator in an isolated user-local environment and does not
modify host system packages.

## Verification

- `test_sim_repeat`: PASS with the official exact-repeatability marker.
- `test_sim_meas`: PASS.
- `run_simulation`: PASS in two independent executions.
- Official estimator configuration: unchanged.
- Official source tree: unchanged before and after the build.
- Environment profile: `official-era-opencv-4.5`.

The build uses `-include cassert` because the pinned release calls
`assert` in `Feature.cpp` without directly including `<cassert>`.
The conda OpenCV 4.5 build also pulls Qt libraries that require
`libGL.so.1`; the isolated conda-forge `libgl` runtime and an
`rpath-link` CMake overlay are therefore used. Official source files
are not edited. Simulator binaries run in Qt offscreen mode.

## Role in VeraNav

OpenVINS is an external estimator baseline. VeraNav's independent work
is the estimator adapter, structured degradation injection, paired
experiments, NIS/NEES consistency analysis, fault-detection metrics,
recovery analysis and reliability-boundary comparison.

## Evidence

Compact evidence is stored in `examples/openvins_official/`. Large
source archives, dependency environments, binaries and raw logs remain
outside the repository under
`/home/itoll/GitHub/VeraNavExternal/OpenVINSStable`.

## VeraNav common-trajectory adapter

A GPL-linked C++ recorder is maintained outside the Apache-2.0
repository under
`/home/itoll/GitHub/VeraNavExternal/OpenVINSStable/adapter`.
It mirrors the official ROS-free simulation loop, reads the public
OpenVINS filter state and simulator ground truth, and writes the
`veranav-position-trajectory-v1` schema.

The adapter maps OpenVINS simulation global x/y/z to VeraNav N/E/D.
This is explicit because the OpenVINS simulator uses positive global
z gravity. Two independent adapter executions must produce
byte-identical estimate and reference trajectories before the record is
accepted.

The committed result is stored in
`reproductions/openvins/simulation/`. The upstream source tree remains
unchanged, and the GPL-linked source and binary remain external.
