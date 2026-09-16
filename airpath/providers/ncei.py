"""NOAA NCEI global-hourly (ISD) surface archive."""

from __future__ import annotations

import urllib.parse
from typing import Any

from ..models import Flight, Observation, Source, Variable, Waypoint
from ..timeutil import iso_z, parse_utc
from .http import PlannedRequest

NCEI_DATA = "https://www.ncei.noaa.gov/access/services/data/v1"


def _bbox(lat: float, lon: float, pad: float = 0.2) -> str:
    # NCEI: north, west, south, east
    return f"{lat+pad:.3f},{lon-pad:.3f},{lat-pad:.3f},{lon+pad:.3f}"


def plan_global_hourly(flight: Flight) -> list[PlannedRequest]:
    out = []
    for icao, wp in (
        (flight.origin_icao, flight.waypoints[0]),
        (flight.dest_icao, flight.waypoints[-1]),
    ):
        start = parse_utc(wp.eta_utc)
        qs = urllib.parse.urlencode(
            {
                "dataset": "global-hourly",
                "dataTypes": "TMP,WND",
                "startDate": start.strftime("%Y-%m-%dT00:00:00"),
                "endDate": start.strftime("%Y-%m-%dT23:59:59"),
                "boundingBox": _bbox(wp.position.lat, wp.position.lon),
                "format": "json",
                "limit": 100,
            }
        )
        out.append(
            PlannedRequest(
                provider="ncei",
                product="global_hourly",
                url=f"{NCEI_DATA}?{qs}",
                waypoint_seq=wp.seq,
                icao=icao,
            )
        )
    return out


def parse_global_hourly(payload: Any, waypoint: Waypoint, icao: str) -> list[Observation]:
    rows = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        rows = payload.get("results") or payload.get("data") or []
    if not rows:
        return []
    target = parse_utc(waypoint.eta_utc).timestamp()

    def row_ts(row: dict) -> float:
        stamp = row.get("DATE") or row.get("date") or row.get("TIMESTAMP")
        if not stamp:
            return float("inf")
        try:
            return parse_utc(str(stamp)).timestamp()
        except ValueError:
            return float("inf")

    row = min(rows, key=lambda r: abs(row_ts(r) - target))
    temp = parse_isd_tmp(row.get("TMP") or row.get("tmp") or row.get("TEMP"))
    wind_kt, wdir = parse_isd_wnd(row.get("WND") or row.get("wnd") or row.get("WIND"))
    issued = iso_z(str(row.get("DATE") or row.get("date") or waypoint.eta_utc))
    meta = {
        "provider": "ncei",
        "product": "global_hourly",
        "station": row.get("STATION") or icao,
        "fl": 0.0,
    }
    out = []
    for variable, value in (
        (Variable.TEMP_C, temp),
        (Variable.WIND_KT, wind_kt),
        (Variable.WIND_FROM_DEG, wdir),
    ):
        if value is None:
            continue
        out.append(
            Observation(waypoint.seq, Source.NCEI, variable, float(value), issued, False, dict(meta))
        )
    return out


def parse_isd_tmp(raw: Any) -> float | None:
    """ISD TMP is +0380,1 → 38.0 °C (tenths). Plain numbers pass through."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        val = float(raw)
        return val / 10.0 if abs(val) > 80 else val
    text = str(raw).split(",")[0].strip()
    if text in {"", "+9999", "9999", "M"}:
        return None
    try:
        return float(text) / 10.0
    except ValueError:
        return None


def parse_isd_wnd(raw: Any) -> tuple[float | None, float | None]:
    """ISD WND: DIR,DIRQ,TYPE,SPD,SPDQ — speed tenths of m/s."""
    if raw is None or raw == "":
        return None, None
    if isinstance(raw, dict):
        spd = raw.get("speed")
        direc = raw.get("direction")
        kt = float(spd) * 1.943844 if spd is not None else None
        return kt, float(direc) if direc is not None else None
    parts = str(raw).split(",")
    wdir = None
    wind_kt = None
    if parts:
        try:
            d = float(parts[0])
            if d < 361:
                wdir = d
        except ValueError:
            pass
    if len(parts) >= 4:
        try:
            spd_ms = float(parts[3]) / 10.0
            if spd_ms < 900:
                wind_kt = spd_ms * 1.943844
        except ValueError:
            pass
    return wind_kt, wdir
