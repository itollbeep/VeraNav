"""Tests for the VeraNav nominal-state container."""

from __future__ import annotations

import unittest

import numpy as np

from veranav.state import NominalState


class NominalStateTest(unittest.TestCase):
    def test_identity_state(self) -> None:
        state = NominalState.identity(timestamp=2.5)
        self.assertEqual(state.timestamp, 2.5)
        np.testing.assert_array_equal(state.position_n, np.zeros(3))
        np.testing.assert_array_equal(state.velocity_n, np.zeros(3))
        np.testing.assert_array_equal(
            state.quaternion_nb,
            np.array([1.0, 0.0, 0.0, 0.0]),
        )
        np.testing.assert_array_equal(state.accel_bias_b, np.zeros(3))
        np.testing.assert_array_equal(state.gyro_bias_b, np.zeros(3))

    def test_constructor_normalizes_quaternion(self) -> None:
        state = NominalState(
            timestamp=0.0,
            position_n=[1.0, 2.0, 3.0],
            velocity_n=[4.0, 5.0, 6.0],
            quaternion_nb=[2.0, 0.0, 0.0, 0.0],
            accel_bias_b=[0.1, 0.2, 0.3],
            gyro_bias_b=[0.4, 0.5, 0.6],
        )
        np.testing.assert_array_equal(
            state.quaternion_nb,
            np.array([1.0, 0.0, 0.0, 0.0]),
        )

    def test_constructor_copies_inputs_and_stores_readonly_arrays(self) -> None:
        position = np.array([1.0, 2.0, 3.0])
        state = NominalState(
            timestamp=0.0,
            position_n=position,
            velocity_n=np.zeros(3),
            quaternion_nb=[1.0, 0.0, 0.0, 0.0],
            accel_bias_b=np.zeros(3),
            gyro_bias_b=np.zeros(3),
        )
        position[0] = 99.0
        self.assertEqual(state.position_n[0], 1.0)
        self.assertFalse(state.position_n.flags.writeable)
        self.assertFalse(state.velocity_n.flags.writeable)
        self.assertFalse(state.quaternion_nb.flags.writeable)
        self.assertFalse(state.accel_bias_b.flags.writeable)
        self.assertFalse(state.gyro_bias_b.flags.writeable)
        with self.assertRaises(ValueError):
            state.position_n[0] = 7.0

    def test_copy_has_independent_arrays(self) -> None:
        state = NominalState.identity()
        copied = state.copy()
        self.assertIsNot(state.position_n, copied.position_n)
        self.assertIsNot(state.velocity_n, copied.velocity_n)
        self.assertIsNot(state.quaternion_nb, copied.quaternion_nb)
        np.testing.assert_array_equal(state.position_n, copied.position_n)
        np.testing.assert_array_equal(state.quaternion_nb, copied.quaternion_nb)

    def test_distinct_states_use_identity_equality(self) -> None:
        state = NominalState.identity()
        copied = state.copy()
        self.assertTrue(state == state)
        self.assertFalse(state == copied)

    def test_rejects_invalid_timestamp(self) -> None:
        with self.assertRaises(ValueError):
            NominalState.identity(timestamp=np.inf)

    def test_rejects_invalid_vectors_and_quaternion(self) -> None:
        base = dict(
            timestamp=0.0,
            position_n=np.zeros(3),
            velocity_n=np.zeros(3),
            quaternion_nb=[1.0, 0.0, 0.0, 0.0],
            accel_bias_b=np.zeros(3),
            gyro_bias_b=np.zeros(3),
        )
        for field, value in (
            ("position_n", [1.0, 2.0]),
            ("velocity_n", [0.0, np.nan, 0.0]),
            ("quaternion_nb", [0.0, 0.0, 0.0, 0.0]),
            ("accel_bias_b", np.zeros(4)),
            ("gyro_bias_b", [0.0, 0.0, np.inf]),
        ):
            with self.subTest(field=field):
                values = dict(base)
                values[field] = value
                with self.assertRaises(ValueError):
                    NominalState(**values)


if __name__ == "__main__":
    unittest.main()
