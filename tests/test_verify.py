from __future__ import annotations

import unittest

from airpath.demo import build_demo_flight
from airpath.models import Severity, Source, Variable
from airpath.stats import phase1_ready, score_verifications
from airpath.verify import verify_flight


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.flight = build_demo_flight()
        self.rows = verify_flight(self.flight)

    def test_every_row_has_equation(self):
        self.assertGreater(len(self.rows), 20)
        for row in self.rows:
            self.assertIsNotNone(row.equation)
            self.assertTrue(row.equation.form)
            self.assertIn("forecast", row.equation.coefficients)

    def test_holds_true_and_severity_populated(self):
        sevs = {row.severity for row in self.rows}
        self.assertTrue(sevs <= {Severity.MILD, Severity.MODERATE, Severity.SEVERE})
        self.assertTrue(any(row.holds_true for row in self.rows))

    def test_weather_model_wind_equation_recovers_bias(self):
        wind = [
            r
            for r in self.rows
            if r.source is Source.WEATHER_MODEL and r.variable is Variable.WIND_KT
        ]
        eq = wind[0].equation
        self.assertAlmostEqual(eq.intercept, -8.0, places=5)
        self.assertAlmostEqual(eq.coefficients["forecast"], 1.12, places=5)
        self.assertLess(eq.rmse_corrected, 0.05)

    def test_phase1_ready_from_demo(self):
        scores = score_verifications(self.rows)
        self.assertTrue(phase1_ready(scores))
        model_wind = next(
            s
            for s in scores
            if s.source is Source.WEATHER_MODEL and s.variable is Variable.WIND_KT
        )
        self.assertTrue(model_wind.suitable_for_phase2)
        self.assertLess(model_wind.rmse_corrected, model_wind.rmse)
