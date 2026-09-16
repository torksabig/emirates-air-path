"""Great-circle geometry in nautical miles / degrees."""

from __future__ import annotations

import math
from dataclasses import dataclass

NM_PER_DEG_LAT = 60.0
EARTH_RADIUS_NM = 3440.065


@dataclass(frozen=True)
class LatLon:
    lat: float
    lon: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.lat, self.lon)


def _rad(deg: float) -> float:
    return math.radians(deg)


def _deg(rad: float) -> float:
    return math.degrees(rad)


def haversine_nm(a: LatLon, b: LatLon) -> float:
    dlat = _rad(b.lat - a.lat)
    dlon = _rad(b.lon - a.lon)
    s = (
        math.sin(dlat / 2) ** 2
        + math.cos(_rad(a.lat)) * math.cos(_rad(b.lat)) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_NM * math.asin(min(1.0, math.sqrt(s)))


def initial_bearing_deg(a: LatLon, b: LatLon) -> float:
    lat1, lat2 = _rad(a.lat), _rad(b.lat)
    dlon = _rad(b.lon - a.lon)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (_deg(math.atan2(x, y)) + 360.0) % 360.0


def destination_point(origin: LatLon, bearing_deg: float, distance_nm: float) -> LatLon:
    ang = distance_nm / EARTH_RADIUS_NM
    brng = _rad(bearing_deg)
    lat1 = _rad(origin.lat)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(ang) + math.cos(lat1) * math.sin(ang) * math.cos(brng)
    )
    lon2 = _rad(origin.lon) + math.atan2(
        math.sin(brng) * math.sin(ang) * math.cos(lat1),
        math.cos(ang) - math.sin(lat1) * math.sin(lat2),
    )
    lon = (_deg(lon2) + 540.0) % 360.0 - 180.0
    return LatLon(_deg(lat2), lon)


def great_circle_points(origin: LatLon, dest: LatLon, n: int) -> list[LatLon]:
    if n < 2:
        raise ValueError("need at least 2 points")
    total = haversine_nm(origin, dest)
    if total < 1e-6:
        return [origin for _ in range(n)]
    bearing = initial_bearing_deg(origin, dest)
    return [destination_point(origin, bearing, total * i / (n - 1)) for i in range(n)]


def parallel_track(origin: LatLon, dest: LatLon, offset_nm: float, n: int) -> list[LatLon]:
    """Shift a great-circle track left (+) / right (−) by offset_nm at mid-route.

    Endpoints stay fixed so the path remains a legal city-pair. Interior
    points are displaced perpendicular to the local track.
    """
    gc = great_circle_points(origin, dest, n)
    if abs(offset_nm) < 1e-9:
        return gc
    out = [gc[0]]
    for i in range(1, n - 1):
        brng = initial_bearing_deg(gc[i], gc[i + 1])
        perp = (brng + 90.0) % 360.0
        # Taper offset to 0 at the endpoints (sin envelope).
        taper = math.sin(math.pi * i / (n - 1))
        out.append(destination_point(gc[i], perp, offset_nm * taper))
    out.append(gc[-1])
    return out


def along_track_wind_kt(wind_speed_kt: float, wind_from_deg: float, track_deg: float) -> float:
    """Positive = tailwind (increases ground speed). Meteorological wind FROM."""
    return wind_speed_kt * math.cos(math.radians((wind_from_deg - track_deg + 180.0) % 360.0))
