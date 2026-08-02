# VeraNav OpenVINS reliability work: final v1 status

## Completion

The fixed six-stage VeraNav v1 plan is complete.

| Stage | Completion |
|---|---:|
| Stage 1 | 100% |
| Stage 2 | 100% |
| Stage 3 | 100% |
| Stage 4 | 100% |
| Stage 5 | 100% |
| Stage 6 | 100% |
| Weighted overall | 100.0% |

## Completed technical evidence

- Official KF-GINS reproduction and metrics
- Official OpenVINS v2.7 stable reproduction
- VeraNav OpenVINS adapter and no-degradation baseline
- Random visual dropout degradation
- Multi-start timed visual burst outage analysis
- Signed camera timestamp-offset sweep with online calibration
- Fixed versus online temporal-calibration comparison
- Trace-level fixed-offset divergence diagnostics
- IMU white-noise and bias-random-walk degradation
- Cross-experiment reliability synthesis and deterministic figures

## Main technical conclusions

1. Fixed camera-to-IMU timestamp mismatch is the strongest tested
   failure mode. Disabling online temporal calibration causes
   catastrophic divergence for every tested nonzero offset from 5 ms to
   50 ms.

2. Online temporal calibration prevents catastrophic failure across the
   same signed offset range, although large offsets still increase
   position error.

3. Random visual dropout becomes strongly harmful around the tested 30%
   loss region. Timed burst outages require local metrics because global
   RMSE can hide short severe failures.

4. Ten-times unmodelled IMU noise raises position RMSE and NEES, but no
   tested IMU-noise scenario crosses the 1 m sustained-failure
   definition on the official trajectory.

## Evidence locations

Primary synthesis:

`experiments/openvins/reliability_synthesis/`

Core experiment directories:

- `experiments/openvins/visual_dropout/`
- `experiments/openvins/visual_burst_sweep/`
- `experiments/openvins/camera_time_offset/`
- `experiments/openvins/camera_time_offset_fixed/`
- `experiments/openvins/time_divergence_diagnostics/`
- `experiments/openvins/imu_noise_degradation/`

Raw GPL-linked runners, derived configurations and large trajectory
evidence remain under:

`/home/itoll/GitHub/VeraNavExternal/OpenVINSStable/`

## Completion boundary

The v1 plan is complete in implementation, evidence traceability,
testing and synthesis. This status does not mean the research topic is
exhausted. Natural v2 extensions include real-world datasets,
multi-seed ensembles, additional trajectories, matched degraded-noise
models and adaptive reliability monitoring.
