# V2-E02 dynamic camera-to-IMU clock drift pilot

Pilot status: `pilot_supported`.

- scenarios: 30
- deterministic executions: 60
- supported clean-vision profiles: 4
- supported dynamic cells: 24
- early-warning-gap cells: 2

## Strongest dynamic cell

- profile: `linear-negative`
- span: `20.0 ms`
- dropout: `0.0`
- global RMSE ratio: `8505.102855`
- local RMSE ratio: `15899.569934`
- tracking RMSE: `8.917996 ms`
- global error above static ±10 ms envelope: `386.174233 m`
- local error above static ±10 ms envelope: `1621.486836 m`
- supported metric groups: `3`
- early-warning gap: `False`

## Confirmatory clean-vision profile decisions

- `linear-positive`: supported spans `3/3`, RMSE nondecreasing `True`, profile supported `True`.
- `linear-negative`: supported spans `3/3`, RMSE nondecreasing `True`, profile supported `True`.
- `sinusoidal-slow`: supported spans `3/3`, RMSE nondecreasing `True`, profile supported `True`.
- `piecewise-random-walk`: supported spans `3/3`, RMSE nondecreasing `True`, profile supported `True`.

## Claim boundary

Single official deterministic trajectory, one deterministic profile realization and one exploratory visual-dropout mask. No multi-trajectory, real-world or literature-level generalization is claimed.
