"""Phase 2: apply Phase 1 equations to raw forecasts."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ImprovementEquation, Source, Variable, identity_equation


@dataclass
class CorrectedForecast:
    waypoint_seq: int
    variable: Variable
    source: Source
    raw: float
    corrected: float
    equation: ImprovementEquation
    features: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "waypoint_seq": self.waypoint_seq,
            "variable": self.variable.value,
            "source": self.source.value,
            "raw": self.raw,
            "corrected": self.corrected,
            "features": self.features,
            "equation": self.equation.to_dict(),
        }


def correct_value(
    variable: Variable,
    source: Source,
    raw: float,
    equations: dict[tuple[Source, Variable], ImprovementEquation],
    features: dict[str, float] | None = None,
) -> tuple[float, ImprovementEquation, dict[str, float]]:
    eq = equations.get((source, variable)) or identity_equation(variable, source)
    feats = dict(features or {})
    feats.setdefault("forecast", raw)
    return eq.apply(feats), eq, feats


def correct_along_route(
    waypoints: list[dict],
    equations: dict[tuple[Source, Variable], ImprovementEquation],
    source: Source = Source.WEATHER_MODEL,
) -> list[CorrectedForecast]:
    """waypoints: dicts with seq, wind_kt, wind_from_deg, temp_c, optional isa_dev_k/fl."""
    out: list[CorrectedForecast] = []
    for wp in waypoints:
        seq = int(wp["seq"])
        extras = {k: float(wp[k]) for k in ("isa_dev_k", "fl", "alt_ft") if k in wp}
        for variable, key in (
            (Variable.WIND_KT, "wind_kt"),
            (Variable.WIND_FROM_DEG, "wind_from_deg"),
            (Variable.TEMP_C, "temp_c"),
        ):
            if key not in wp:
                continue
            raw = float(wp[key])
            corr, eq, feats = correct_value(variable, source, raw, equations, extras)
            out.append(
                CorrectedForecast(
                    waypoint_seq=seq,
                    variable=variable,
                    source=source,
                    raw=raw,
                    corrected=corr,
                    equation=eq,
                    features=feats,
                )
            )
    return out
