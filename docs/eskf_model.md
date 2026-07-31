# ESKF Mathematical Model

This document defines the VeraNav V0.1 error-state Kalman filter model. It must remain consistent with `docs/scientific_conventions.md`.

No estimator implementation exists yet. Equations in this document are the specification that later code and tests must follow.

## 1. State Definitions

The nominal state is:

`x = [p_n, v_n, q_nb, b_a, b_g]`

with 16 stored parameters:

- `p_n` in metres
- `v_n` in metres per second
- unit quaternion `q_nb = [w, x, y, z]`
- accelerometer bias `b_a` in metres per second squared
- gyroscope bias `b_g` in radians per second

The 15-dimensional error state is:

`delta_x = [delta_p_n, delta_v_n, delta_theta_b, delta_b_a, delta_b_g]`

The error-state ordering is fixed as:

- position: indices 0 to 2
- velocity: indices 3 to 5
- attitude: indices 6 to 8
- accelerometer bias: indices 9 to 11
- gyroscope bias: indices 12 to 14

The attitude error is a right local perturbation:

`q_true = q_nominal tensor_product Exp(delta_theta_b)`

where `delta_theta_b` is expressed in the local body tangent frame.

## 2. Corrected IMU Measurements

For an IMU sample held over one interval:

`f_hat = f_m - b_a`

`omega_hat = omega_m - b_g`

The V0.1 flat-Earth approximation treats `omega_hat` as body angular velocity relative to the navigation frame, expressed in the body frame.

## 3. Continuous-Time Nominal Dynamics

The nominal dynamics are:

`p_dot_n = v_n`

`v_dot_n = R_nb f_hat + g_n`

`q_dot_nb = 0.5 q_nb tensor_product [0, omega_hat]`

`b_dot_a = 0`

`b_dot_g = 0`

with:

`g_n = [0, 0, g0]`

for the NED navigation frame.

The true accelerometer and gyroscope biases follow random walks even though the nominal biases are constant between correction steps.

## 4. Discrete Nominal Propagation

IMU measurements use zero-order hold over `dt = t_(k+1) - t_k`.

The interval update uses midpoint attitude for translational propagation:

`q_half = q_k tensor_product Exp(0.5 omega_hat dt)`

`a_mid_n = R(q_half) f_hat + g_n`

`p_(k+1) = p_k + v_k dt + 0.5 a_mid_n dt^2`

`v_(k+1) = v_k + a_mid_n dt`

`q_(k+1) = normalize(q_k tensor_product Exp(omega_hat dt))`

`b_a_(k+1) = b_a_k`

`b_g_(k+1) = b_g_k`

Requirements:

- `dt` must be finite and strictly positive.
- The quaternion must be normalized after propagation.
- The same held IMU sample and midpoint attitude must be used consistently when constructing the interval linearization.

## 5. Continuous-Time Error Dynamics

Define the continuous white-noise vector:

`w = [n_a, n_g, n_ba, n_bg]`

with dimension 12.

The first-order error dynamics are:

`delta_p_dot_n = delta_v_n`

`delta_v_dot_n = -R_nb [f_hat]_x delta_theta_b - R_nb delta_b_a - R_nb n_a`

`delta_theta_dot_b = -[omega_hat]_x delta_theta_b - delta_b_g - n_g`

`delta_b_dot_a = n_ba`

`delta_b_dot_g = n_bg`

These equations correspond to:

- true-minus-nominal additive errors
- right local attitude perturbation
- `R_nb` mapping body coordinates into navigation coordinates

## 6. Continuous-Time Linear System

The linearized system is:

`delta_x_dot = F delta_x + G w`

Using 3 by 3 blocks, the nonzero blocks of `F` are:

- `F[p, v] = I`
- `F[v, theta] = -R_nb [f_hat]_x`
- `F[v, b_a] = -R_nb`
- `F[theta, theta] = -[omega_hat]_x`
- `F[theta, b_g] = -I`

All other blocks are zero.

The nonzero blocks of `G` are:

- `G[v, n_a] = -R_nb`
- `G[theta, n_g] = -I`
- `G[b_a, n_ba] = I`
- `G[b_g, n_bg] = I`

`F` has shape 15 by 15. `G` has shape 15 by 12.

For each propagation interval, `F` and `G` are evaluated using the held corrected IMU sample and the midpoint attitude used by nominal propagation.

## 7. Continuous Process-Noise Model

The continuous white-noise convention is:

`E[w(t) w(tau)^T] = Q_c delta(t - tau)`

The continuous process-noise covariance is:

`Q_c = block_diag(Q_a, Q_g, Q_ba, Q_bg)`

Each block is 3 by 3 and positive semidefinite. Each scalar `sigma` below is a nonnegative continuous-time noise density; squaring it produces the corresponding power spectral density block. These quantities must not be interpreted as discrete per-sample standard deviations.

For the initial isotropic model:

- `Q_a = sigma_a^2 I`
- `Q_g = sigma_g^2 I`
- `Q_ba = sigma_ba^2 I`
- `Q_bg = sigma_bg^2 I`

These values are continuous-time power spectral densities, not per-sample variances. Their units and interpretation must be documented in configuration files.

No default numerical noise values may be invented.

## 8. Covariance Discretization and Propagation

For an interval of duration `dt`, define:

`Phi = exp(F dt)`

`Q_d = integral_0^dt exp(F tau) G Q_c G^T exp(F tau)^T d tau`

The V0.1 reference implementation must compute `Phi` and `Q_d` using the Van Loan block-matrix exponential or an algebraically equivalent exact method for piecewise-constant `F`, `G`, and `Q_c`.

