# OpenVINS v2.7 ROS-free simulator reproduction

- Release: `v2.7`
- Upstream commit: `93adc241390d13e99232652cf05cbe18a93c7bea`
- Upstream commit date: `2023-06-19T23:55:01Z`
- Environment profile: `official-era-opencv-4.5`
- CMake: `cmake version 3.25.1`
- Compiler: `x86_64-conda-linux-gnu-g++ (conda-forge gcc 10.4.0-19) 10.4.0`
- OpenCV: `4.5.5`
- ROS enabled: `false`
- ArUco enabled: `false`
- Official `test_sim_repeat`: `PASS`
- Official `test_sim_meas`: `PASS`
- Official `run_simulation`: `PASS` on two independent runs
- Build-only compiler compatibility flag: `-include cassert`
- Isolated OpenGL runtime linked explicitly: `true`
- Headless runtime mode: `QT_QPA_PLATFORM=offscreen`
- Official source modified: `false`
- Host system packages modified: `false`

This is a stable upstream baseline for VeraNav. It establishes source
provenance, isolated compilation and official simulator execution. It
does not claim that OpenVINS itself is a VeraNav innovation. VeraNav's
independent contribution begins with estimator adaptation, structured
degradation injection and uncertainty-aware reliability comparison.
