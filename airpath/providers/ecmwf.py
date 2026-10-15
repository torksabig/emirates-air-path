"""Official ECMWF stack: Open Data IFS/AIFS, MARS language, ERA5 via CDS.

Portal: https://www.ecmwf.int/
Open Data: https://www.ecmwf.int/en/forecasts/datasets/open-data  (CC-BY-4.0)
ERA5: Copernicus CDS reanalysis-era5-pressure-levels

GRIB2 on the Open Data portal is not decoded here (needs eccodes /
ecmwf-opendata). We build MARS requests + file URLs, parse the `.index`
manifest, and accept a decoded JSON point {t_k, u_ms, v_ms} for tests
and for operators who extract a grid point first.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from ..isa import isa_deviation_k, isa_pressure_hpa
from ..models import Flight, Observation, Source, Variable, Waypoint
from ..timeutil import iso_z, parse_utc
from .http import PlannedRequest

ECMWF_HOME = "https://www.ecmwf.int/"
OPEN_DATA_DOCS = "https://www.ecmwf.int/en/forecasts/datasets/open-data"
OPEN_DATA_ROOT = "https://data.ecmwf.int/forecasts"
CDS_DATASET = "reanalysis-era5-pressure-levels"
ATTRIBUTION = (
    "Contains modified Copernicus Climate Change Service information / "
    "ECMWF Open Data CC-BY-4.0 (https://www.ecmwf.int/)"
)

# Open Data pressure levels after IFS Cycle 50r1 (May 2026).
OPEN_DATA_LEVELS_HPA = (1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50, 10)
KT_PER_MS = 1.943844


def ecmwf_level_hpa(alt_ft: float) -> int:
    p = isa_pressure_hpa(alt_ft)
    return min(OPEN_DATA_LEVELS_HPA, key=lambda level: abs(level - p))


def uv_to_wind(u_ms: float, v_ms: float) -> tuple[float, float]:
    """ECMWF u/v (eastward/northward m/s) → meteorological wind FROM (kt, deg)."""
    speed_kt = math.hypot(u_ms, v_ms) * KT_PER_MS
    from_deg = (math.degrees(math.atan2(-u_ms, -v_ms)) + 360.0) % 360.0
    return speed_kt, from_deg


def latest_cycle(valid: datetime) -> datetime:
    """Most recent 00/06/12/18 UTC cycle at or before `valid`."""
    utc = valid.astimezone(timezone.utc)
    hour = (utc.hour // 6) * 6
    return utc.replace(hour=hour, minute=0, second=0, microsecond=0)


def forecast_step_hours(cycle: datetime, valid: datetime) -> int:
    raw = (valid - cycle).total_seconds() / 3600.0
    if raw < 0:
        raw = 0.0
    step = int(round(raw / 3.0) * 3)
    return max(0, min(144, step))


def open_data_grib_url(cycle: datetime, step: int, *, model: str = "ifs") -> str:
    """IFS Cycle 50r1 path: …/YYYYMMDD/HHz/{ifs|aifs-single}/0p25/oper/…-STEPh-oper-fc.grib2"""
    folder = "aifs-single" if model == "aifs" else "ifs"
    ymd = cycle.strftime("%Y%m%d")
    hh = cycle.strftime("%H")
    stamp = cycle.strftime("%Y%m%d%H0000")
    name = f"{stamp}-{step}h-oper-fc.grib2"
    return f"{OPEN_DATA_ROOT}/{ymd}/{hh}z/{folder}/0p25/oper/{name}"


def mars_request(
    waypoint: Waypoint,
    *,
    cycle: datetime,
    step: int,
    model: str = "ifs",
) -> dict[str, Any]:
    """MARS language — ECMWF's common request vocabulary (class/stream/type/param)."""
    level = ecmwf_level_hpa(waypoint.fl * 100.0)
    lat, lon = waypoint.position.lat, waypoint.position.lon
    return {
        "class": "od",
        "stream": "oper",
        "type": "fc",
        "expver": "1",
        "levtype": "pl",
        "levelist": str(level),
        "param": "t/u/v",
        "date": cycle.strftime("%Y%m%d"),
        "time": cycle.strftime("%H00"),
        "step": str(step),
        "grid": "0.25/0.25",
        "area": f"{lat+0.25:.2f}/{lon-0.25:.2f}/{lat-0.25:.2f}/{lon+0.25:.2f}",
        "model": "aifs-single" if model == "aifs" else "ifs",
    }


