"""Open-Meteo GFS / ECMWF IFS / ERA5-archive sampling along a track."""

from __future__ import annotations

import urllib.parse
from typing import Any

from ..geo import LatLon
from ..isa import isa_deviation_k, nearest_pressure_level_hpa
from ..models import Observation, Source, Variable, Waypoint
from ..timeutil import date_utc, iso_z, nearest_index
from .http import PlannedRequest

GFS_FORECAST = "https://api.open-meteo.com/v1/gfs"
HISTORICAL_FORECAST = "https://historical-forecast-api.open-meteo.com/v1/forecast"
ERA5_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

_PRESSURE_HOURLY = (
    "temperature_{level}hPa",
    "wind_speed_{level}hPa",
    "wind_direction_{level}hPa",
)
_SURFACE_HOURLY = "temperature_2m,wind_speed_10m,wind_direction_10m"


def pressure_hourly(level_hpa: int) -> str:
    return ",".join(name.format(level=level_hpa) for name in _PRESSURE_HOURLY)


def openmeteo_url(
    host: str,
    position: LatLon,
    start: str,
    end: str,
    hourly: str,
    *,
    models: str | None = None,
    wind_unit: str = "kn",
) -> str:
    params = {
        "latitude": f"{position.lat:.4f}",
        "longitude": f"{position.lon:.4f}",
        "start_date": start,
        "end_date": end,
        "hourly": hourly,
        "wind_speed_unit": wind_unit,
        "timezone": "UTC",
    }
    if models:
        params["models"] = models
    return f"{host}?{urllib.parse.urlencode(params)}"


def plan_pressure_level(
    provider: str,
    waypoint: Waypoint,
    *,
    models: str | None,
    historical: bool,
) -> PlannedRequest:
    level = nearest_pressure_level_hpa(waypoint.fl * 100.0)
    day = date_utc(waypoint.eta_utc)
    host = HISTORICAL_FORECAST if historical else GFS_FORECAST
    if provider == "era5" and not models:
        host = ERA5_ARCHIVE
        hourly = _SURFACE_HOURLY
        product = "surface"
    else:
        hourly = pressure_hourly(level)
        product = "pressure_level"
    url = openmeteo_url(
        host,
        waypoint.position,
        day,
        day,
        hourly,
        models=models,
    )
    return PlannedRequest(
        provider=provider,
        product=product,
        url=url,
        waypoint_seq=waypoint.seq,
        meta={"level_hpa": level, "models": models, "historical": historical},
    )


def plan_gfs(waypoints: list[Waypoint], *, historical: bool) -> list[PlannedRequest]:
    return [
        plan_pressure_level("gfs", wp, models="gfs_global", historical=historical)
        for wp in waypoints
    ]


def plan_ecmwf_ifs(waypoints: list[Waypoint]) -> list[PlannedRequest]:
    return [
        plan_pressure_level("ecmwf_ifs", wp, models="ecmwf_ifs", historical=True)
        for wp in waypoints
    ]


def plan_era5(waypoints: list[Waypoint]) -> list[PlannedRequest]:
    # Surface archive always; pressure-level ERA5 is CDS (see era5_cds_request).
    return [
        plan_pressure_level("era5", wp, models=None, historical=True) for wp in waypoints
    ]


def era5_cds_request(waypoint: Waypoint) -> dict[str, Any]:
    from .ecmwf import era5_cds_request as _cds

    return _cds(waypoint)


def parse_openmeteo_hourly(
    payload: dict[str, Any],
    waypoint: Waypoint,
    source: Source,
    *,
    is_forecast: bool,
    provider: str,
) -> list[Observation]:
    hourly = payload.get("hourly") or {}
    times = [str(t) for t in (hourly.get("time") or [])]
    idx = nearest_index(times, waypoint.eta_utc)
    if idx is None:
        return []
    level = nearest_pressure_level_hpa(waypoint.fl * 100.0)
    temp = _first_present(
        hourly,
        idx,
        f"temperature_{level}hPa",
        "temperature_2m",
    )
    wind = _first_present(
        hourly,
        idx,
        f"wind_speed_{level}hPa",
        "wind_speed_10m",
    )
    wdir = _first_present(
        hourly,
        idx,
        f"wind_direction_{level}hPa",
        "wind_direction_10m",
    )
    issued = iso_z(times[idx])
    meta = {
        "provider": provider,
        "fl": waypoint.fl,
        "alt_ft": waypoint.fl * 100.0,
        "level_hpa": level,
        "valid_time": issued,
    }
    if temp is not None:
        meta["isa_dev_k"] = isa_deviation_k(temp, waypoint.fl * 100.0)
    out: list[Observation] = []
    specs = (
        (Variable.TEMP_C, temp),
        (Variable.WIND_KT, wind),
        (Variable.WIND_FROM_DEG, wdir),
    )
    if temp is not None:
        specs = specs + ((Variable.ISA_DEV_K, meta["isa_dev_k"]),)
    for variable, value in specs:
        if value is None:
            continue
        out.append(
            Observation(
                waypoint_seq=waypoint.seq,
                source=source,
                variable=variable,
                value=float(value),
                issued_at_utc=issued,
                is_forecast=is_forecast,
                meta=dict(meta),
            )
        )
    return out


def _first_present(hourly: dict, idx: int, *keys: str) -> float | None:
    for key in keys:
        series = hourly.get(key)
        if not series or idx >= len(series) or series[idx] is None:
            continue
        return float(series[idx])
    return None
