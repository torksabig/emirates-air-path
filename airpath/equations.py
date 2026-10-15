"""Phase 1 improvement equations.

Every forecast→actual pair is scored with an equation that can later
correct a raw forecast. The default is identity; with ≥ MIN_SAMPLES
we fit MOS (actual ≈ a + b·forecast) and keep it only if it does not
increase RMSE.
"""

from __future__ import annotations

import math
from collections import defaultdict

from .models import (
    ImprovementEquation,
    Observation,
    Source,
    Variable,
    identity_equation,
)

MIN_SAMPLES = 4
FORECAST_FEATURE = "forecast"


def _rmse(pairs: list[tuple[float, float]]) -> float:
    if not pairs:
        return 0.0
    return math.sqrt(sum((a - b) ** 2 for a, b in pairs) / len(pairs))


def fit_mos(forecasts: list[float], actuals: list[float]) -> tuple[float, float]:
    """Ordinary least squares: actual = a + b * forecast."""
    n = len(forecasts)
    if n == 0:
        return 0.0, 1.0
    mean_x = sum(forecasts) / n
    mean_y = sum(actuals) / n
    var_x = sum((x - mean_x) ** 2 for x in forecasts)
    if var_x < 1e-12:
        return mean_y - mean_x, 1.0  # pure bias
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(forecasts, actuals))
    b = cov / var_x
    a = mean_y - b * mean_x
    return a, b


def format_equation(intercept: float, coefficients: dict[str, float]) -> str:
    parts = [f"{intercept:.4f}"]
    for name, coef in coefficients.items():
        sign = "+" if coef >= 0 else "-"
        parts.append(f"{sign} {abs(coef):.4f}*{name}")
    return "corrected = " + " ".join(parts)


def fit_improvement_equation(
    variable: Variable,
    source: Source,
    forecasts: list[float],
    actuals: list[float],
) -> ImprovementEquation:
    """Return the best valid equation. Never returns None."""
    n = len(forecasts)
    if n != len(actuals):
        raise ValueError("forecasts and actuals length mismatch")
    if n < MIN_SAMPLES:
        eq = identity_equation(variable, source)
        raw = _rmse(list(zip(forecasts, actuals))) if n else 0.0
        return ImprovementEquation(
            variable=variable.value,
            source=source.value,
            intercept=eq.intercept,
            coefficients=dict(eq.coefficients),
            n_samples=n,
            rmse_raw=raw,
            rmse_corrected=raw,
            form=eq.form,
        )

    a, b = fit_mos(forecasts, actuals)
    corrected = [a + b * x for x in forecasts]
    rmse_raw = _rmse(list(zip(forecasts, actuals)))
    rmse_corr = _rmse(list(zip(corrected, actuals)))

    # Keep identity if MOS does not improve (overfit / noise).
    if rmse_corr > rmse_raw + 1e-9:
        return ImprovementEquation(
            variable=variable.value,
            source=source.value,
            intercept=0.0,
            coefficients={FORECAST_FEATURE: 1.0},
            n_samples=n,
            rmse_raw=rmse_raw,
            rmse_corrected=rmse_raw,
            form="corrected = forecast",
        )

    coefs = {FORECAST_FEATURE: b}
    return ImprovementEquation(
        variable=variable.value,
        source=source.value,
        intercept=a,
        coefficients=coefs,
        n_samples=n,
        rmse_raw=rmse_raw,
        rmse_corrected=rmse_corr,
        form=format_equation(a, coefs),
    )


def fit_all_equations(
    observations: list[Observation],
) -> dict[tuple[Source, Variable], ImprovementEquation]:
    """Fit one equation per (source, variable) from forecast/actual pairs."""
    buckets: dict[tuple[Source, Variable], dict[int, dict[str, float]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for obs in observations:
        key = (obs.source, obs.variable)
        kind = "forecast" if obs.is_forecast else "actual"
        buckets[key][obs.waypoint_seq][kind] = obs.value

    out: dict[tuple[Source, Variable], ImprovementEquation] = {}
    for (source, variable), by_wp in buckets.items():
        forecasts: list[float] = []
        actuals: list[float] = []
        for vals in by_wp.values():
            if "forecast" in vals and "actual" in vals:
                forecasts.append(vals["forecast"])
                actuals.append(vals["actual"])
        out[(source, variable)] = fit_improvement_equation(
            variable, source, forecasts, actuals
        )
    return out
