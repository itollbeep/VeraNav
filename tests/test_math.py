"""Unit tests for VeraNav quaternion and rotation utilities."""

from __future__ import annotations

import math
import unittest

import numpy as np

from veranav.math import (
    quat_conjugate,
    quat_equivalent,
    quat_exp,
    quat_inverse,
    quat_log,
    quat_multiply,
    quat_normalize,
    quat_to_rotation_matrix,
    rotation_matrix_to_quat,
    skew,
)


class SkewMatrixTest(unittest.TestCase):
    def test_cross_product_identity(self) -> None:
        vector = np.array([1.2, -0.7, 2.5])
        operand = np.array([-0.3, 4.0, 1.1])
        np.testing.assert_allclose(
            skew(vector) @ operand,
            np.cross(vector, operand),
            rtol=0.0,
            atol=1.0e-14,
        )

    def test_is_antisymmetric(self) -> None:
        matrix = skew([1.0, 2.0, 3.0])
        np.testing.assert_allclose(matrix.T, -matrix, rtol=0.0, atol=0.0)

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            skew([1.0, 2.0])
        with self.assertRaises(ValueError):
            skew([1.0, np.nan, 3.0])


class QuaternionAlgebraTest(unittest.TestCase):
    def test_normalization(self) -> None:
        np.testing.assert_allclose(
            quat_normalize([2.0, 0.0, 0.0, 0.0]),
            np.array([1.0, 0.0, 0.0, 0.0]),
            rtol=0.0,
            atol=0.0,
        )

    def test_normalization_rejects_zero(self) -> None:
        with self.assertRaises(ValueError):
            quat_normalize([0.0, 0.0, 0.0, 0.0])

    def test_identity_product(self) -> None:
        identity = np.array([1.0, 0.0, 0.0, 0.0])
        quaternion = quat_exp([0.2, -0.1, 0.3])
        np.testing.assert_allclose(quat_multiply(identity, quaternion), quaternion)
        np.testing.assert_allclose(quat_multiply(quaternion, identity), quaternion)

    def test_conjugate_and_inverse(self) -> None:
        quaternion = np.array([2.0, -1.0, 0.5, 3.0])
        np.testing.assert_allclose(
            quat_conjugate(quaternion),
            np.array([2.0, 1.0, -0.5, -3.0]),
        )
        np.testing.assert_allclose(
            quat_multiply(quaternion, quat_inverse(quaternion)),
            np.array([1.0, 0.0, 0.0, 0.0]),
            atol=1.0e-15,
        )

    def test_inverse_rejects_zero(self) -> None:
        with self.assertRaises(ValueError):
            quat_inverse([0.0, 0.0, 0.0, 0.0])

    def test_composition_matches_rotation_matrices(self) -> None:
        first = quat_exp([0.2, -0.4, 0.1])
        second = quat_exp([-0.3, 0.05, 0.25])
        product = quat_multiply(first, second)
        np.testing.assert_allclose(
            quat_to_rotation_matrix(product),
            quat_to_rotation_matrix(first) @ quat_to_rotation_matrix(second),
            rtol=0.0,
            atol=2.0e-15,
        )


class QuaternionMapTest(unittest.TestCase):
    def test_exp_zero(self) -> None:
        np.testing.assert_allclose(
            quat_exp([0.0, 0.0, 0.0]),
            np.array([1.0, 0.0, 0.0, 0.0]),
        )

    def test_small_angle_approximation(self) -> None:
        rotation_vector = np.array([1.0e-10, -2.0e-10, 3.0e-10])
        np.testing.assert_allclose(
            quat_exp(rotation_vector)[1:],
            0.5 * rotation_vector,
            rtol=0.0,
            atol=1.0e-25,
        )

    def test_exp_log_round_trip(self) -> None:
        cases = (
            np.array([1.0e-10, -2.0e-10, 3.0e-10]),
            np.array([0.2, -0.4, 0.1]),
            np.array([math.pi - 1.0e-8, 0.0, 0.0]),
        )
        for rotation_vector in cases:
            with self.subTest(rotation_vector=rotation_vector):
                np.testing.assert_allclose(
                    quat_log(quat_exp(rotation_vector)),
                    rotation_vector,
                    rtol=0.0,
                    atol=2.0e-12,
                )

    def test_log_is_sign_invariant(self) -> None:
        quaternion = quat_exp([0.4, -0.2, 0.1])
        np.testing.assert_allclose(quat_log(quaternion), quat_log(-quaternion))

    def test_equivalence_is_sign_invariant(self) -> None:
        quaternion = quat_exp([0.1, 0.2, -0.3])
        self.assertTrue(quat_equivalent(quaternion, -quaternion))
        self.assertFalse(
            quat_equivalent(quaternion, quat_exp([0.1, 0.2, -0.29]), atol=1.0e-6)
        )

    def test_rejects_invalid_quaternion_shapes(self) -> None:
        with self.assertRaises(ValueError):
            quat_exp([1.0, 2.0])
        with self.assertRaises(ValueError):
            quat_log([1.0, 0.0, 0.0])
        with self.assertRaises(ValueError):
            quat_equivalent([1.0, 0.0, 0.0, 0.0], [1.0, 0.0, np.inf, 0.0])


class RotationMatrixConversionTest(unittest.TestCase):
    def test_identity_conversion(self) -> None:
        identity_quaternion = np.array([1.0, 0.0, 0.0, 0.0])
        identity_matrix = np.eye(3)
        np.testing.assert_allclose(
            quat_to_rotation_matrix(identity_quaternion), identity_matrix
        )
        self.assertTrue(
            quat_equivalent(rotation_matrix_to_quat(identity_matrix), identity_quaternion)
        )

    def test_rotation_matrix_is_proper(self) -> None:
        matrix = quat_to_rotation_matrix(quat_exp([0.3, -0.5, 0.7]))
        np.testing.assert_allclose(matrix.T @ matrix, np.eye(3), atol=4.0e-16)
        self.assertAlmostEqual(float(np.linalg.det(matrix)), 1.0, places=14)

    def test_quaternion_matrix_round_trip(self) -> None:
        cases = (
            np.array([0.2, -0.4, 0.1]),
            np.array([math.pi, 0.0, 0.0]),
            np.array([0.0, math.pi, 0.0]),
            np.array([0.0, 0.0, math.pi]),
        )
        for rotation_vector in cases:
            with self.subTest(rotation_vector=rotation_vector):
                quaternion = quat_exp(rotation_vector)
                recovered = rotation_matrix_to_quat(
                    quat_to_rotation_matrix(quaternion)
                )
                self.assertTrue(quat_equivalent(quaternion, recovered, atol=2.0e-14))

    def test_rejects_non_rotation_matrices(self) -> None:
        with self.assertRaises(ValueError):
            rotation_matrix_to_quat(np.eye(2))
        with self.assertRaises(ValueError):
            rotation_matrix_to_quat(np.diag([1.0, 1.0, -1.0]))
        invalid = np.eye(3)
        invalid[0, 1] = 0.1
        with self.assertRaises(ValueError):
            rotation_matrix_to_quat(invalid)
        with self.assertRaises(ValueError):
            rotation_matrix_to_quat(np.full((3, 3), np.nan))


if __name__ == "__main__":
    unittest.main()
