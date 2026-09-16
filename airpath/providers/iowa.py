"""Iowa Environmental Mesonet — METAR/ASOS, PIREPs, RAOB."""

from __future__ import annotations

import math
import urllib.parse
from typing import Any

from ..geo import LatLon, haversine_nm
from ..models import Flight, Observation, Source, Variable, Waypoint
from ..timeutil import iso_z, parse_utc
from .http import PlannedRequest

ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
PIREP_GEOJSON = "https://mesonet.agron.iastate.edu/geojson/pireps.py"
PIREP_MAX_NM = 60.0
PIREP_MAX_FL = 40.0


def plan_metar(flight: Flight) -> list[PlannedRequest]:
    out: list[PlannedRequest] = []
    for icao, wp in (
        (flight.origin_icao, flight.waypoints[0]),
        (flight.dest_icao, flight.waypoints[-1]),
    ):
        dt = parse_utc(wp.eta_utc)
        qs = urllib.parse.urlencode(
            {
                "station": icao,
                "data": "tmpc,sknt,drct",
                "year1": dt.strftime("%Y"),
                "month1": str(dt.month),
                "day1": str(dt.day),
                "year2": dt.strftime("%Y"),
                "month2": str(dt.month),
                "day2": str(dt.day),
                "tz": "UTC",
                "format": "json",
                "latlon": "no",
            }
        )
        out.append(
            PlannedRequest(
                provider="iowa",
                product="metar",
                url=f"{ASOS}?{qs}",
                waypoint_seq=wp.seq,
                icao=icao,
            )
        )
    return out


def plan_pireps(flight: Flight) -> list[PlannedRequest]:
    lats = [w.position.lat for w in flight.waypoints]
    lons = [w.position.lon for w in flight.waypoints]
    # IEM bbox: west,south,east,north (same family as many GIS APIs).
    bbox = f"{min(lons)-2:.2f},{min(lats)-2:.2f},{max(lons)+2:.2f},{max(lats)+2:.2f}"
    qs = urllib.parse.urlencode({"hours": 24, "bbox": bbox})
    return [
        PlannedRequest(
            provider="iowa",
            product="pirep",
            url=f"{PIREP_GEOJSON}?{qs}",
            meta={"bbox": bbox},
        )
    ]


def parse_metar_json(payload: Any, waypoint: Waypoint, icao: str) -> list[Observation]:
    rows = _as_rows(payload)
    if not rows:
        return []
    target = parse_utc(waypoint.eta_utc).timestamp()
    row = min(rows, key=lambda r: abs(_row_ts(r) - target))
    temp = _num(row.get("tmpc") or row.get("temp") or row.get("tmpf"))
    if temp is not None and "tmpf" in row and "tmpc" not in row:
        temp = (float(row["tmpf"]) - 32.0) * 5.0 / 9.0
    wind = _num(row.get("sknt") or row.get("wspd") or row.get("wind_kt"))
    wdir = _num(row.get("drct") or row.get("wdir") or row.get("wind_dir"))
    issued = iso_z(str(row.get("valid") or row.get("utc_valid") or waypoint.eta_utc))
    meta = {"provider": "iowa", "product": "metar", "station": icao, "fl": 0.0}
    return _obs(waypoint.seq, Source.METAR, issued, False, meta, temp, wind, wdir)


def parse_pirep_geojson(payload: Any, flight: Flight) -> list[Observation]:
    features = []
    if isinstance(payload, dict):
        features = payload.get("features") or payload.get("data") or []
    elif isinstance(payload, list):
        features = payload
    out: list[Observation] = []
    for feat in features:
        props = feat.get("properties") if isinstance(feat, dict) and "properties" in feat else feat
        geom = feat.get("geometry") if isinstance(feat, dict) else {}
        coords = (geom or {}).get("coordinates") or []
        if len(coords) < 2:
            lon = _num(props.get("lon") or props.get("longitude"))
            lat = _num(props.get("lat") or props.get("latitude"))
        else:
            lon, lat = float(coords[0]), float(coords[1])
        if lat is None or lon is None:
            continue
        pos = LatLon(lat, lon)
        wp = min(flight.waypoints, key=lambda w: haversine_nm(w.position, pos))
        if haversine_nm(wp.position, pos) > PIREP_MAX_NM:
            continue
        fl = _pirep_fl(props)
        if fl is not None and abs(fl - wp.fl) > PIREP_MAX_FL:
            continue
        temp = _num(props.get("temp") or props.get("tmpc") or props.get("temperature"))
        wind = _num(props.get("sknt") or props.get("wspd") or props.get("wind"))
        wdir = _num(props.get("drct") or props.get("wdir"))
        issued = iso_z(str(props.get("valid") or props.get("utc_valid") or wp.eta_utc))
        meta = {
            "provider": "iowa",
            "product": "pirep",
            "fl": fl if fl is not None else wp.fl,
            "lat": lat,
            "lon": lon,
        }
        out.extend(_obs(wp.seq, Source.PIREP, issued, False, meta, temp, wind, wdir))
    return out


def _pirep_fl(props: dict) -> float | None:
    raw = props.get("flight_level") or props.get("fl") or props.get("altitude")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        val = float(raw)
        return val / 100.0 if val > 1000 else val
    text = str(raw).upper().replace("FL", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _as_rows(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("data", "values", "results"):
            if isinstance(payload.get(key), list):
                return [r for r in payload[key] if isinstance(r, dict)]
    return []


def _row_ts(row: dict) -> float:
    stamp = row.get("valid") or row.get("utc_valid") or row.get("valid_utc")
    if stamp is None:
        return math.inf
    try:
        return parse_utc(str(stamp)).timestamp()
    except ValueError:
        return math.inf


def _num(value: Any) -> float | None:
    if value is None or value == "" or value == "M":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _obs(
    seq: int,
    source: Source,
    issued: str,
    is_forecast: bool,
    meta: dict,
    temp: float | None,
    wind: float | None,
    wdir: float | None,
) -> list[Observation]:
    out = []
    for variable, value in (
        (Variable.TEMP_C, temp),
        (Variable.WIND_KT, wind),
        (Variable.WIND_FROM_DEG, wdir),
    ):
        if value is None:
            continue
        out.append(
            Observation(seq, source, variable, float(value), issued, is_forecast, dict(meta))
        )
    return out
