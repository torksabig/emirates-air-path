"""Commercial aviation APIs — IBM Weather Company and Meteoblue.

URL builders and tolerant parsers. Live calls require env keys; tests inject
payloads and never hit the network.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

from ..isa import nearest_pressure_level_hpa
from ..models import Observation, Source, Variable, Waypoint
from ..timeutil import iso_z, nearest_index
from .http import AuthRequired, PlannedRequest, require_env

IBM_HOST = "https://api.weather.com/v3/wx/forecast/hourly/2day"
METEOBLUE_HOST = "https://my.meteoblue.com/packages/aviation-1h"


def plan_ibm(waypoints: list[Waypoint], *, api_key: str | None = None) -> list[PlannedRequest]:
    key = api_key if api_key is not None else require_env("IBM_WEATHER_API_KEY")
    out = []
    for wp in waypoints:
        qs = urllib.parse.urlencode(
            {
                "geocode": f"{wp.position.lat:.4f},{wp.position.lon:.4f}",
                "units": "m",
                "language": "en-US",
                "format": "json",
                "apiKey": key,
            }
        )
        out.append(
            PlannedRequest(
                provider="ibm",
                product="aviation",
                url=f"{IBM_HOST}?{qs}",
                waypoint_seq=wp.seq,
                meta={"fl": wp.fl},
            )
        )
    return out


def plan_meteoblue(waypoints: list[Waypoint], *, api_key: str | None = None) -> list[PlannedRequest]:
    key = api_key if api_key is not None else require_env("METEOBLUE_API_KEY")
    out = []
    for wp in waypoints:
        level = nearest_pressure_level_hpa(wp.fl * 100.0)
        qs = urllib.parse.urlencode(
            {
                "lat": f"{wp.position.lat:.4f}",
                "lon": f"{wp.position.lon:.4f}",
                "apikey": key,
                "format": "json",
                "tz": "UTC",
                "windspeed": "kn",
            }
        )
        out.append(
            PlannedRequest(
                provider="meteoblue",
                product="aviation_fl",
                url=f"{METEOBLUE_HOST}?{qs}",
                waypoint_seq=wp.seq,
                meta={"fl": wp.fl, "level_hpa": level},
            )
        )
    return out


def parse_ibm(payload: Any, waypoint: Waypoint) -> list[Observation]:
    block = payload.get("hourly") if isinstance(payload, dict) else None
    if block is None and isinstance(payload, dict):
        block = payload
    if not isinstance(block, dict):
        return []
    times = [str(t) for t in (block.get("validTimeUtc") or block.get("time") or [])]
    idx = nearest_index(times, waypoint.eta_utc) if times else 0
    temp = _at(block.get("temperature") or block.get("temperatureChange"), idx)
    # IBM metric wind is often km/h or m/s; prefer explicit knots if present.
    wind = _at(
        block.get("windSpeedKts") or block.get("windSpeed") or block.get("windspeed"),
        idx,
    )
    if wind is not None and block.get("windSpeedKts") is None and block.get("windSpeed"):
        wind = float(wind) * 1.943844  # assume m/s in metric units=m
    wdir = _at(block.get("windDirection") or block.get("wind_dir"), idx)
    issued = iso_z(times[idx] if times else waypoint.eta_utc)
    return _pack(Source.IBM_AVIATION, waypoint, issued, True, "ibm", temp, wind, wdir)


def parse_meteoblue(payload: Any, waypoint: Waypoint) -> list[Observation]:
    block = None
    if isinstance(payload, dict):
        block = payload.get("data_1h") or payload.get("data_fl") or payload.get("hourly") or payload
    if not isinstance(block, dict):
        return []
    times = [str(t) for t in (block.get("time") or [])]
    idx = nearest_index(times, waypoint.eta_utc) if times else 0
    fl = int(waypoint.fl)
    temp = _at(
        block.get(f"temperature_FL{fl}")
        or block.get("temperature")
        or block.get("temperature_250hPa"),
        idx,
    )
    wind = _at(
        block.get(f"windspeed_FL{fl}")
        or block.get("windspeed")
        or block.get("wind_speed_250hPa"),
        idx,
    )
    wdir = _at(
        block.get(f"winddirection_FL{fl}")
        or block.get("winddirection")
        or block.get("wind_direction_250hPa"),
        idx,
    )
    issued = iso_z(times[idx] if times else waypoint.eta_utc)
    return _pack(Source.METEOBLUE, waypoint, issued, True, "meteoblue", temp, wind, wdir)


def _at(series: Any, idx: int) -> float | None:
    if not isinstance(series, list) or idx >= len(series) or series[idx] is None:
        return None
    try:
        return float(series[idx])
    except (TypeError, ValueError):
        return None


def _pack(source, waypoint, issued, is_forecast, provider, temp, wind, wdir) -> list[Observation]:
    meta = {"provider": provider, "fl": waypoint.fl, "alt_ft": waypoint.fl * 100.0}
    out = []
    for variable, value in (
        (Variable.TEMP_C, temp),
        (Variable.WIND_KT, wind),
        (Variable.WIND_FROM_DEG, wdir),
    ):
        if value is None:
            continue
        out.append(
            Observation(waypoint.seq, source, variable, float(value), issued, is_forecast, dict(meta))
        )
    return out


def missing_keys() -> list[str]:
    missing = []
    for name in ("IBM_WEATHER_API_KEY", "METEOBLUE_API_KEY", "CDSAPI_KEY"):
        try:
            require_env(name)
        except AuthRequired:
            missing.append(name)
    return missing
