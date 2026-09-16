from __future__ import annotations

import math
import unittest

from airpath.isa import (
    isa_deviation_k,
    isa_pressure_hpa,
    isa_temperature_c,
    isa_temperature_k,
    nearest_pressure_level_hpa,
)


class IsaTests(unittest.TestCase):
    def test_sl_temperature(self):
        self.assertAlmostEqual(isa_temperature_k(0), 288.15, places=2)
        self.assertAlmostEqual(isa_temperature_c(0), 15.0, places=2)

    def test_fl350_temperature(self):
        t = isa_temperature_c(35000)
        self.assertTrue(-56.0 < t < -52.0)

    def test_isa_deviation_zero_at_isa(self):
        t_c = isa_temperature_c(35000)
        self.assertAlmostEqual(isa_deviation_k(t_c, 35000), 0.0, places=6)

    def test_pressure_decreases(self):
        self.assertGreater(isa_pressure_hpa(0), isa_pressure_hpa(35000))
        self.assertAlmostEqual(isa_pressure_hpa(0), 1013.25, places=1)

    def test_fl350_maps_to_250hpa(self):
        self.assertEqual(nearest_pressure_level_hpa(35000), 250)
