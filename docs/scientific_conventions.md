# Scientific Conventions

This document freezes the scientific conventions for VeraNav V0.1. Implementations must follow these conventions unless a later reviewed change updates this file and the affected tests.

## Scope

V0.1 uses a local, flat-Earth navigation model for short-duration synthetic experiments. Earth rotation, transport rate, curvature, geodetic conversion, magnetic heading, lever arms, and relativistic effects are outside the current scope.

## Frames

- Navigation frame `n`: local North-East-Down (NED).
  - `x`: north
  - `y`: east
  - `z`: down
- Body frame `b`: Forward-Right-Down (FRD).
  - `x`: forward
  - `y`: right
  - `z`: down
- Position `p_n` is the body-frame origin expressed relative to the local navigation-frame origin.
- Velocity `v_n` is expressed in the navigation frame.
- Column vectors are used throughout.

## Rotations and Quaternions

- `R_nb` maps body-frame coordinates into navigation-frame coordinates:
  `v_n = R_nb @ v_b`.
- `q_nb` represents the same rotation as `R_nb`.
- Quaternions use Hamilton algebra and scalar-first storage:
  `[w, x, y, z]`.
- Quaternion composition follows:
  `q_ac = q_ab ⊗ q_bc`.
- The quaternion is normalized after propagation and error injection.
- Quaternion sign is not forced during filtering because `q` and `-q` represent the same rotation. Orientation comparisons must be sign invariant.
- The skew-symmetric operator is defined by:
  `[a]_x b = a × b`.

- The quaternion exponential map uses the rotation-vector convention:
  `Exp(δθ) = [cos(||δθ||/2), u sin(||δθ||/2)]`, where `u = δθ / ||δθ||`.
- For zero rotation, `Exp(0) = [1, 0, 0, 0]`; for small rotation vectors, `Exp(δθ) ≈ [1, 0.5 δθ]` before normalization.

## Nominal and Error States

The nominal state is:

`x = [p_n, v_n, q_nb, b_a, b_g]`

It contains 16 stored parameters:

- position: 3
- velocity: 3
- quaternion: 4
- accelerometer bias: 3
- gyroscope bias: 3

The 15-dimensional error state is ordered as:

`δx = [δp_n, δv_n, δθ_b, δb_a, δb_g]`

The covariance uses the same ordering.

The attitude error uses a right, local perturbation:

`q_true = q_nom ⊗ Exp(δθ_b)`

Therefore `δθ_b` is expressed in the local/body tangent frame.

## Error Injection and Reset

After a correction:

- `p_n <- p_n + δp_n`
- `v_n <- v_n + δv_n`
- `q_nb <- q_nb ⊗ Exp(δθ_b)`
- `b_a <- b_a + δb_a`
- `b_g <- b_g + δb_g`

The injected error state is reset to zero. The covariance reset Jacobian must be derived consistently with the right-perturbation convention and verified by unit tests before the ESKF update is implemented.

## IMU Measurement Model

Accelerometer and gyroscope measurements are expressed in the body frame.

- accelerometer: metres per second squared (`m/s^2`)
- gyroscope: radians per second (`rad/s`)
- accelerometer bias: `m/s^2`
- gyroscope bias: `rad/s`

The measurement models are:

- `f_m = f_b + b_a + n_a`
- `ω_m = ω_ib_b + b_g + n_g`

Specific force excludes gravity. Nominal propagation therefore adds gravity in the navigation frame after rotating corrected specific force from body to navigation coordinates.

Under the V0.1 flat-Earth approximation, the corrected gyroscope measurement is treated as body angular velocity relative to the navigation frame, expressed in the body frame.

For NED, the constant gravity vector is:

`g_n = [0, 0, +g0]`

where `g0` is an explicit configuration value in `m/s^2`.

## GNSS Position Model

V0.1 GNSS measurements are local Cartesian positions in the navigation frame:

`z_p = p_n + n_p`

Units are metres. GNSS and IMU are assumed co-located in V0.1, so no lever arm is modelled.

## Time Convention

- Timestamps use seconds as `float64`.
- Timestamps must be finite and strictly increasing within each sensor stream.
- IMU measurements use zero-order hold: the sample at `t_k` is applied over the interval `[t_k, t_{k+1})`.
- Propagation to a GNSS timestamp occurs before applying the GNSS update at that timestamp.
- Measurements outside the estimator time range must raise an explicit error rather than being silently reordered or clipped.

## Numerical and Reproducibility Rules

- Scientific arrays use `float64` by default.
- Physical quantities use SI units.
- Randomness must come from an explicitly created generator with a recorded seed.
- Functions must validate shapes, finiteness, timestamp order, covariance symmetry, and covariance definiteness.
- State covariance matrices may be positive semidefinite; measurement-noise covariance matrices must be positive definite.
- Invalid inputs must fail explicitly.
- Mathematical equations, code, tests, and documentation must use the same state ordering and frame notation.

## Initial V0.1 Assumptions

- local NED frame with constant gravity
- body FRD frame
- no Earth rotation or curvature
- no Coriolis or transport-rate terms
- no GNSS lever arm
- no clock-state estimation
- no magnetometer
- no visual or LiDAR measurement
- no online calibration
- no adaptive noise model

Any change to these assumptions requires an explicit reviewed update to this document before implementation.

## References

- Joan Sola, *Quaternion Kinematics for the Error-State Kalman Filter*, arXiv:1711.02508.
- PX4 User Guide, *ROS 2 and PX4 Frame Conventions*.
