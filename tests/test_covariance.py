"""Tests for Van Loan discretization and covariance propagation."""

from __future__ import annotations

import unittest

import numpy as np
from scipy.linalg import expm

from veranav.covariance import (
    CovariancePropagation,
    ProcessNoise,
    propagate_covariance,
    propagate_error_covariance,
    van_loan_discretize,
)
from veranav.imu import ImuSample, STANDARD_GRAVITY_MPS2
from veranav.linearization import continuous_error_dynamics
from veranav.state import NominalState


class ProcessNoiseTest(unittest.TestCase):
    def test_continuous_covariance_diagonal(self) -> None:
        noise = ProcessNoise(0.1, 0.2, 0.3, 0.4)
        covariance = noise.continuous_covariance()
        expected = np.repeat(np.array([0.01, 0.04, 0.09, 0.16]), 3)
        np.testing.assert_allclose(np.diag(covariance), expected, atol=1.0e-15)
        np.testing.assert_array_equal(
            covariance - np.diag(np.diag(covariance)),
            np.zeros((12, 12)),
        )
        self.assertFalse(covariance.flags.writeable)

    def test_accepts_zero_noise(self) -> None:
        covariance = ProcessNoise(0.0, 0.0, 0.0, 0.0).continuous_covariance()
        np.testing.assert_array_equal(covariance, np.zeros((12, 12)))

    def test_rejects_invalid_noise_values(self) -> None:
        for value in (-1.0, np.nan, np.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ProcessNoise(value, 0.1, 0.1, 0.1)


class VanLoanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.system = np.zeros((15, 15))
        self.mapping = np.zeros((15, 12))
        self.mapping[0:12, 0:12] = np.eye(12)
        self.continuous = np.diag(np.linspace(0.1, 1.2, 12))

    def test_zero_dynamics_exact_solution(self) -> None:
        transition, process = van_loan_discretize(
            self.system,
            self.mapping,
            self.continuous,
            0.25,
        )
        expected_density = self.mapping @ self.continuous @ self.mapping.T
        np.testing.assert_allclose(transition, np.eye(15), atol=1.0e-15)
        np.testing.assert_allclose(process, expected_density * 0.25, atol=1.0e-15)

    def test_transition_matches_direct_matrix_exponential(self) -> None:
        rng = np.random.default_rng(9)
        system = rng.normal(scale=0.1, size=(15, 15))
        transition, _ = van_loan_discretize(
            system,
            self.mapping,
            self.continuous,
            0.03,
        )
        np.testing.assert_allclose(
            transition,
            expm(system * 0.03),
            rtol=0.0,
            atol=2.0e-15,
        )

    def test_process_covariance_matches_numerical_quadrature(self) -> None:
        rng = np.random.default_rng(10)
        system = rng.normal(scale=0.08, size=(15, 15))
        mapping = rng.normal(scale=0.2, size=(15, 12))
        continuous = np.diag(np.linspace(0.01, 0.12, 12))
        dt = 0.02
        _, process = van_loan_discretize(system, mapping, continuous, dt)
        density = mapping @ continuous @ mapping.T

        nodes = 2_001
        times = np.linspace(0.0, dt, nodes)
        integral = np.zeros((15, 15))
        previous = density
        for index in range(1, nodes):
            phi = expm(system * times[index])
            current = phi @ density @ phi.T
            step = times[index] - times[index - 1]
            integral += 0.5 * (previous + current) * step
            previous = current
        np.testing.assert_allclose(process, integral, rtol=0.0, atol=2.0e-11)

    def test_discrete_semigroup_property(self) -> None:
        rng = np.random.default_rng(11)
        system = rng.normal(scale=0.05, size=(15, 15))
        mapping = rng.normal(scale=0.1, size=(15, 12))
        continuous = np.diag(np.linspace(0.02, 0.13, 12))
        phi_a, q_a = van_loan_discretize(system, mapping, continuous, 0.01)
        phi_b, q_b = van_loan_discretize(system, mapping, continuous, 0.02)
        phi_total, q_total = van_loan_discretize(
            system,
            mapping,
            continuous,
            0.03,
        )
        np.testing.assert_allclose(phi_b @ phi_a, phi_total, atol=3.0e-15)
        np.testing.assert_allclose(
            phi_b @ q_a @ phi_b.T + q_b,
            q_total,
            atol=3.0e-15,
        )

    def test_process_covariance_is_symmetric_psd(self) -> None:
        rng = np.random.default_rng(12)
        system = rng.normal(scale=0.2, size=(15, 15))
        mapping = rng.normal(scale=0.3, size=(15, 12))
        continuous = np.diag(np.linspace(0.001, 0.012, 12))
        _, process = van_loan_discretize(system, mapping, continuous, 0.05)
        np.testing.assert_allclose(process, process.T, atol=1.0e-15)
        self.assertGreaterEqual(float(np.min(np.linalg.eigvalsh(process))), -1.0e-14)

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            van_loan_discretize(np.zeros((14, 14)), self.mapping, self.continuous, 0.1)
        with self.assertRaises(ValueError):
            van_loan_discretize(self.system, np.zeros((15, 11)), self.continuous, 0.1)
        nonsymmetric = self.continuous.copy()
        nonsymmetric[0, 1] = 1.0
        with self.assertRaises(ValueError):
            van_loan_discretize(self.system, self.mapping, nonsymmetric, 0.1)
        negative = self.continuous.copy()
        negative[0, 0] = -1.0
        with self.assertRaises(ValueError):
            van_loan_discretize(self.system, self.mapping, negative, 0.1)
        for dt in (0.0, -0.1, np.nan, np.inf):
            with self.subTest(dt=dt):
                with self.assertRaises(ValueError):
                    van_loan_discretize(
                        self.system,
                        self.mapping,
                        self.continuous,
                        dt,
                    )


class CovariancePropagationTest(unittest.TestCase):
    def test_formula_and_input_immutability(self) -> None:
        covariance = np.diag(np.linspace(0.1, 1.5, 15))
        transition = np.eye(15)
        transition[0:3, 3:6] = 0.1 * np.eye(3)
        process = 0.01 * np.eye(15)
        snapshots = [array.copy() for array in (covariance, transition, process)]
        result = propagate_covariance(covariance, transition, process)
        expected = transition @ covariance @ transition.T + process
        np.testing.assert_allclose(result, expected, atol=1.0e-15)
        for actual, snapshot in zip(
            (covariance, transition, process), snapshots, strict=True
        ):
            np.testing.assert_array_equal(actual, snapshot)

    def test_rejects_invalid_covariances(self) -> None:
        valid = np.eye(15)
        nonsymmetric = valid.copy()
        nonsymmetric[0, 1] = 0.1
        with self.assertRaises(ValueError):
            propagate_covariance(nonsymmetric, valid, valid)
        negative = valid.copy()
        negative[0, 0] = -0.1
        with self.assertRaises(ValueError):
            propagate_covariance(negative, valid, valid)
        with self.assertRaises(ValueError):
            propagate_covariance(valid, np.eye(14), valid)

    def test_end_to_end_propagation(self) -> None:
        state = NominalState.identity(timestamp=0.0)
        sample = ImuSample(
            timestamp=0.0,
            specific_force_b=[0.0, 0.0, -STANDARD_GRAVITY_MPS2],
            angular_rate_b=np.zeros(3),
        )
        prior = np.diag(np.linspace(0.01, 0.15, 15))
        noise = ProcessNoise(0.02, 0.003, 0.0002, 0.00003)
        result = propagate_error_covariance(
            state,
            sample,
            prior,
            noise,
            0.01,
        )
        self.assertIsInstance(result, CovariancePropagation)
        self.assertEqual(result.transition.shape, (15, 15))
        self.assertEqual(result.process_covariance.shape, (15, 15))
        self.assertEqual(result.covariance.shape, (15, 15))
        for matrix in (
            result.transition,
            result.process_covariance,
            result.covariance,
        ):
            self.assertFalse(matrix.flags.writeable)
        self.assertGreaterEqual(
            float(np.min(np.linalg.eigvalsh(result.covariance))),
            -1.0e-13,
        )

    def test_end_to_end_matches_explicit_steps(self) -> None:
        state = NominalState.identity(timestamp=0.0)
        sample = ImuSample(
            timestamp=0.0,
            specific_force_b=[1.0, -0.5, -STANDARD_GRAVITY_MPS2],
            angular_rate_b=[0.01, -0.02, 0.03],
        )
        prior = 0.1 * np.eye(15)
        noise = ProcessNoise(0.02, 0.003, 0.0002, 0.00003)
        system, mapping = continuous_error_dynamics(state, sample)
        transition, process = van_loan_discretize(
            system,
            mapping,
            noise.continuous_covariance(),
            0.02,
        )
        expected = propagate_covariance(prior, transition, process)
        result = propagate_error_covariance(
            state,
            sample,
            prior,
            noise,
            0.02,
        )
        np.testing.assert_allclose(result.transition, transition, atol=1.0e-15)
        np.testing.assert_allclose(result.process_covariance, process, atol=1.0e-15)
        np.testing.assert_allclose(result.covariance, expected, atol=1.0e-15)

    def test_rejects_invalid_process_noise_type(self) -> None:
        state = NominalState.identity()
        sample = ImuSample(0.0, np.zeros(3), np.zeros(3))
        with self.assertRaises(TypeError):
            propagate_error_covariance(state, sample, np.eye(15), object(), 0.1)


if __name__ == "__main__":
    unittest.main()
