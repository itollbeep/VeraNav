# OpenVINS v2.7 simulation adapter baseline

- Upstream commit: `93adc241390d13e99232652cf05cbe18a93c7bea`
- Common aligned samples: `2921`
- Position RMSE: `0.045410644 m`
- Position mean error: `0.039415903 m`
- Position maximum error: `0.107145188 m`
- Deterministic estimate and reference CSV outputs: `PASS`
- Official OpenVINS source modified: `false`
- GPL-linked C++ adapter source location: external only

The adapter mirrors the official ROS-free simulation loop and records
the public OpenVINS state together with simulator ground truth. The
synthetic OpenVINS global x/y/z coordinates are mapped to VeraNav
north/east/down because the simulator uses positive global z gravity.
