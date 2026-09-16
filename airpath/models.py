"""Shared data models for Emirates Air Path / Intensity."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

from .geo import LatLon


class Source(str, Enum):
    WEATHER_MODEL = "weather_model"
    METAR = "metar"
    AIRCRAFT_SENSOR = "aircraft_sensor"
    SIMULATION = "simulation"
    ERA5 = "era5"
    ECMWF_IFS = "ecmwf_ifs"
    ECMWF_AIFS = "ecmwf_aifs"
    GFS = "gfs"
    PIREP = "pirep"
    RAOB = "raob"
    NCEI = "ncei"
    AWC_WINDS = "awc_winds"
    IBM_AVIATION = "ibm_aviation"
    METEOBLUE = "meteoblue"
    ADS_B = "ads_b"


# Forecast products that Phase 2 may apply after a suitable Phase 1 score.
FORECAST_PRODUCTS: frozenset[Source] = frozenset(
    {
        Source.WEATHER_MODEL,
        Source.GFS,
        Source.ECMWF_IFS,
        Source.ECMWF_AIFS,
        Source.AWC_WINDS,
        Source.IBM_AVIATION,
        Source.METEOBLUE,
    }
)

# Issued forecast → independent truth. Same-source pairing stays the default
# for synthetic demos; match-from-archives uses this crosswalk.
FORECAST_TRUTH_PAIRS: tuple[tuple[Source, Source], ...] = (
    (Source.GFS, Source.ERA5),
    (Source.GFS, Source.ECMWF_IFS),
    (Source.GFS, Source.AIRCRAFT_SENSOR),
    (Source.GFS, Source.PIREP),
    (Source.WEATHER_MODEL, Source.ERA5),
    (Source.WEATHER_MODEL, Source.ECMWF_IFS),
    (Source.WEATHER_MODEL, Source.AIRCRAFT_SENSOR),
    (Source.IBM_AVIATION, Source.ERA5),
    (Source.IBM_AVIATION, Source.ECMWF_IFS),
    (Source.IBM_AVIATION, Source.AIRCRAFT_SENSOR),
    (Source.METEOBLUE, Source.ERA5),
    (Source.METEOBLUE, Source.ECMWF_IFS),
    (Source.METEOBLUE, Source.AIRCRAFT_SENSOR),
    (Source.AWC_WINDS, Source.PIREP),
    (Source.AWC_WINDS, Source.ERA5),
    (Source.AWC_WINDS, Source.ECMWF_IFS),
    (Source.ECMWF_IFS, Source.ERA5),
    (Source.ECMWF_IFS, Source.AIRCRAFT_SENSOR),
    (Source.ECMWF_IFS, Source.PIREP),
    (Source.ECMWF_AIFS, Source.ERA5),
    (Source.ECMWF_AIFS, Source.ECMWF_IFS),
    (Source.ECMWF_AIFS, Source.AIRCRAFT_SENSOR),
    (Source.ECMWF_AIFS, Source.PIREP),
)


class Severity(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


class Variable(str, Enum):
    WIND_KT = "wind_kt"
    WIND_FROM_DEG = "wind_from_deg"
    TEMP_C = "temp_c"
    ISA_DEV_K = "isa_dev_k"
    FUEL_FLOW_KG_H = "fuel_flow_kg_h"
    GROUND_SPEED_KT = "ground_speed_kt"


# Operational error thresholds used for "holds true" + severity.
THRESHOLDS: dict[Variable, dict[str, float]] = {
    Variable.WIND_KT: {"holds": 5.0, "moderate": 5.0, "severe": 15.0},
    Variable.WIND_FROM_DEG: {"holds": 15.0, "moderate": 15.0, "severe": 40.0},
    Variable.TEMP_C: {"holds": 2.0, "moderate": 2.0, "severe": 4.0},
    Variable.ISA_DEV_K: {"holds": 2.0, "moderate": 2.0, "severe": 4.0},
    Variable.FUEL_FLOW_KG_H: {"holds": 150.0, "moderate": 150.0, "severe": 400.0},
    Variable.GROUND_SPEED_KT: {"holds": 20.0, "moderate": 20.0, "severe": 50.0},
}


@dataclass(frozen=True)
class Waypoint:
    seq: int
    position: LatLon
    fl: float
    eta_utc: str  # ISO-8601


@dataclass
class Observation:
    """One measured or forecast value at a waypoint from a named source."""

    waypoint_seq: int
    source: Source
    variable: Variable
    value: float
    issued_at_utc: str
    is_forecast: bool
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImprovementEquation:
    """Always-on correction: y_hat = intercept + Σ coef_i * feature_i.

    Identity (intercept=0, coef_forecast=1) is valid before enough samples
    exist. After Phase 1 fit, coefficients are MOS / bias-correction.
    """

    variable: str
    source: str
    intercept: float
    coefficients: dict[str, float]
    n_samples: int
    rmse_raw: float
    rmse_corrected: float
    form: str

    def apply(self, features: dict[str, float]) -> float:
        y = self.intercept
        for name, coef in self.coefficients.items():
            y += coef * features.get(name, 0.0)
        return y

    @property
    def improvement_ratio(self) -> float:
        if self.rmse_raw <= 1e-12:
            return 1.0
        return self.rmse_corrected / self.rmse_raw

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def identity_equation(variable: Variable, source: Source) -> ImprovementEquation:
    return ImprovementEquation(
        variable=variable.value,
        source=source.value,
        intercept=0.0,
        coefficients={"forecast": 1.0},
        n_samples=0,
        rmse_raw=0.0,
        rmse_corrected=0.0,
        form="corrected = forecast",
    )


@dataclass
class PointVerification:
    waypoint_seq: int
    source: Source
    variable: Variable
    forecast: float
    actual: float
    error: float
    abs_error: float
    holds_true: bool
    severity: Severity
    equation: ImprovementEquation
    corrected: float
    corrected_error: float
    features: dict[str, float]
    truth_source: Source | None = None

    def to_dict(self) -> dict[str, Any]:
        truth = self.truth_source or self.source
        return {
            "waypoint_seq": self.waypoint_seq,
            "source": self.source.value,
            "truth_source": truth.value,
            "variable": self.variable.value,
            "forecast": self.forecast,
            "actual": self.actual,
            "error": self.error,
            "abs_error": self.abs_error,
            "holds_true": self.holds_true,
            "severity": self.severity.value,
            "corrected": self.corrected,
            "corrected_error": self.corrected_error,
            "features": self.features,
            "equation": self.equation.to_dict(),
        }


@dataclass
class SourceScore:
    source: Source
    variable: Variable
    n: int
    mae: float
    rmse: float
    bias: float
    hit_rate: float
    mild: int
    moderate: int
    severe: int
    suitability: float
    suitable_for_phase2: bool
    equation: ImprovementEquation
    rmse_corrected: float
    truth_source: Source | None = None

    def to_dict(self) -> dict[str, Any]:
        truth = self.truth_source or self.source
        return {
            "source": self.source.value,
            "truth_source": truth.value,
            "variable": self.variable.value,
            "n": self.n,
            "mae": self.mae,
            "rmse": self.rmse,
            "bias": self.bias,
            "hit_rate": self.hit_rate,
            "mild": self.mild,
            "moderate": self.moderate,
            "severe": self.severe,
            "suitability": self.suitability,
            "suitable_for_phase2": self.suitable_for_phase2,
            "rmse_corrected": self.rmse_corrected,
            "equation": self.equation.to_dict(),
        }


@dataclass
class Flight:
    flight_id: str
    origin_icao: str
    dest_icao: str
    origin: LatLon
    dest: LatLon
    aircraft_type: str
    departure_utc: str
    waypoints: list[Waypoint]
    observations: list[Observation]
