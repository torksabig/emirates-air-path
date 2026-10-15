"""Load realized flight / forecast JSON (QAR-like, no CSV — repo gitignores CSV)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .geo import LatLon
from .models import Flight, Observation, Source, Variable, Waypoint


def _source(value: str) -> Source:
    return Source(value)


def _variable(value: str) -> Variable:
    return Variable(value)


def flight_from_dict(data: dict[str, Any]) -> Flight:
    origin = LatLon(data["origin"]["lat"], data["origin"]["lon"])
    dest = LatLon(data["dest"]["lat"], data["dest"]["lon"])
    waypoints = [
        Waypoint(
            seq=int(w["seq"]),
            position=LatLon(w["lat"], w["lon"]),
            fl=float(w["fl"]),
            eta_utc=str(w["eta_utc"]),
        )
        for w in data["waypoints"]
    ]
    observations = [
        Observation(
            waypoint_seq=int(o["waypoint_seq"]),
            source=_source(o["source"]),
            variable=_variable(o["variable"]),
            value=float(o["value"]),
            issued_at_utc=str(o["issued_at_utc"]),
            is_forecast=bool(o["is_forecast"]),
            meta=dict(o.get("meta") or {}),
        )
        for o in data.get("observations", [])
    ]
    return Flight(
        flight_id=str(data["flight_id"]),
        origin_icao=str(data["origin_icao"]),
        dest_icao=str(data["dest_icao"]),
        origin=origin,
        dest=dest,
        aircraft_type=str(data.get("aircraft_type", "A388")),
        departure_utc=str(data["departure_utc"]),
        waypoints=waypoints,
        observations=observations,
    )


def flight_to_dict(flight: Flight) -> dict[str, Any]:
    return {
        "flight_id": flight.flight_id,
        "origin_icao": flight.origin_icao,
        "dest_icao": flight.dest_icao,
        "origin": {"lat": flight.origin.lat, "lon": flight.origin.lon},
        "dest": {"lat": flight.dest.lat, "lon": flight.dest.lon},
        "aircraft_type": flight.aircraft_type,
        "departure_utc": flight.departure_utc,
        "waypoints": [
            {
                "seq": w.seq,
                "lat": w.position.lat,
                "lon": w.position.lon,
                "fl": w.fl,
                "eta_utc": w.eta_utc,
            }
            for w in flight.waypoints
        ],
        "observations": [
            {
                "waypoint_seq": o.waypoint_seq,
                "source": o.source.value,
                "variable": o.variable.value,
                "value": o.value,
                "issued_at_utc": o.issued_at_utc,
                "is_forecast": o.is_forecast,
                "meta": o.meta,
            }
            for o in flight.observations
        ],
    }


def load_flight(path: str | Path) -> Flight:
    with Path(path).open(encoding="utf-8") as fh:
        return flight_from_dict(json.load(fh))


def save_flight(path: str | Path, flight: Flight) -> None:
    dump_json(path, flight_to_dict(flight))


def dump_json(path: str | Path, payload: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
