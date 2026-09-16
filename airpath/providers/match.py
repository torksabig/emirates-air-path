"""Match a flown / planned track to archive + forecast products."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..models import Flight, Observation, Source, Waypoint
from . import awc, commercial, ecmwf, iowa, ncei, openmeteo, tracks
from .catalog import get_provider
from .http import AuthRequired, FetchFn, PlannedRequest, http_get
from .tracks import TRACK_PROVIDER_IDS, HTML_PRODUCTS, TrackPoint

DEFAULT_FREE = ("iowa", "awc", "ncei", "era5", "ecmwf", "ecmwf_ifs", "gfs")
DEFAULT_TRACK = ("opensky",)
_NO_AUTO_FETCH = frozenset({"ifs_open", "aifs_open", "era5_cds"})


@dataclass
class MatchResult:
    observations: list[Observation]
    requests: list[PlannedRequest]
    skipped: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    track_points: list[TrackPoint] = field(default_factory=list)
    schedules: list[dict[str, Any]] = field(default_factory=list)
    applied_to_flight: bool = False
    flight: Flight | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_observations": len(self.observations),
            "n_requests": len(self.requests),
            "n_track_points": len(self.track_points),
            "n_schedules": len(self.schedules),
            "applied_to_flight": self.applied_to_flight,
            "skipped": self.skipped,
            "errors": self.errors,
            "requests": [r.to_dict() for r in self.requests],
            "track_points": [p.to_dict() for p in self.track_points],
            "schedules": self.schedules,
        }


def match_flight(
    flight: Flight,
    providers: Iterable[str] | None = None,
    *,
    fetch: FetchFn | None = None,
    dry_run: bool = False,
    historical: bool = True,
    ident: str | None = None,
    icao24: str | None = None,
    apply_track: bool = True,
) -> MatchResult:
    """Pull (or plan) ADS-B track then weather along waypoints.

    Track providers run first. If a flown path is found, waypoints are
    replaced so weather is sampled on the realized route. `fetch` is
    injectable. dry_run records URLs and does not call the network.
    HTML pages (FlightsFrom, Flighty) are never fetched.
    """
    wanted = tuple(providers or DEFAULT_FREE)
    for pid in wanted:
        get_provider(pid)
    flight = tracks.with_ident(flight, ident)

    track_ids = [p for p in wanted if p in TRACK_PROVIDER_IDS]
    wx_ids = [p for p in wanted if p not in TRACK_PROVIDER_IDS]

    skipped: list[dict[str, str]] = []
    planned: list[PlannedRequest] = []
    errors: list[str] = []
    track_points: list[TrackPoint] = []
    schedules: list[dict[str, Any]] = []

    for pid in track_ids:
        try:
            planned.extend(_plan(pid, flight, historical=historical, icao24=icao24))
        except AuthRequired as exc:
            skipped.append({"provider": pid, "reason": str(exc)})

    if dry_run:
        for pid in wx_ids:
            try:
                planned.extend(_plan(pid, flight, historical=historical, icao24=icao24))
            except AuthRequired as exc:
                skipped.append({"provider": pid, "reason": str(exc)})
        return MatchResult([], planned, skipped, flight=flight)

    getter = fetch or http_get
    follow: list[PlannedRequest] = []
    for req in list(planned):
        if _skip_fetch(req, fetch):
            continue
        try:
            payload = getter(req)
        except Exception as exc:  # noqa: BLE001 — keep other providers going
            errors.append(f"{req.provider}/{req.product}: {exc}")
            continue
        pts, sched, extra = tracks.consume_payload(req, payload, flight)
        track_points.extend(pts)
        schedules.extend(sched)
        follow.extend(extra)

    for req in follow:
        planned.append(req)
        if _skip_fetch(req, fetch):
            continue
        try:
            payload = getter(req)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{req.provider}/{req.product}: {exc}")
            continue
        pts, sched, extra = tracks.consume_payload(req, payload, flight)
        track_points.extend(pts)
        schedules.extend(sched)

    applied = False
    working = flight
    if apply_track and len(track_points) >= 2:
        working = tracks.points_to_flight(flight, track_points, include_gs=False)
        applied = True

    wx_planned: list[PlannedRequest] = []
    for pid in wx_ids:
        try:
            wx_planned.extend(_plan(pid, working, historical=historical, icao24=icao24))
        except AuthRequired as exc:
            skipped.append({"provider": pid, "reason": str(exc)})
    planned.extend(wx_planned)

    observations: list[Observation] = []
    track_points = tracks.infer_ground_speed(tracks.downsample(track_points))
    if track_points:
        observations.extend(tracks.gs_observations(track_points))

    by_seq = {w.seq: w for w in working.waypoints}
    for req in wx_planned:
        if _skip_fetch(req, fetch):
            continue
        try:
            payload = getter(req)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{req.provider}/{req.product}: {exc}")
            continue
        observations.extend(_parse(req, payload, working, by_seq))

    return MatchResult(
        observations,
        planned,
        skipped,
        errors,
        track_points=tracks.downsample(track_points),
        schedules=schedules,
        applied_to_flight=applied,
        # Always return the flight used for weather sampling (planned or flown).
        flight=working,
    )


def _skip_fetch(req: PlannedRequest, fetch: FetchFn | None) -> bool:
    if req.meta.get("html") or req.product in HTML_PRODUCTS:
        return True
    if fetch is None and req.product in _NO_AUTO_FETCH:
        return True
    return False


def _plan(
    provider: str,
    flight: Flight,
    *,
    historical: bool,
    icao24: str | None = None,
) -> list[PlannedRequest]:
    wps = flight.waypoints
    if provider == "iowa":
        return iowa.plan_metar(flight) + iowa.plan_pireps(flight)
    if provider == "awc":
        return awc.plan_metar(flight) + awc.plan_pirep(flight) + awc.plan_windtemp()
    if provider == "ncei":
        return ncei.plan_global_hourly(flight)
    if provider == "ecmwf":
        return ecmwf.plan_open_data(flight, model="ifs") + ecmwf.plan_era5_cds(flight)
    if provider == "gfs":
        return openmeteo.plan_gfs(wps, historical=historical)
    if provider == "ecmwf_ifs":
        return openmeteo.plan_ecmwf_ifs(wps)
    if provider == "era5":
        ends = [flight.waypoints[0], flight.waypoints[-1]]
        return openmeteo.plan_era5(ends)
    if provider == "ibm":
        return commercial.plan_ibm(wps)
    if provider == "meteoblue":
        return commercial.plan_meteoblue(wps)
    if provider == "opensky":
        return tracks.plan_opensky(flight, icao24=icao24)
    if provider == "flightaware":
        return tracks.plan_flightaware(flight)
    if provider == "fr24":
        return tracks.plan_fr24(flight)
    if provider == "oag":
        return tracks.plan_oag(flight)
    if provider == "flightsfrom":
        return tracks.plan_flightsfrom(flight)
    if provider == "flighty":
        return tracks.plan_flighty(flight)
    raise KeyError(provider)


def _parse(
    req: PlannedRequest,
    payload: Any,
    flight: Flight,
    by_seq: dict[int, Waypoint],
) -> list[Observation]:
    wp = by_seq.get(req.waypoint_seq) if req.waypoint_seq is not None else None
    if req.provider == "iowa" and req.product == "metar" and wp is not None:
        return iowa.parse_metar_json(payload, wp, req.icao or "")
    if req.provider == "iowa" and req.product == "pirep":
        return iowa.parse_pirep_geojson(payload, flight)
    if req.provider == "awc" and req.product == "metar":
        return awc.parse_metar(payload, flight)
    if req.provider == "awc" and req.product == "pirep":
        return awc.parse_pirep(payload, flight)
    if req.provider == "awc" and req.product == "windtemp":
        return awc.parse_windtemp(payload, flight)
    if req.provider == "ncei" and wp is not None:
        return ncei.parse_global_hourly(payload, wp, req.icao or "")
    if req.provider == "gfs" and wp is not None:
        return openmeteo.parse_openmeteo_hourly(
            payload, wp, Source.GFS, is_forecast=True, provider="gfs"
        )
    if req.provider == "ecmwf_ifs" and wp is not None:
        return openmeteo.parse_openmeteo_hourly(
            payload, wp, Source.ECMWF_IFS, is_forecast=False, provider="ecmwf_ifs"
        )
    if req.provider == "era5" and wp is not None:
        return openmeteo.parse_openmeteo_hourly(
            payload, wp, Source.ERA5, is_forecast=False, provider="era5"
        )
    if req.provider == "ecmwf" and wp is not None:
        model = "aifs" if "aifs" in req.product else "ifs"
        if req.product == "era5_cds":
            model = "ifs"
            if isinstance(payload, dict):
                payload = {**payload, "product_type": payload.get("product_type", "reanalysis")}
        return ecmwf.parse_decoded_point(payload, wp, model=model)
    if req.provider == "ibm" and wp is not None:
        return commercial.parse_ibm(payload, wp)
    if req.provider == "meteoblue" and wp is not None:
        return commercial.parse_meteoblue(payload, wp)
    return []


def attach_observations(flight: Flight, extra: list[Observation]) -> Flight:
    flight.observations.extend(extra)
    return flight


__all__ = ["MatchResult", "match_flight", "attach_observations", "DEFAULT_TRACK"]
