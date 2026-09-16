"""NOAA Aviation Weather Center Data API — METAR, PIREP, FD winds."""

from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone
from typing import Any

from ..geo import LatLon, haversine_nm
from ..models import Flight, Observation, Source, Variable, Waypoint
from ..timeutil import iso_z, parse_utc
from .http import PlannedRequest

AWC = "https://aviationweather.gov/api/data"
PIREP_MAX_NM = 60.0
PIREP_MAX_FL = 40.0


def plan_metar(flight: Flight) -> list[PlannedRequest]:
    ids = f"{flight.origin_icao},{flight.dest_icao}"
    date = parse_utc(flight.departure_utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    qs = urllib.parse.urlencode(
        {"ids": ids, "format": "json", "hours": 6, "date": date}
    )
    return [
        PlannedRequest(
            provider="awc",
            product="metar",
            url=f"{AWC}/metar?{qs}",
            icao=ids,
        )
    ]


def plan_pirep(flight: Flight) -> list[PlannedRequest]:
    lats = [w.position.lat for w in flight.waypoints]
    lons = [w.position.lon for w in flight.waypoints]
    bbox = f"{min(lats)-2:.2f},{min(lons)-2:.2f},{max(lats)+2:.2f},{max(lons)+2:.2f}"
    date = parse_utc(flight.departure_utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    qs = urllib.parse.urlencode({"bbox": bbox, "format": "json", "hours": 12, "date": date})
    return [
        PlannedRequest(provider="awc", product="pirep", url=f"{AWC}/pirep?{qs}", meta={"bbox": bbox})
    ]


def plan_windtemp(*, region: str = "us", level: str = "high") -> list[PlannedRequest]:
    qs = urllib.parse.urlencode({"region": region, "level": level, "format": "json"})
    return [
        PlannedRequest(
            provider="awc",
            product="windtemp",
            url=f"{AWC}/windtemp?{qs}",
            meta={"region": region, "level": level, "coverage": "conus"},
        )
    ]


def parse_metar(payload: Any, flight: Flight) -> list[Observation]:
    rows = payload if isinstance(payload, list) else (payload.get("data") if isinstance(payload, dict) else [])
    out: list[Observation] = []
    for row in rows or []:
        icao = str(row.get("icaoId") or row.get("icao") or "").upper()
        wp = _station_waypoint(flight, icao)
        if wp is None:
            continue
        issued = _obs_time(row, wp.eta_utc)
        meta = {"provider": "awc", "product": "metar", "station": icao, "fl": 0.0}
        out.extend(
            _obs(
                wp.seq,
                Source.METAR,
                issued,
                False,
                meta,
                _num(row.get("temp")),
                _num(row.get("wspd")),
                _num(row.get("wdir")),
            )
        )
    return out


def parse_pirep(payload: Any, flight: Flight) -> list[Observation]:
    rows = payload if isinstance(payload, list) else (payload.get("data") if isinstance(payload, dict) else [])
    out: list[Observation] = []
    for row in rows or []:
        lat = _num(row.get("lat"))
        lon = _num(row.get("lon"))
        if lat is None or lon is None:
            continue
        pos = LatLon(lat, lon)
        wp = min(flight.waypoints, key=lambda w: haversine_nm(w.position, pos))
        if haversine_nm(wp.position, pos) > PIREP_MAX_NM:
            continue
        fl = _flt_lvl(row.get("fltLvl"))
        if fl is not None and abs(fl - wp.fl) > PIREP_MAX_FL:
            continue
        issued = _obs_time(row, wp.eta_utc)
        meta = {
            "provider": "awc",
            "product": "pirep",
            "fl": fl if fl is not None else wp.fl,
            "raw": row.get("rawOb"),
        }
        out.extend(
            _obs(
                wp.seq,
                Source.PIREP,
                issued,
                False,
                meta,
                _num(row.get("temp")),
                _num(row.get("wspd")),
                _num(row.get("wdir")),
            )
        )
    return out


def parse_windtemp(payload: Any, flight: Flight) -> list[Observation]:
    """FD winds are station/level tables; attach nearest station to each waypoint."""
    rows = payload if isinstance(payload, list) else (payload.get("data") if isinstance(payload, dict) else [])
    if not rows:
        return []
    out: list[Observation] = []
    for wp in flight.waypoints:
        row = _nearest_windtemp_row(rows, wp)
        if row is None:
            continue
        issued = _obs_time(row, wp.eta_utc)
        meta = {
            "provider": "awc",
            "product": "windtemp",
            "station": row.get("icaoId") or row.get("station"),
            "fl": wp.fl,
        }
        out.extend(
            _obs(
                wp.seq,
                Source.AWC_WINDS,
                issued,
                True,
                meta,
                _num(row.get("temp") or row.get("temp_c")),
                _num(row.get("wspd") or row.get("speed")),
                _num(row.get("wdir") or row.get("dir")),
            )
        )
    return out


def _nearest_windtemp_row(rows: list[dict], wp: Waypoint) -> dict | None:
    scored = []
    for row in rows:
        lat = _num(row.get("lat"))
        lon = _num(row.get("lon"))
        if lat is None or lon is None:
            continue
        scored.append((haversine_nm(wp.position, LatLon(lat, lon)), row))
    if not scored:
        return None
    dist, row = min(scored, key=lambda item: item[0])
    return row if dist <= 250.0 else None


def _station_waypoint(flight: Flight, icao: str) -> Waypoint | None:
    if icao == flight.origin_icao.upper():
        return flight.waypoints[0]
    if icao == flight.dest_icao.upper():
        return flight.waypoints[-1]
    return None


def _flt_lvl(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).upper().replace("FL", "").strip()
    try:
        val = float(text)
    except ValueError:
        return None
    return val / 100.0 if val > 1000 else val


def _obs_time(row: dict, fallback: str) -> str:
    if row.get("obsTime") is not None:
        try:
            ts = float(row["obsTime"])
            if ts > 1e12:
                ts /= 1000.0
            return iso_z(datetime.fromtimestamp(ts, tz=timezone.utc))
        except (TypeError, ValueError, OSError):
            pass
    for key in ("receiptTime", "valid", "issueTime"):
        if row.get(key):
            try:
                return iso_z(str(row[key]))
            except ValueError:
                continue
    return fallback


def _num(value: Any) -> float | None:
    if value is None or value == "" or value == "M":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _obs(seq, source, issued, is_forecast, meta, temp, wind, wdir) -> list[Observation]:
    out = []
    for variable, value in (
        (Variable.TEMP_C, temp),
        (Variable.WIND_KT, wind),
        (Variable.WIND_FROM_DEG, wdir),
    ):
        if value is None:
            continue
        out.append(Observation(seq, source, variable, float(value), issued, is_forecast, dict(meta)))
    return out
