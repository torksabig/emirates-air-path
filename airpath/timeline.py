"""Along-track route + time-matched weather timeline.

Turns a flight JSON (waypoints with eta_utc + observations keyed by
waypoint_seq) into a plain per-point series and a change-point summary
so you can see where and when wind/temp (etc.) shift along the path.

Time matching is already done at ingest/match time: each Observation
is attached to a waypoint whose eta_utc was the ADS-B fix time (or
planned ETA). Archive/forecast series pick the nearest hour to that
ETA (see timeutil.nearest_index / openmeteo / ncei parsers). This
module only reorganizes and diffs those pairs — no network.
"""

from __future__ import annotations

from typing import Any, Iterable

from .models import THRESHOLDS, Flight, Observation, Variable
from .timeutil import parse_utc

# Default |delta| that marks a "weather is changing" event between
# consecutive waypoints. Uses Phase 1 "moderate" thresholds.
DEFAULT_CHANGE_THRESHOLDS: dict[str, float] = {
    v.value: float(THRESHOLDS[v]["moderate"]) for v in Variable
}


def circular_delta_deg(curr: float, prev: float) -> float:
    """Signed shortest-path difference on a 0–360 compass (deg)."""
    d = (float(curr) - float(prev) + 180.0) % 360.0 - 180.0
    return d


def delta_for(variable: str, curr: float, prev: float) -> float:
    if variable == Variable.WIND_FROM_DEG.value:
        return circular_delta_deg(curr, prev)
    return float(curr) - float(prev)


def _obs_row(obs: Observation) -> dict[str, Any]:
    meta = dict(obs.meta or {})
    valid = meta.get("valid_time") or meta.get("valid_at_utc") or obs.issued_at_utc
    return {
        "source": obs.source.value,
        "variable": obs.variable.value,
        "value": float(obs.value),
        "issued_at_utc": obs.issued_at_utc,
        "valid_time_utc": valid,
        "is_forecast": bool(obs.is_forecast),
        "meta": meta,
    }


def _index_observations(
    observations: Iterable[Observation],
    *,
    sources: set[str] | None,
    variables: set[str] | None,
) -> dict[int, list[Observation]]:
    by_seq: dict[int, list[Observation]] = {}
    for obs in observations:
        if sources is not None and obs.source.value not in sources:
            continue
        if variables is not None and obs.variable.value not in variables:
            continue
        by_seq.setdefault(obs.waypoint_seq, []).append(obs)
    for seq in by_seq:
        by_seq[seq].sort(key=lambda o: (o.source.value, o.variable.value, o.issued_at_utc))
    return by_seq


def build_timeline(
    flight: Flight,
    *,
    sources: Iterable[str] | None = None,
    variables: Iterable[str] | None = None,
    change_thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build plain along-track points + change summary from a Flight.

    Each point carries matched weather (issued / valid times) and
    deltas vs the previous waypoint for the same (source, variable).
    """
    source_filter = {s.strip() for s in sources} if sources is not None else None
    var_filter = {v.strip() for v in variables} if variables is not None else None
    if source_filter is not None:
        source_filter = {s for s in source_filter if s}
    if var_filter is not None:
        var_filter = {v for v in var_filter if v}

    thresholds = dict(DEFAULT_CHANGE_THRESHOLDS)
    if change_thresholds:
        thresholds.update({k: float(v) for k, v in change_thresholds.items()})

    by_seq = _index_observations(
        flight.observations, sources=source_filter, variables=var_filter
    )
    waypoints = sorted(flight.waypoints, key=lambda w: w.seq)

    # Last value per (source, variable) for delta computation.
    prev_vals: dict[tuple[str, str], float] = {}
    points: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []

    for wp in waypoints:
        weather = [_obs_row(o) for o in by_seq.get(wp.seq, [])]
        deltas: list[dict[str, Any]] = []
        for row in weather:
            key = (row["source"], row["variable"])
            if key in prev_vals:
                d = delta_for(row["variable"], row["value"], prev_vals[key])
                thresh = thresholds.get(row["variable"])
                significant = thresh is not None and abs(d) >= thresh
                delta_row = {
                    "source": row["source"],
                    "variable": row["variable"],
                    "from_value": prev_vals[key],
                    "to_value": row["value"],
                    "delta": d,
                    "threshold": thresh,
                    "significant": significant,
                }
                deltas.append(delta_row)
                if significant:
                    changes.append(
                        {
                            "seq": wp.seq,
                            "lat": wp.position.lat,
                            "lon": wp.position.lon,
                            "fl": wp.fl,
                            "time_utc": wp.eta_utc,
                            **delta_row,
                        }
                    )
            prev_vals[key] = float(row["value"])

        points.append(
            {
                "seq": wp.seq,
                "lat": wp.position.lat,
                "lon": wp.position.lon,
                "fl": wp.fl,
                "time_utc": wp.eta_utc,
                "weather": weather,
                "deltas": deltas,
            }
        )

    return {
        "kind": "airpath_along_track",
        "flight_id": flight.flight_id,
        "origin_icao": flight.origin_icao,
        "dest_icao": flight.dest_icao,
        "departure_utc": flight.departure_utc,
        "n_waypoints": len(points),
        "n_observations": sum(len(p["weather"]) for p in points),
        "n_changes": len(changes),
        "change_thresholds": thresholds,
        "points": points,
        "changes": changes,
    }


def time_lag_seconds(waypoint_eta_utc: str, weather_time_utc: str) -> float:
    """Seconds between waypoint ETA and matched weather valid/issued time."""
    return (
        parse_utc(weather_time_utc).timestamp()
        - parse_utc(waypoint_eta_utc).timestamp()
    )


__all__ = [
    "DEFAULT_CHANGE_THRESHOLDS",
    "build_timeline",
    "circular_delta_deg",
    "delta_for",
    "time_lag_seconds",
]
