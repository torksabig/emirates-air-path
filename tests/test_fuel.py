from __future__ import annotations

import unittest

from airpath.fuel import cruise_fuel_flow_kg_h, ground_speed_kt, segment_fuel_kg, tas_kt
from airpath.geo import LatLon, along_track_wind_kt, haversine_nm
from airpath.isa import isa_temperature_c


class FuelGeoTests(unittest.TestCase):
    def test_headwind_burns_more_fuel(self):
        oat = isa_temperature_c(35000)
        tas = tas_kt(0.84, oat)
        ff = cruise_fuel_flow_kg_h(350, oat)
        dist = 100.0
        fuel_tail = segment_fuel_kg(dist, ground_speed_kt(tas, 40), ff)
        fuel_head = segment_fuel_kg(dist, ground_speed_kt(tas, -40), ff)
        self.assertGreater(fuel_head, fuel_tail)

    def test_hotter_than_isa_raises_fuel_flow(self):
        isa = isa_temperature_c(35000)
        cool = cruise_fuel_flow_kg_h(350, isa - 5)
        hot = cruise_fuel_flow_kg_h(350, isa + 5)
        self.assertGreater(hot, cool)

    def test_tailwind_sign(self):
        # Track east (90), wind from west (270) => tailwind.
        self.assertGreater(along_track_wind_kt(50, 270, 90), 40)
        # Wind from east (90), track east => headwind.
        self.assertLess(along_track_wind_kt(50, 90, 90), -40)

    def test_omdb_egll_distance(self):
        omdb = LatLon(25.2532, 55.3657)
        egll = LatLon(51.4700, -0.4543)
        nm = haversine_nm(omdb, egll)
        self.assertTrue(2800 < nm < 3100)