Define:

`L = G Q_c G^T`

Form the 30 by 30 block matrix:

`M = [[-F, L], [0, F^T]] dt`

and partition its exponential as:

`exp(M) = [[A, B], [0, D]]`

Then extract:

`Phi = D^T`

`Q_d = Phi B`

The upper-left block `A` must agree with `Phi^(-1)` to numerical tolerance. The interval duration `dt` is applied exactly once through `M`. After extraction, numerical roundoff may be removed using `Q_d = 0.5 (Q_d + Q_d^T)`, but eigenvalue clipping is not permitted.

The propagated covariance is:

`P_minus = Phi P_plus Phi^T + Q_d`

After propagation:

- enforce numerical symmetry with `P = 0.5 (P + P^T)`
- do not silently clip negative eigenvalues
- raise or report a numerical failure if definiteness checks exceed an approved tolerance

A first-order approximation may be used only in isolated tests that explicitly compare it with the reference discretization.

## 9. GNSS Position Measurement Update

The V0.1 GNSS measurement model is:

`z_p = p_n + n_p`

The prior innovation is:

`r = z_p - p_n_minus`

The observation matrix is:

`H = [I, 0, 0, 0, 0]`

with shape 3 by 15.

The innovation covariance is:

`S = H P_minus H^T + R_p`

where `R_p` is a symmetric positive-definite 3 by 3 measurement-noise covariance.

The Kalman gain is computed by a linear solve:

`K = P_minus H^T S^(-1)`

Code must not form an explicit matrix inverse.

The estimated error correction is:

`delta_x_hat = K r`

## 10. Joseph Covariance Update

Before error injection, update the covariance using Joseph form:

`A = I - K H`

`P_corrected = A P_minus A^T + K R_p K^T`

Then enforce numerical symmetry:

`P_corrected = 0.5 (P_corrected + P_corrected^T)`

The simplified update `(I - K H) P_minus` is not the V0.1 reference update.

## 11. Error Injection and Covariance Reset

Inject the correction into the nominal state:

- `p_n <- p_n + delta_p_n`
- `v_n <- v_n + delta_v_n`
- `q_nb <- normalize(q_nb tensor_product Exp(delta_theta_b))`
- `b_a <- b_a + delta_b_a`
- `b_g <- b_g + delta_b_g`

Reset the estimated error state to zero.

For the right local perturbation, the first-order reset Jacobian is identity except for the attitude block:

`J_reset[theta, theta] = I - 0.5 [delta_theta_b]_x`

The reset covariance is:

`P_plus = J_reset P_corrected J_reset^T`

Then enforce numerical symmetry.

The sign and first-order accuracy of the attitude reset Jacobian must be verified by a dedicated numerical perturbation test before the measurement-update implementation is accepted.

## 12. NIS Definition

For each GNSS update, the normalized innovation squared is:

`NIS = r^T S^(-1) r`

The innovation and `S` must be the prior values computed before applying the measurement update.

The GNSS position NIS has 3 degrees of freedom.

Code must use a linear solve and must reject non-finite inputs or a non-positive-definite `S`.

## 13. NEES Definition

When full ground truth is available, construct the 15-dimensional estimation error:

`e = [p_true - p_hat, v_true - v_hat, Log(q_hat^(-1) tensor_product q_true), b_a_true - b_a_hat, b_g_true - b_g_hat]`

The quaternion error must be converted to the shortest sign-invariant rotation vector.

The normalized estimation error squared is:

`NEES = e^T P^(-1) e`

The full-state NEES has 15 degrees of freedom.

Code must use a linear solve and must reject non-finite inputs or an invalid covariance.

Position-only or other partial-state NEES values must use explicitly documented substate indices and degrees of freedom.

## 14. Required Mathematical Tests

Implementation must not be accepted until tests cover at least:

1. skew-matrix cross-product identity
2. quaternion identity, composition, inverse, and normalization
3. exponential and logarithm round trip, including small angles
4. sign-invariant quaternion comparison
5. nominal stationary IMU propagation in NED
6. constant-velocity propagation
7. constant-angular-rate propagation
8. finite-difference verification of the attitude and bias blocks of `F`
9. dimensions and symmetry of `F`, `G`, `Phi`, `Q_d`, `H`, `S`, and `K`
10. Van Loan discretization against a trusted numerical integral on a small case
11. covariance symmetry and positive-semidefinite tolerance after propagation
12. GNSS residual and observation Jacobian finite-difference check
13. Joseph update symmetry and positive-semidefinite tolerance
14. attitude injection and reset-Jacobian numerical check
15. NIS against a hand-computed 3-dimensional case
16. NEES against a hand-computed 15-dimensional case
17. deterministic repeatability for a fixed random seed
18. explicit rejection of invalid shapes, non-finite values, non-increasing timestamps, and invalid covariances

## 15. Deferred Topics

The following are outside VeraNav V0.1:

- Earth rotation and transport-rate corrections
- geodetic coordinates and Earth curvature
- Coriolis acceleration
- GNSS lever arms
- clock states
- asynchronous interpolation beyond the declared zero-order-hold rule
- adaptive noise estimation
- robust losses and outlier rejection
- visual, LiDAR, wheel, radar, or magnetometer updates
- online spatial or temporal calibration

Any later addition must update this specification, the scientific conventions, and the corresponding tests before implementation.

## References

- Joan Sola, *Quaternion Kinematics for the Error-State Kalman Filter*, arXiv:1711.02508.
- C. F. Van Loan, *Computing Integrals Involving the Matrix Exponential*, IEEE Transactions on Automatic Control, 1978.
