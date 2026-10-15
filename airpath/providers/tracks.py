"""International flight tracking, schedules, and airport status.

Live / historic paths come from ADS-B networks (OpenSky, Flightradar24,
FlightAware). Forward schedules from OAG. Route frequency pages from
FlightsFrom. Airport live boards are what Flighty shows consumers —
machine access is FlightAware FIDS.

Converted tracks replace great-circle waypoints so Phase 1 weather is
sampled on the flown path, not the planned one.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, asdict, replace
from datetime import datetime, timezone
from typing import Any

from ..geo import LatLon, great_circle_points, haversine_nm
from ..models import Flight, Observation, Source, Variable, Waypoint
from ..timeutil import iso_z, parse_utc
from .http import OPENSKY_TIMEOUT_S, PlannedRequest, require_env

OPENSKY = "https://opensky-network.org/api"
AEROAPI = "https://aeroapi.flightaware.com/aeroapi"
FR24 = "https://fr24api.flightradar24.com/api"
OAG = "https://api.oag.com"
FLIGHTSFROM = "https://www.flightsfrom.com"
FLIGHTY = "https://www.flightyapp.com"

MAX_TRACK_POINTS = 24

# Emirates-centric IATA ↔ ICAO; unknown 4-letter codes pass through as ICAO.
IATA_TO_ICAO = {
    "DXB": "OMDB",
    "AUH": "OMAA",
    "LHR": "EGLL",
    "JFK": "KJFK",
    "CDG": "LFPG",
    "FRA": "EDDF",
    "SIN": "WSSS",
    "SYD": "YSSY",
    "BKK": "VTBS",
    "DEL": "VIDP",
    "BOM": "VABB",
    "MXP": "LIMC",
    "MIA": "KMIA",
    "LAX": "KLAX",
    "SFO": "KSFO",
    "IAD": "KIAD",
    "ORD": "KORD",
    "HEL": "EFHK",
    "CPH": "EKCH",
    "ARN": "ESSA",
    "AMS": "EHAM",
    "MAD": "LEMD",
    "FCO": "LIRF",
    "IST": "LTFM",
    "DOH": "OTHH",
    "BAH": "OBBI",
    "RUH": "OERK",
    "CAI": "HECA",
    "NBO": "HKJK",
    "JNB": "FAOR",
    "MNL": "RPLL",
    "HKG": "VHHH",
    "NRT": "RJAA",
    "PEK": "ZBAA",
    "PVG": "ZSPD",
    "YYZ": "CYYZ",
    "GRU": "SBGR",
}
ICAO_TO_IATA = {icao: iata for iata, icao in IATA_TO_ICAO.items()}

# Approximate airport reference points for skeleton tracks (no --flight JSON).
AIRPORT_LL: dict[str, tuple[float, float]] = {
    "OMDB": (25.2532, 55.3657),
    "OMAA": (24.4330, 54.6511),
    "EGLL": (51.4700, -0.4543),
    "KJFK": (40.6413, -73.7781),
    "LFPG": (49.0097, 2.5479),
    "EDDF": (50.0379, 8.5622),
    "WSSS": (1.3644, 103.9915),
    "YSSY": (-33.9399, 151.1753),
    "VTBS": (13.6900, 100.7501),
    "VIDP": (28.5562, 77.1000),
    "VABB": (19.0896, 72.8656),
    "LIMC": (45.6306, 8.7281),
    "KMIA": (25.7959, -80.2870),
    "KLAX": (33.9425, -118.4081),
    "KSFO": (37.6213, -122.3790),
    "KIAD": (38.9531, -77.4565),
    "KORD": (41.9742, -87.9073),
    "EFHK": (60.3172, 24.9633),
    "EKCH": (55.6180, 12.6508),
    "ESSA": (59.6519, 17.9186),
    "EHAM": (52.3105, 4.7683),
    "LEMD": (40.4983, -3.5676),
    "LIRF": (41.8003, 12.2389),
    "LTFM": (41.2753, 28.7519),
    "OTHH": (25.2731, 51.6081),
    "OBBI": (26.2708, 50.6336),
    "OERK": (24.9578, 46.6989),
    "HECA": (30.1219, 31.4056),
    "HKJK": (-1.3192, 36.9278),
    "FAOR": (-26.1392, 28.2460),
    "RPLL": (14.5086, 121.0194),
    "VHHH": (22.3080, 113.9185),
    "RJAA": (35.7720, 140.3929),
    "ZBAA": (40.0799, 116.6031),
    "ZSPD": (31.1443, 121.8083),
    "CYYZ": (43.6777, -79.6248),
    "SBGR": (-23.4356, -46.4731),
}

TRACK_PROVIDER_IDS = frozenset(
    {"opensky", "flightaware", "fr24", "oag", "flightsfrom", "flighty"}
)
HTML_PRODUCTS = frozenset({"route_network", "consumer_status"})


@dataclass
class TrackPoint:
    time_utc: str
    position: LatLon
    fl: float
    gs_kt: float | None = None
    heading_deg: float | None = None
    ident: str | None = None
    icao24: str | None = None
    provider: str = "ads_b"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["position"] = {"lat": self.position.lat, "lon": self.position.lon}
        return payload


def to_icao(code: str) -> str:
    text = code.strip().upper()
    if len(text) == 3:
        return IATA_TO_ICAO.get(text, text)
    return text


def to_iata(code: str) -> str:
    text = code.strip().upper()
    if len(text) == 3:
        return text
    return ICAO_TO_IATA.get(text, text[:3] if len(text) == 4 else text)


def airport_ll(code: str) -> LatLon:
    icao = to_icao(code)
    if icao not in AIRPORT_LL:
        raise KeyError(
            f"no reference coordinates for {code!r}; pass --flight JSON with waypoints"
        )
    lat, lon = AIRPORT_LL[icao]
    return LatLon(lat, lon)


def skeleton_flight(
    ident: str,
    origin_icao: str,
    dest_icao: str,
    departure_utc: str,
    *,
    aircraft_type: str = "A388",
    n_points: int = 8,
) -> Flight:
    """Minimal city-pair track so ADS-B bbox / schedule queries have geometry."""
    origin_icao = to_icao(origin_icao)
    dest_icao = to_icao(dest_icao)
    origin = airport_ll(origin_icao)
    dest = airport_ll(dest_icao)
    dep = iso_z(parse_utc(departure_utc))
    points = great_circle_points(origin, dest, n_points)
    waypoints = [
        Waypoint(seq=i, position=p, fl=350.0, eta_utc=dep) for i, p in enumerate(points)
    ]
    return Flight(
        flight_id=ident.replace(" ", ""),
        origin_icao=origin_icao,
        dest_icao=dest_icao,
        origin=origin,
        dest=dest,
        aircraft_type=aircraft_type,
        departure_utc=dep,
        waypoints=waypoints,
        observations=[],
    )


def with_ident(flight: Flight, ident: str | None) -> Flight:
    if not ident:
        return flight
    cleaned = ident.replace(" ", "")
    if cleaned == flight.flight_id:
        return flight
    return replace(flight, flight_id=cleaned)


def downsample(points: list[TrackPoint], max_n: int = MAX_TRACK_POINTS) -> list[TrackPoint]:
    if len(points) <= max_n or max_n < 2:
        return points
    last = len(points) - 1
    idxs = sorted({round(i * last / (max_n - 1)) for i in range(max_n)})
    return [points[i] for i in idxs]


def alt_to_fl(alt: float | None) -> float:
    """AeroAPI/FR24 often send feet; OpenSky metres; values ≤ 600 treated as FL."""
    if alt is None:
        return 350.0
    val = float(alt)
    if val <= 0:
        return 0.0
    if val <= 600:
        return val
    if val > 20000:  # metres well above tropopause if mis-tagged as ft
        return val / 100.0
    # 3000–20000: feet
    if val > 600:
        return val / 100.0
    return val


def plan_opensky(flight: Flight, *, icao24: str | None = None) -> list[PlannedRequest]:
    dep = parse_utc(flight.departure_utc)
    begin = int(dep.timestamp()) - 3600
    end = begin + 12 * 3600
    out = [
        PlannedRequest(
            provider="opensky",
            product="departures",
            url=(
                f"{OPENSKY}/flights/departure?"
                + urllib.parse.urlencode(
                    {"airport": to_icao(flight.origin_icao), "begin": begin, "end": end}
                )
            ),
            icao=to_icao(flight.origin_icao),
            meta={"ident": flight.flight_id},
            timeout_s=OPENSKY_TIMEOUT_S,
        )
    ]
    lats = [w.position.lat for w in flight.waypoints] or [flight.origin.lat, flight.dest.lat]
    lons = [w.position.lon for w in flight.waypoints] or [flight.origin.lon, flight.dest.lon]
    qs = urllib.parse.urlencode(
        {
            "lamin": f"{min(lats)-2:.3f}",
            "lomin": f"{min(lons)-2:.3f}",
            "lamax": f"{max(lats)+2:.3f}",
            "lomax": f"{max(lons)+2:.3f}",
        }
    )
    out.append(
        PlannedRequest(
            provider="opensky",
            product="states",
            url=f"{OPENSKY}/states/all?{qs}",
            meta={"ident": flight.flight_id},
            timeout_s=OPENSKY_TIMEOUT_S,
        )
    )
    if icao24:
        hex_id = icao24.strip().lower()
        out.append(
            PlannedRequest(
                provider="opensky",
                product="track",
                url=f"{OPENSKY}/tracks/all?icao24={urllib.parse.quote(hex_id)}&time={begin}",
                meta={"icao24": hex_id, "ident": flight.flight_id},
                timeout_s=OPENSKY_TIMEOUT_S,
            )
        )
    return out


def plan_flightaware(flight: Flight, *, api_key: str | None = None) -> list[PlannedRequest]:
    key = api_key if api_key is not None else require_env("FLIGHTAWARE_API_KEY")
    ident = urllib.parse.quote(flight.flight_id.replace(" ", ""))
    headers = {"x-apikey": key, "Accept": "application/json; charset=UTF-8"}
    return [
        PlannedRequest(
            provider="flightaware",
            product="flights",
            url=f"{AEROAPI}/flights/{ident}",
            headers=headers,
            meta={"ident": flight.flight_id},
        ),
        PlannedRequest(
            provider="flightaware",
            product="track",
            url=f"{AEROAPI}/flights/{ident}/track",
            headers=headers,
            meta={"ident": flight.flight_id},
        ),
        PlannedRequest(
            provider="flightaware",
            product="airport_fids",
            url=f"{AEROAPI}/airports/{to_icao(flight.origin_icao)}/flights",
            headers=headers,
            icao=to_icao(flight.origin_icao),
            meta={"role": "departures", "flighty_equivalent": True},
        ),
    ]


def plan_fr24(flight: Flight, *, api_token: str | None = None) -> list[PlannedRequest]:
    token = api_token if api_token is not None else require_env("FR24_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    ident = flight.flight_id.replace(" ", "")
    bounds = _bounds(flight)
    return [
        PlannedRequest(
            provider="fr24",
            product="live_positions",
            url=(
                f"{FR24}/live/flight-positions/full?"
                + urllib.parse.urlencode({"flights": ident, "bounds": bounds})
            ),
            headers=headers,
            meta={"ident": ident},
        )
    ]


def plan_oag(flight: Flight, *, api_key: str | None = None) -> list[PlannedRequest]:
    key = api_key if api_key is not None else require_env("OAG_API_KEY")
    date = parse_utc(flight.departure_utc).strftime("%Y-%m-%d")
    qs = urllib.parse.urlencode(
        {
            "DepartureAirport": to_iata(flight.origin_icao),
            "ArrivalAirport": to_iata(flight.dest_icao),
            "DepartureDateTime": date,
            "CarrierCode": _carrier(flight.flight_id),
        }
    )
    return [
        PlannedRequest(
            provider="oag",
            product="schedules",
            url=f"{OAG}/flight-instances?{qs}",
            headers={"Subscription-Key": key, "Accept": "application/json"},
            meta={"date": date, "ident": flight.flight_id},
        )
    ]


def plan_flightsfrom(flight: Flight) -> list[PlannedRequest]:
    pair = f"{to_iata(flight.origin_icao)}-{to_iata(flight.dest_icao)}"
    return [
        PlannedRequest(
            provider="flightsfrom",
            product="route_network",
            url=f"{FLIGHTSFROM}/{pair}",
            meta={"pair": pair, "html": True},
        )
    ]


def plan_flighty(flight: Flight) -> list[PlannedRequest]:
    ident = flight.flight_id.replace(" ", "")
    return [
        PlannedRequest(
            provider="flighty",
            product="consumer_status",
            url=f"{FLIGHTY}/",
            meta={
                "ident": ident,
                "note": "No public API; airport live boards via FlightAware FIDS (airport_fids).",
            },
        )
    ]


def parse_opensky_track(payload: Any, ident: str | None = None) -> list[TrackPoint]:
    path = []
    if isinstance(payload, dict):
        path = payload.get("path") or payload.get("waypoints") or []
        icao24 = payload.get("icao24")
        callsign = (payload.get("callsign") or ident or "").strip()
    else:
        icao24 = None
        callsign = ident
    out: list[TrackPoint] = []
    for row in path:
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            continue
        lat, lon = row[1], row[2]
        if lat is None or lon is None:
            continue
        alt_m = row[3] if len(row) > 3 else None
        track = row[4] if len(row) > 4 else None
        t = row[0]
        out.append(
            TrackPoint(
                time_utc=_unix_or_iso(t),
                position=LatLon(float(lat), float(lon)),
                fl=alt_to_fl(float(alt_m) * 3.28084 if alt_m is not None else None),
                heading_deg=float(track) if track is not None else None,
                ident=callsign or ident,
                icao24=str(icao24) if icao24 else None,
                provider="opensky",
            )
        )
    return infer_ground_speed(downsample(out))


def infer_ground_speed(points: list[TrackPoint]) -> list[TrackPoint]:
    """Fill missing GS from consecutive ADS-B fixes (OpenSky path has no velocity)."""
    if len(points) < 2:
        return points
    for i in range(len(points) - 1):
        if points[i].gs_kt is not None:
            continue
        try:
            dt = (
                parse_utc(points[i + 1].time_utc).timestamp()
                - parse_utc(points[i].time_utc).timestamp()
            )
        except ValueError:
            continue
        if dt <= 1.0:
            continue
        dist_nm = haversine_nm(points[i].position, points[i + 1].position)
        points[i].gs_kt = dist_nm / dt * 3600.0
    if points[-1].gs_kt is None and points[-2].gs_kt is not None:
        points[-1].gs_kt = points[-2].gs_kt
    return points


def parse_opensky_states(payload: Any, ident: str | None = None) -> list[TrackPoint]:
    states = payload.get("states") if isinstance(payload, dict) else payload
    if not isinstance(states, list):
        return []
    want = (ident or "").replace(" ", "").upper()
    out: list[TrackPoint] = []
    now = iso_z(datetime.now(timezone.utc))
    for row in states:
        if not isinstance(row, (list, tuple)) or len(row) < 8:
            continue
        callsign = str(row[1] or "").strip().upper()
        if want and callsign.replace(" ", "") != want and want not in callsign.replace(" ", ""):
            continue
        lon, lat = row[5], row[6]
        if lat is None or lon is None:
            continue
        alt = row[7]
        gs = row[9] if len(row) > 9 else None  # m/s
        hdg = row[10] if len(row) > 10 else None
        out.append(
            TrackPoint(
                time_utc=_unix_or_iso(row[3] or now),
                position=LatLon(float(lat), float(lon)),
                fl=alt_to_fl(float(alt) * 3.28084 if alt is not None else None),
                gs_kt=float(gs) * 1.943844 if gs is not None else None,
                heading_deg=float(hdg) if hdg is not None else None,
                ident=callsign or ident,
                icao24=str(row[0] or ""),
                provider="opensky",
            )
        )
    return downsample(out)


def parse_aeroapi_track(payload: Any, ident: str | None = None) -> list[TrackPoint]:
    rows = []
    if isinstance(payload, dict):
        rows = payload.get("positions") or payload.get("track") or payload.get("flights") or []
        if rows and isinstance(rows[0], dict) and "positions" in rows[0]:
            ident = rows[0].get("ident") or ident
            rows = rows[0]["positions"]
    elif isinstance(payload, list):
        rows = payload
    out: list[TrackPoint] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        lat = row.get("latitude") or row.get("lat")
        lon = row.get("longitude") or row.get("lon")
        if lat is None or lon is None:
            continue
        alt = row.get("altitude") or row.get("alt")
        gs = row.get("groundspeed") or row.get("gs")
        out.append(
            TrackPoint(
                time_utc=_unix_or_iso(row.get("timestamp") or row.get("clock") or row.get("time")),
                position=LatLon(float(lat), float(lon)),
                fl=alt_to_fl(float(alt) if alt is not None else None),
                gs_kt=float(gs) if gs is not None else None,
                heading_deg=_num(row.get("heading") or row.get("track")),
                ident=ident,
                provider="flightaware",
            )
        )
    return downsample(out)


def parse_fr24_positions(payload: Any, ident: str | None = None) -> list[TrackPoint]:
    rows = []
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("flights") or payload.get("positions") or []
        if isinstance(rows, dict):
            rows = list(rows.values())
    elif isinstance(payload, list):
        rows = payload
    out: list[TrackPoint] = []
    want = (ident or "").replace(" ", "").upper()
    for row in rows:
        if isinstance(row, (list, tuple)) and len(row) >= 5:
            lat, lon = row[0], row[1]
            if lat is None or lon is None:
                continue
            out.append(
                TrackPoint(
                    time_utc=_unix_or_iso(row[9] if len(row) > 9 else None),
                    position=LatLon(float(lat), float(lon)),
                    fl=alt_to_fl(_num(row[3])),
                    gs_kt=_num(row[4]),
                    heading_deg=_num(row[2]),
                    ident=str(row[13] if len(row) > 13 else ident or ""),
                    provider="fr24",
                )
            )
            continue
        if not isinstance(row, dict):
            continue
        call = str(row.get("flight") or row.get("callsign") or row.get("ident") or "").upper()
        if want and call.replace(" ", "") and want not in call.replace(" ", ""):
            continue
        lat = row.get("lat") or row.get("latitude")
        lon = row.get("lon") or row.get("lng") or row.get("longitude")
        if lat is None or lon is None:
            continue
        alt = row.get("alt") or row.get("altitude")
        spd = row.get("spd") or row.get("gspeed") or row.get("speed")
        out.append(
            TrackPoint(
                time_utc=_unix_or_iso(row.get("timestamp") or row.get("pos_time")),
                position=LatLon(float(lat), float(lon)),
                fl=alt_to_fl(float(alt) if alt is not None else None),
                gs_kt=float(spd) if spd is not None else None,
                heading_deg=_num(row.get("track") or row.get("heading")),
                ident=call or ident,
                icao24=str(row.get("hex") or row.get("icao_24") or "") or None,
                provider="fr24",
            )
        )
    return downsample(out)


def parse_oag_instances(payload: Any, ident: str | None = None) -> list[dict[str, Any]]:
    """Forward schedules — not a flown track. Returns normalized instance dicts."""
    rows = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("flights") or payload.get("instances") or []
    out = []
    want = (ident or "").replace(" ", "").upper()
    for row in rows:
        if not isinstance(row, dict):
            continue
        fn = str(
            row.get("flightNumber")
            or row.get("FlightNumber")
            or row.get("marketingFlightNumber")
            or ""
        ).upper()
        if want and fn and want not in fn.replace(" ", "") and fn.replace(" ", "") not in want:
            continue
        out.append(
            {
                "ident": fn or ident,
                "origin": row.get("departureAirport") or row.get("DepartureAirport"),
                "dest": row.get("arrivalAirport") or row.get("ArrivalAirport"),
                "std": row.get("departureDateTime") or row.get("ScheduledDeparture"),
                "sta": row.get("arrivalDateTime") or row.get("ScheduledArrival"),
                "status": row.get("status") or row.get("FlightStatus"),
                "provider": "oag",
            }
        )
    return out


def points_to_flight(
    flight: Flight,
    points: list[TrackPoint],
    *,
    aircraft_type: str | None = None,
    include_gs: bool = True,
) -> Flight:
    if not points:
        return flight
    points = downsample(points)
    waypoints = [
        Waypoint(seq=i, position=p.position, fl=p.fl, eta_utc=p.time_utc)
        for i, p in enumerate(points)
    ]
    origin = points[0].position
    dest = points[-1].position
    extra = gs_observations(points) if include_gs else []
    return Flight(
        flight_id=flight.flight_id,
        origin_icao=flight.origin_icao,
        dest_icao=flight.dest_icao,
        origin=origin,
        dest=dest,
        aircraft_type=aircraft_type or flight.aircraft_type,
        departure_utc=points[0].time_utc,
        waypoints=waypoints,
        observations=list(flight.observations) + extra,
    )


def gs_observations(points: list[TrackPoint]) -> list[Observation]:
    out = []
    for i, p in enumerate(points):
        if p.gs_kt is None:
            continue
        out.append(
            Observation(
                i,
                Source.ADS_B,
                Variable.GROUND_SPEED_KT,
                float(p.gs_kt),
                p.time_utc,
                False,
                {"provider": p.provider, "fl": p.fl, "ident": p.ident, "icao24": p.icao24},
            )
        )
    return out


def parse_track(req: PlannedRequest, payload: Any) -> list[TrackPoint]:
    ident = (req.meta or {}).get("ident")
    if req.provider == "opensky" and req.product == "track":
        return parse_opensky_track(payload, ident)
    if req.provider == "opensky" and req.product == "states":
        return parse_opensky_states(payload, ident)
    if req.provider == "flightaware" and req.product in {"track", "flights"}:
        return parse_aeroapi_track(payload, ident)
    if req.provider == "fr24":
        return parse_fr24_positions(payload, ident)
    return []


def icao24_from_departures(payload: Any, ident: str | None = None) -> str | None:
    rows = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("flights") or []
    want = (ident or "").replace(" ", "").upper()
    for row in rows:
        if not isinstance(row, dict):
            continue
        cs = str(row.get("callsign") or "").replace(" ", "").upper()
        if want and cs and want not in cs and cs not in want:
            continue
        hex_id = row.get("icao24")
        if hex_id:
            return str(hex_id).lower()
    return None


def parse_opensky_departures(payload: Any, ident: str | None = None) -> list[dict[str, Any]]:
    rows = payload if isinstance(payload, list) else []
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("flights") or []
    want = (ident or "").replace(" ", "").upper()
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cs = str(row.get("callsign") or "").replace(" ", "").upper()
        if want and cs and want not in cs and cs not in want:
            continue
        out.append(
            {
                "ident": cs or ident,
                "icao24": row.get("icao24"),
                "origin": row.get("estDepartureAirport"),
                "dest": row.get("estArrivalAirport"),
                "first_seen": row.get("firstSeen"),
                "last_seen": row.get("lastSeen"),
                "provider": "opensky",
            }
        )
    return out


def fa_flight_id_from_flights(payload: Any, ident: str | None = None) -> str | None:
    rows: list[Any] = []
    if isinstance(payload, dict):
        rows = payload.get("flights") or payload.get("data") or []
    elif isinstance(payload, list):
        rows = payload
    want = (ident or "").replace(" ", "").upper()
    for row in rows:
        if not isinstance(row, dict):
            continue
        ident_row = str(row.get("ident") or row.get("ident_iata") or "").replace(" ", "").upper()
        if want and ident_row and want not in ident_row and ident_row not in want:
            continue
        fa_id = row.get("fa_flight_id") or row.get("id")
        if fa_id:
            return str(fa_id)
    return None


def parse_aeroapi_fids(payload: Any) -> list[dict[str, Any]]:
    rows: list[Any] = []
    if isinstance(payload, dict):
        for key in (
            "departures",
            "arrivals",
            "scheduled_departures",
            "scheduled_arrivals",
            "flights",
        ):
            chunk = payload.get(key) or []
            if isinstance(chunk, list):
                rows.extend(chunk)
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        origin = row.get("origin")
        dest = row.get("destination")
        out.append(
            {
                "ident": row.get("ident"),
                "origin": origin.get("code") if isinstance(origin, dict) else origin,
                "dest": dest.get("code") if isinstance(dest, dict) else dest,
                "status": row.get("status"),
                "off": row.get("actual_off") or row.get("estimated_off"),
                "provider": "flightaware",
                "flighty_equivalent": True,
            }
        )
    return out


def consume_payload(
    req: PlannedRequest,
    payload: Any,
    flight: Flight,
) -> tuple[list[TrackPoint], list[dict[str, Any]], list[PlannedRequest]]:
    """Parse one track/schedule response. May queue a follow-up track GET."""
    ident = (req.meta or {}).get("ident") or flight.flight_id
    follow: list[PlannedRequest] = []
    if req.product in HTML_PRODUCTS or req.meta.get("html"):
        return [], [], []
    if req.provider == "opensky" and req.product == "departures":
        hex_id = icao24_from_departures(payload, ident)
        if hex_id:
            follow.extend(
                r for r in plan_opensky(flight, icao24=hex_id) if r.product == "track"
            )
        return [], parse_opensky_departures(payload, ident), follow
    if req.provider == "oag" and req.product == "schedules":
        return [], parse_oag_instances(payload, ident), []
    if req.provider == "flightaware" and req.product == "airport_fids":
        return [], parse_aeroapi_fids(payload), []
    if req.provider == "flightaware" and req.product == "flights":
        points = parse_aeroapi_track(payload, ident)
        fa_id = fa_flight_id_from_flights(payload, ident)
        if fa_id and not points:
            follow.append(
                PlannedRequest(
                    provider="flightaware",
                    product="track",
                    url=f"{AEROAPI}/flights/{urllib.parse.quote(fa_id)}/track",
                    headers=req.headers,
                    meta={"ident": ident, "fa_flight_id": fa_id},
                )
            )
        return points, [], follow
    return parse_track(req, payload), [], []


def _bounds(flight: Flight) -> str:
    lats = [w.position.lat for w in flight.waypoints] or [flight.origin.lat, flight.dest.lat]
    lons = [w.position.lon for w in flight.waypoints] or [flight.origin.lon, flight.dest.lon]
    return f"{max(lats)+2:.2f},{min(lons)-2:.2f},{min(lats)-2:.2f},{max(lons)+2:.2f}"


def _carrier(ident: str) -> str:
    letters = "".join(ch for ch in ident.upper() if ch.isalpha())
    return letters[:2] if len(letters) >= 2 else letters


def _unix_or_iso(value: Any) -> str:
    if value is None or value == "":
        return iso_z(datetime.now(timezone.utc))
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return iso_z(datetime.fromtimestamp(ts, tz=timezone.utc))
    try:
        return iso_z(parse_utc(str(value)))
    except ValueError:
        return str(value)


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
