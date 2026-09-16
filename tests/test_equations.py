from __future__ import annotations

import unittest

from airpath.equations import MIN_SAMPLES, fit_improvement_equation, fit_mos
from airpath.models import Source, Variable, identity_equation


class EquationTests(unittest.TestCase):
    def test_identity_always_defined(self):
        eq = identity_equation(Variable.WIND_KT, Source.WEATHER_MODEL)
        self.assertEqual(eq.apply({"forecast": 42.0}), 42.0)
        self.assertIn("forecast", eq.coefficients)
        self.assertTrue(eq.form)

    def test_mos_recovers_known_line(self):
        a, b = -8.0, 1.12
        actuals = [40.0 + 3.0 * i for i in range(12)]
        forecasts = [(y - a) / b for y in actuals]
        fa, fb = fit_mos(forecasts, actuals)
        self.assertAlmostEqual(fa, a, places=6)
        self.assertAlmostEqual(fb, b, places=6)

    def test_fit_keeps_identity_when_too_few_samples(self):
        eq = fit_improvement_equation(
            Variable.TEMP_C, Source.METAR, [10.0, 11.0], [10.5, 11.2]
        )
        self.assertLess(eq.n_samples, MIN_SAMPLES)
        self.assertEqual(eq.coefficients["forecast"], 1.0)
        self.assertEqual(eq.intercept, 0.0)

    def test_fit_improves_rmse(self):
        a, b = 1.4, 0.94
        actuals = [-50.0 + i * 0.4 for i in range(16)]
        forecasts = [(y - a) / b for y in actuals]
        eq = fit_improvement_equation(
            Variable.TEMP_C, Source.WEATHER_MODEL, forecasts, actuals
        )
        self.assertLess(eq.rmse_corrected, eq.rmse_raw)
        self.assertAlmostEqual(eq.intercept, a, places=5)
        self.assertAlmostEqual(eq.coefficients["forecast"], b, places=5)
        for x, y in zip(forecasts, actuals):
            self.assertAlmostEqual(eq.apply({"forecast": x}), y, places=5)

    def test_never_returns_worse_than_identity(self):
        # Uncorrelated noise — MOS may not help; identity is allowed.
        forecasts = [float(i) for i in range(10)]
        actuals = [50.0 - i for i in range(10)]
        eq = fit_improvement_equation(
            Variable.WIND_KT, Source.SIMULATION, forecasts, actuals
        )
        self.assertLessEqual(eq.rmse_corrected, eq.rmse_raw + 1e-9)
        self.assertTrue(eq.form.startswith("corrected ="))
