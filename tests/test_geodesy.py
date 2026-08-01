from __future__ import annotations

import unittest

import numpy as np

from veranav.geodesy import (
    WGS84_SEMI_MAJOR_AXIS_M,
    ecef_to_local_ned,
    geodetic_to_ecef,
    geodetic_to_local_ned,
)


class GeodesyTest(unittest.TestCase):
    def test_equator_prime_meridian(self) -> None:
        result = geodetic_to_ecef(0.0, 0.0, 0.0)
        np.testing.assert_allclose(
            result,
            np.array([WGS84_SEMI_MAJOR_AXIS_M, 0.0, 0.0]),
            rtol=0.0,
            atol=1.0e-9,
        )

    def test_anchor_maps_to_ned_origin(self) -> None:
        geodetic = np.array([[30.0, 114.0, 50.0]])
        result = geodetic_to_local_ned(geodetic, 30.0, 114.0, 50.0)
        np.testing.assert_allclose(result, np.zeros((1, 3)), atol=1.0e-9)

    def test_local_direction_signs(self) -> None:
        geodetic = np.array(
            [
                [30.00001, 114.0, 50.0],
                [30.0, 114.00001, 50.0],
                [30.0, 114.0, 51.0],
            ]
        )
        result = geodetic_to_local_ned(geodetic, 30.0, 114.0, 50.0)
        self.assertGreater(result[0, 0], 0.0)
        self.assertGreater(result[1, 1], 0.0)
        self.assertLess(result[2, 2], 0.0)

    def test_ecef_shape_validation(self) -> None:
        with self.assertRaises(ValueError):
            ecef_to_local_ned(np.zeros((2, 2)), 0.0, 0.0, 0.0)

    def test_invalid_geodetic_ranges(self) -> None:
        with self.assertRaises(ValueError):
            geodetic_to_ecef(91.0, 0.0, 0.0)
        with self.assertRaises(ValueError):
            geodetic_to_ecef(0.0, 181.0, 0.0)

    def test_input_arrays_are_not_modified(self) -> None:
        latitude = np.array([0.0, 30.0])
        longitude = np.array([0.0, 114.0])
        height = np.array([0.0, 10.0])
        copies = (latitude.copy(), longitude.copy(), height.copy())
        result = geodetic_to_ecef(latitude, longitude, height)
        self.assertEqual(result.shape, (2, 3))
        np.testing.assert_array_equal(latitude, copies[0])
        np.testing.assert_array_equal(longitude, copies[1])
        np.testing.assert_array_equal(height, copies[2])


if __name__ == "__main__":
    unittest.main()
