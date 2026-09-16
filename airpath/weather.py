"""Optional live weather: Open-Meteo pressure-level wind + temperature.

Network is not required for Phase 1/2 tests. Call fetch_upper_air() only
when the operator wants a live snapshot along a route.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .geo import LatLon
from .isa import nearest_pressure_level_hpa

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_S = 20


@dataclass
class UpperAirSample:
    position: LatLon
    level_hpa: int
    temp_c: float | None
    wind_kt: float | None
    wind_from_deg: float | None
    time_utc: str | None
    raw: dict


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "emirates-air-path/0.1"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_upper_air(position: LatLon, alt_ft: float, *, wind_unit: str = "kn") -> UpperAirSample:
    level = nearest_pressure_level_hpa(alt_ft)
    hourly = ",".join(
        [
            f"temperature_{level}hPa",
            f"wind_speed_{level}hPa",
            f"wind_direction_{level}hPa",
        ]
    )
    qs = urllib.parse.urlencode(
        {
            "latitude": f"{position.lat:.4f}",
            "longitude": f"{position.lon:.4f}",
            "hourly": hourly,
            "wind_speed_unit": wind_unit,
            "timezone": "UTC",
            "forecast_days": 1,
        }
    )
    payload = _get(f"{OPEN_METEO}?{qs}")
    hourly_block = payload.get("hourly") or {}
    times = hourly_block.get("time") or []
    temps = hourly_block.get(f"temperature_{level}hPa") or []
    speeds = hourly_block.get(f"wind_speed_{level}hPa") or []
    dirs_ = hourly_block.get(f"wind_direction_{level}hPa") or []
    idx = 0
    return UpperAirSample(
        position=position,
        level_hpa=level,
        temp_c=_num(temps[idx] if temps else None),
        wind_kt=_num(speeds[idx] if speeds else None),
        wind_from_deg=_num(dirs_[idx] if dirs_ else None),
        time_utc=str(times[idx]) if times else None,
        raw=payload,
    )


def _num(value) -> float | None:
    if value is None:
        return None
    return float(value)
