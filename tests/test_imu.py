"""Tests for IMU validation and nominal-state propagation."""

from __future__ import annotations

import math
import unittest

import numpy as np

from veranav.imu import ImuSample, STANDARD_GRAVITY_MPS2, propagate_nominal
from veranav.math import quat_equivalent, quat_exp
from veranav.state import NominalState


def stationary_sample(timestamp: float) -> ImuSample:
    return ImuSample(
        timestamp=timestamp,
        specific_force_b=[0.0, 0.0, -STANDARD_GRAVITY_MPS2],
        angular_rate_b=np.zeros(3),
    )


class ImuSampleTest(unittest.TestCase):
    def test_copies_inputs_and_stores_readonly_arrays(self) -> None:
        force = np.array([1.0, 2.0, 3.0])
        rate = np.array([0.1, 0.2, 0.3])
        sample = ImuSample(1.0, force, rate)
        force[0] = 99.0
        rate[0] = 99.0
        self.assertEqual(sample.specific_force_b[0], 1.0)
        self.assertEqual(sample.angular_rate_b[0], 0.1)
        self.assertFalse(sample.specific_force_b.flags.writeable)
        self.assertFalse(sample.angular_rate_b.flags.writeable)

    def test_distinct_samples_use_identity_equality(self) -> None:
        first = ImuSample(0.0, np.zeros(3), np.zeros(3))
        second = ImuSample(0.0, np.zeros(3), np.zeros(3))
        self.assertTrue(first == first)
        self.assertFalse(first == second)

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            ImuSample(np.nan, np.zeros(3), np.zeros(3))
        with self.assertRaises(ValueError):
            ImuSample(0.0, np.zeros(2), np.zeros(3))
        with self.assertRaises(ValueError):
            ImuSample(0.0, np.zeros(3), [0.0, np.inf, 0.0])