def era5_cds_request(waypoint: Waypoint) -> dict[str, Any]:
    """CDS API body for ERA5 pressure-level temperature and wind (Phase 1 truth)."""
    dt = parse_utc(waypoint.eta_utc)
    level = str(ecmwf_level_hpa(waypoint.fl * 100.0))
    return {
        "dataset": CDS_DATASET,
        "product_type": "reanalysis",
        "variable": ["temperature", "u_component_of_wind", "v_component_of_wind"],
        "pressure_level": [level],
        "year": dt.strftime("%Y"),
        "month": dt.strftime("%m"),
        "day": dt.strftime("%d"),
        "time": [dt.strftime("%H:00")],
        "area": [
            waypoint.position.lat + 0.25,
            waypoint.position.lon - 0.25,
            waypoint.position.lat - 0.25,
            waypoint.position.lon + 0.25,
        ],
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def plan_open_data(flight: Flight, *, model: str = "ifs") -> list[PlannedRequest]:
    dep = parse_utc(flight.departure_utc)
    # Open Data is a rolling ~12-run archive; pick the cycle at/before departure.
    cycle = latest_cycle(dep - timedelta(hours=1))
    source = "aifs" if model == "aifs" else "ifs"
    out: list[PlannedRequest] = []
    seen: set[tuple[int, int]] = set()
    for wp in flight.waypoints:
        step = forecast_step_hours(cycle, parse_utc(wp.eta_utc))
        level = ecmwf_level_hpa(wp.fl * 100.0)
        key = (step, level)
        url = open_data_grib_url(cycle, step, model=model)
        req = PlannedRequest(
            provider="ecmwf",
            product=f"{source}_open",
            url=url,
            waypoint_seq=wp.seq,
            meta={
                "model": source,
                "cycle": iso_z(cycle),
                "step": step,
                "level_hpa": level,
                "index_url": url.replace(".grib2", ".index"),
                "mars": mars_request(wp, cycle=cycle, step=step, model=model),
                "attribution": ATTRIBUTION,
                "docs": OPEN_DATA_DOCS,
            },
        )
        if key in seen:
            # Same GRIB file; still keep per-waypoint MARS area for point extract.
            req.meta["duplicate_grib"] = True
        seen.add(key)
        out.append(req)
    return out


def plan_era5_cds(flight: Flight) -> list[PlannedRequest]:
    out = []
    for wp in flight.waypoints:
        body = era5_cds_request(wp)
        out.append(
            PlannedRequest(
                provider="ecmwf",
                product="era5_cds",
                url=f"https://cds.climate.copernicus.eu/api/retrieve/v1/processes/{CDS_DATASET}",
                waypoint_seq=wp.seq,
                meta={
                    "cds_request": body,
                    "attribution": ATTRIBUTION,
                    "docs": "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels",
                },
            )
        )
    return out


def parse_decoded_point(
    payload: Any,
    waypoint: Waypoint,
    *,
    model: str = "ifs",
) -> list[Observation]:
    """Accept operator-decoded Open Data / ERA5 point JSON."""
    if isinstance(payload, (bytes, bytearray)):
        return []
    if isinstance(payload, str):
        text = payload.strip()
        if text.startswith("GRIB") or not text:
            return []
        if text.startswith("{") or text.startswith("["):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return []
        else:
            return []
    if not isinstance(payload, dict):
        return []
    t_k = _num(payload.get("t_k") or payload.get("temperature_k") or payload.get("t"))
    # Temperature in C if clearly not Kelvin.
    t_c = _num(payload.get("t_c") or payload.get("temp_c"))
    if t_c is None and t_k is not None:
        t_c = t_k - 273.15 if t_k > 100 else t_k
    u = _num(payload.get("u_ms") or payload.get("u"))
    v = _num(payload.get("v_ms") or payload.get("v"))
    wind_kt = wdir = None
    if u is not None and v is not None:
        wind_kt, wdir = uv_to_wind(u, v)
    issued = iso_z(str(payload.get("valid_time") or waypoint.eta_utc))
    is_forecast = bool(payload.get("is_forecast", model in {"ifs", "aifs"}))
    if payload.get("product_type") == "reanalysis":
        is_forecast = False
        source = Source.ERA5
    elif model == "aifs":
        source = Source.ECMWF_AIFS
        is_forecast = True
    else:
        source = Source.ECMWF_IFS
    level = int(payload.get("level_hpa") or ecmwf_level_hpa(waypoint.fl * 100.0))
    meta = {
        "provider": "ecmwf",
        "model": model,
        "fl": waypoint.fl,
        "alt_ft": waypoint.fl * 100.0,
        "level_hpa": level,
        "attribution": ATTRIBUTION,
        "mars": payload.get("mars"),
    }
    if t_c is not None:
        meta["isa_dev_k"] = isa_deviation_k(t_c, waypoint.fl * 100.0)
    out: list[Observation] = []
    values = (
        (Variable.TEMP_C, t_c),
        (Variable.WIND_KT, wind_kt),
        (Variable.WIND_FROM_DEG, wdir),
    )
    if t_c is not None:
        values = values + ((Variable.ISA_DEV_K, meta["isa_dev_k"]),)
    for variable, value in values:
        if value is None:
            continue
        out.append(
            Observation(
                waypoint.seq,
                source,
                variable,
                float(value),
                issued,
                is_forecast,
                dict(meta),
            )
        )
    return out


def parse_index_fields(payload: Any) -> list[dict[str, Any]]:
    """Open Data `.index` is NDJSON of MARS keys + byte offsets."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        return [payload]
    if not isinstance(payload, str):
        return []
    rows = []
    for line in payload.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def index_has_pl_wind(payload: Any, level_hpa: int) -> bool:
    rows = parse_index_fields(payload)
    have = {(str(r.get("param")), str(r.get("levelist") or r.get("level"))) for r in rows}
    lvl = str(level_hpa)
    return ("t", lvl) in have and ("u", lvl) in have and ("v", lvl) in have


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
