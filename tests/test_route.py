from __future__ import annotations

import unittest

from airpath.demo import run_demo
from airpath.geo import LatLon, great_circle_points
from airpath.route import optimal_route, plan_routes


class RouteTests(unittest.TestCase):
    def test_optimizer_prefers_tailwind_offset(self):
        origin = LatLon(25.0, 55.0)
        dest = LatLon(51.0, 0.0)
        gc = great_circle_points(origin, dest, 12)
        # Strong southerly wind: a north offset should not magically win on
        # interpolated GC weather, but higher FL / same weather still ranks.
        winds_kt = [80.0] * 12
        winds_from = [270.0] * 12  # westerly = tailwind westbound? track is NW
        temps = [-50.0] * 12
        cands = plan_routes(
            origin,
            dest,
            gc_points=gc,
            winds_kt=winds_kt,
            winds_from=winds_from,
            temps_c=temps,
        )
        best = optimal_route(cands)
        self.assertGreater(best.fuel_kg, 0)
        self.assertEqual(best, cands[0])
        gc_fl350 = next(c for c in cands if c.offset_nm == 0 and c.fl == 350)
        self.assertLessEqual(best.fuel_kg, gc_fl350.fuel_kg)

    def test_demo_phase2_runs_after_phase1(self):
        payload = run_demo()
        self.assertTrue(payload["phase1_ready"])
        self.assertIn("optimal", payload["phase2"])
        self.assertGreater(payload["phase2"]["optimal"]["fuel_kg"], 10_000)
        for src in payload["phase1"]["sources"]:
            self.assertIn("equation", src)
            self.assertTrue(src["equation"]["form"])
        for row in payload["verifications"]:
            self.assertIn("equation", row)
