"""Phase 1: verify issued forecasts against realized measurements.

For every (waypoint, source, variable) that has both a forecast and an
actual, we record:
  - whether the measurement point holds true (error within threshold)
  - severity (mild / moderate / severe)
  - the improvement equation (never missing)
  - corrected forecast + residual after the equation
"""

from __future__ import annotations

from .equations import fit_all_equations, fit_improvement_equation
from .models import (
    THRESHOLDS,
    FORECAST_TRUTH_PAIRS,
    Flight,
    ImprovementEquation,
    Observation,
    PointVerification,
    Severity,
    Source,
    Variable,
    identity_equation,
)


def _circular_error(forecast: float, actual: float) -> float:
    d = (actual - forecast + 180.0) % 360.0 - 180.0
    return d


def _error(variable: Variable, forecast: float, actual: float) -> float:
    if variable is Variable.WIND_FROM_DEG:
        return _circular_error(forecast, actual)
    return actual - forecast


def classify_severity(variable: Variable, abs_error: float) -> Severity:
    t = THRESHOLDS[variable]
    if abs_error >= t["severe"]:
        return Severity.SEVERE
    if abs_error >= t["moderate"]:
        return Severity.MODERATE
    return Severity.MILD


def holds_true(variable: Variable, abs_error: float) -> bool:
    return abs_error <= THRESHOLDS[variable]["holds"]


def collect_pairs(
    observations: list[Observation],
    mode: str = "same",
) -> list[tuple[Observation, Observation]]:
    """Pair issued forecasts with truth.

    mode:
      same — forecast and actual from the same Source (demo / QAR self-check)
      crosswalk — GFS/IBM/… vs ERA5/IFS/PIREP/QAR
      auto — both
    """
    by: dict[tuple[int, Source, Variable, bool], Observation] = {}
    for obs in observations:
        by[(obs.waypoint_seq, obs.source, obs.variable, obs.is_forecast)] = obs

    pairs: list[tuple[Observation, Observation]] = []
    seen: set[tuple[int, Source, Source, Variable]] = set()

    def add(forecast: Observation, actual: Observation) -> None:
        key = (forecast.waypoint_seq, forecast.source, actual.source, forecast.variable)
        if key in seen:
            return
        seen.add(key)
        pairs.append((forecast, actual))

    if mode in ("same", "auto"):
        for obs in observations:
            if not obs.is_forecast:
                continue
            actual = by.get((obs.waypoint_seq, obs.source, obs.variable, False))
            if actual is not None:
                add(obs, actual)
    if mode in ("crosswalk", "auto"):
        for obs in observations:
            if not obs.is_forecast:
                continue
            for fc_src, ac_src in FORECAST_TRUTH_PAIRS:
                if obs.source is not fc_src:
                    continue
                actual = by.get((obs.waypoint_seq, ac_src, obs.variable, False))
                if actual is not None:
                    add(obs, actual)
    return pairs


def _pair_observations(
    observations: list[Observation],
) -> list[tuple[Observation, Observation]]:
    return collect_pairs(observations, mode="same")


def _features(forecast_obs: Observation, actual_obs: Observation) -> dict[str, float]:
    feats = {"forecast": forecast_obs.value}
    for extra in ("isa_dev_k", "fl", "alt_ft"):
        if extra in forecast_obs.meta:
            feats[extra] = float(forecast_obs.meta[extra])
        elif extra in actual_obs.meta:
            feats[extra] = float(actual_obs.meta[extra])
    return feats


def _equations_for_pairs(
    pairs: list[tuple[Observation, Observation]],
) -> dict[tuple[Source, Source, Variable], ImprovementEquation]:
    buckets: dict[tuple[Source, Source, Variable], tuple[list[float], list[float]]] = {}
    for forecast_obs, actual_obs in pairs:
        key = (forecast_obs.source, actual_obs.source, forecast_obs.variable)
        bucket = buckets.setdefault(key, ([], []))
        bucket[0].append(forecast_obs.value)
        bucket[1].append(actual_obs.value)
    out: dict[tuple[Source, Source, Variable], ImprovementEquation] = {}
    for (fc_src, ac_src, variable), (forecasts, actuals) in buckets.items():
        eq = fit_improvement_equation(variable, fc_src, forecasts, actuals)
        out[(fc_src, ac_src, variable)] = eq
    return out


def verify_flight(flight: Flight, *, pairing: str = "same") -> list[PointVerification]:
    pairs = collect_pairs(flight.observations, mode=pairing)
    equations = _equations_for_pairs(pairs)
    # Same-source MOS still available under (source, variable) for Phase 2 apply.
    same_source = fit_all_equations(flight.observations)
    results: list[PointVerification] = []
    for forecast_obs, actual_obs in pairs:
        variable = forecast_obs.variable
        source = forecast_obs.source
        eq = equations.get((source, actual_obs.source, variable)) or same_source.get(
            (source, variable)
        ) or identity_equation(variable, source)
        err = _error(variable, forecast_obs.value, actual_obs.value)
        abs_err = abs(err)
        feats = _features(forecast_obs, actual_obs)
        corrected = eq.apply(feats)
        corr_err = _error(variable, corrected, actual_obs.value)
        results.append(
            PointVerification(
                waypoint_seq=forecast_obs.waypoint_seq,
                source=source,
                variable=variable,
                forecast=forecast_obs.value,
                actual=actual_obs.value,
                error=err,
                abs_error=abs_err,
                holds_true=holds_true(variable, abs_err),
                severity=classify_severity(variable, abs_err),
                equation=eq,
                corrected=corrected,
                corrected_error=corr_err,
                features=feats,
                truth_source=actual_obs.source,
            )
        )
    _assert_equations(results)
    return results


def _assert_equations(results: list[PointVerification]) -> None:
    missing = [r for r in results if r.equation is None]
    if missing:
        raise RuntimeError("improvement equation missing on verification rows")
    for r in results:
        if not r.equation.form:
            raise RuntimeError("improvement equation has empty form")
        if "forecast" not in r.equation.coefficients and r.equation.n_samples == 0:
            raise RuntimeError("identity equation must include forecast coefficient")


def equations_from_verifications(
    results: list[PointVerification],
) -> dict[tuple[Source, Variable], ImprovementEquation]:
    out: dict[tuple[Source, Variable], ImprovementEquation] = {}
    for r in results:
        out[(r.source, r.variable)] = r.equation
    return out