class NominalPropagationTest(unittest.TestCase):
    def test_stationary_state_in_ned(self) -> None:
        state = NominalState.identity(timestamp=3.0)
        result = propagate_nominal(state, stationary_sample(3.0), 0.01)
        self.assertAlmostEqual(result.timestamp, 3.01, places=15)
        np.testing.assert_allclose(result.position_n, np.zeros(3), atol=1.0e-15)
        np.testing.assert_allclose(result.velocity_n, np.zeros(3), atol=1.0e-15)
        self.assertTrue(
            quat_equivalent(
                result.quaternion_nb,
                [1.0, 0.0, 0.0, 0.0],
            )
        )

    def test_constant_velocity(self) -> None:
        state = NominalState(
            timestamp=1.0,
            position_n=[2.0, -1.0, 4.0],
            velocity_n=[3.0, -2.0, 0.5],
            quaternion_nb=[1.0, 0.0, 0.0, 0.0],
            accel_bias_b=np.zeros(3),
            gyro_bias_b=np.zeros(3),
        )
        result = propagate_nominal(state, stationary_sample(1.0), 2.0)
        np.testing.assert_allclose(
            result.position_n,
            np.array([8.0, -5.0, 5.0]),
            rtol=0.0,
            atol=2.0e-15,
        )
        np.testing.assert_allclose(
            result.velocity_n,
            state.velocity_n,
            rtol=0.0,
            atol=1.0e-15,
        )

    def test_constant_specific_force(self) -> None:
        state = NominalState.identity()
        sample = ImuSample(
            timestamp=0.0,
            specific_force_b=[2.0, 0.0, -STANDARD_GRAVITY_MPS2],
            angular_rate_b=np.zeros(3),
        )
        result = propagate_nominal(state, sample, 1.0)
        np.testing.assert_allclose(
            result.position_n,
            np.array([1.0, 0.0, 0.0]),
            rtol=0.0,
            atol=1.0e-15,
        )
        np.testing.assert_allclose(
            result.velocity_n,
            np.array([2.0, 0.0, 0.0]),
            rtol=0.0,
            atol=1.0e-15,
        )

    def test_constant_angular_rate(self) -> None:
        state = NominalState.identity()
        rate = 0.4
        sample = ImuSample(
            timestamp=0.0,
            specific_force_b=[0.0, 0.0, -STANDARD_GRAVITY_MPS2],
            angular_rate_b=[0.0, 0.0, rate],
        )
        result = propagate_nominal(state, sample, 2.0)
        self.assertTrue(
            quat_equivalent(
                result.quaternion_nb,
                quat_exp([0.0, 0.0, 0.8]),
                atol=1.0e-14,
            )
        )
        np.testing.assert_allclose(result.position_n, np.zeros(3), atol=1.0e-14)
        np.testing.assert_allclose(result.velocity_n, np.zeros(3), atol=1.0e-14)

    def test_translation_uses_midpoint_attitude(self) -> None:
        state = NominalState.identity()
        sample = ImuSample(
            timestamp=0.0,
            specific_force_b=[1.0, 0.0, -STANDARD_GRAVITY_MPS2],
            angular_rate_b=[0.0, 0.0, math.pi / 2.0],
        )
        result = propagate_nominal(state, sample, 1.0)
        acceleration = np.array(
            [math.sqrt(0.5), math.sqrt(0.5), 0.0],
        )
        np.testing.assert_allclose(
            result.velocity_n,
            acceleration,
            rtol=0.0,
            atol=2.0e-15,
        )
        np.testing.assert_allclose(
            result.position_n,
            0.5 * acceleration,
            rtol=0.0,
            atol=1.0e-15,
        )

    def test_biases_are_removed_and_preserved(self) -> None:
        state = NominalState(
            timestamp=0.0,
            position_n=np.zeros(3),
            velocity_n=np.zeros(3),
            quaternion_nb=[1.0, 0.0, 0.0, 0.0],
            accel_bias_b=[0.2, -0.1, 0.3],
            gyro_bias_b=[0.01, -0.02, 0.03],
        )
        sample = ImuSample(
            timestamp=0.0,
            specific_force_b=[
                0.2,
                -0.1,
                0.3 - STANDARD_GRAVITY_MPS2,
            ],
            angular_rate_b=[0.01, -0.02, 0.03],
        )
        result = propagate_nominal(state, sample, 0.5)
        np.testing.assert_allclose(result.position_n, np.zeros(3), atol=1.0e-15)
        np.testing.assert_allclose(result.velocity_n, np.zeros(3), atol=1.0e-15)
        np.testing.assert_array_equal(result.accel_bias_b, state.accel_bias_b)
        np.testing.assert_array_equal(result.gyro_bias_b, state.gyro_bias_b)

    def test_propagation_does_not_mutate_inputs(self) -> None:
        state = NominalState.identity()
        sample = stationary_sample(0.0)
        state_snapshot = (
            state.position_n.copy(),
            state.velocity_n.copy(),
            state.quaternion_nb.copy(),
            state.accel_bias_b.copy(),
            state.gyro_bias_b.copy(),
        )
        sample_snapshot = (
            sample.specific_force_b.copy(),
            sample.angular_rate_b.copy(),
        )
        result = propagate_nominal(state, sample, 0.1)

        np.testing.assert_array_equal(state.position_n, state_snapshot[0])
        np.testing.assert_array_equal(state.velocity_n, state_snapshot[1])
        np.testing.assert_array_equal(state.quaternion_nb, state_snapshot[2])
        np.testing.assert_array_equal(state.accel_bias_b, state_snapshot[3])
        np.testing.assert_array_equal(state.gyro_bias_b, state_snapshot[4])
        np.testing.assert_array_equal(sample.specific_force_b, sample_snapshot[0])
        np.testing.assert_array_equal(sample.angular_rate_b, sample_snapshot[1])
        self.assertIsNot(result.position_n, state.position_n)
        self.assertIsNot(result.quaternion_nb, state.quaternion_nb)

    def test_rejects_invalid_propagation_arguments(self) -> None:
        state = NominalState.identity()
        sample = stationary_sample(0.0)
        for dt in (0.0, -0.1, np.nan, np.inf):
            with self.subTest(dt=dt):
                with self.assertRaises(ValueError):
                    propagate_nominal(state, sample, dt)

        for gravity in (0.0, -1.0, np.nan, np.inf):
            with self.subTest(gravity=gravity):
                with self.assertRaises(ValueError):
                    propagate_nominal(
                        state,
                        sample,
                        0.1,
                        gravity_magnitude=gravity,
                    )

        large_state = NominalState.identity(timestamp=1.0e20)
        large_sample = stationary_sample(1.0e20)
        with self.assertRaises(ValueError):
            propagate_nominal(large_state, large_sample, 1.0e-3)

        with self.assertRaises(ValueError):
            propagate_nominal(state, stationary_sample(1.0), 0.1)
        with self.assertRaises(TypeError):
            propagate_nominal(object(), sample, 0.1)
        with self.assertRaises(TypeError):
            propagate_nominal(state, object(), 0.1)


if __name__ == "__main__":
    unittest.main()
