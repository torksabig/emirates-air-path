"""Phase 2 route search: great-circle plus parallel tracks × flight levels.

Cost is block fuel from the cruise model using corrected wind + temperature
at each waypoint. Intensity is mean |along-track wind| + |ISA deviation|.
"""

from __future__ import annotations

from dataclasses import dataclass

from .fuel import cruise_fuel_flow_kg_h, ground_speed_kt, segment_fuel_kg, segment_time_h, tas_kt
from .geo import LatLon, along_track_wind_kt, great_circle_points, haversine_nm, initial_bearing_deg, parallel_track
from .isa import isa_deviation_k
from .models import Variable

DEFAULT_OFFSETS_NM = (0.0, 50.0, -50.0, 100.0, -100.0)
DEFAULT_FLS = (350.0, 370.0, 390.0)


@dataclass
class RouteCandidate:
    name: str
    offset_nm: float
    fl: float
    points: list[LatLon]
    fuel_kg: float
    time_h: float
    mean_tailwind_kt: float
    mean_isa_dev_k: float
    intensity: float
    segment_fuels: list[float]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "offset_nm": self.offset_nm,
            "fl": self.fl,
            "fuel_kg": round(self.fuel_kg, 1),
            "time_h": round(self.time_h, 3),
            "mean_tailwind_kt": round(self.mean_tailwind_kt, 2),
            "mean_isa_dev_k": round(self.mean_isa_dev_k, 2),
            "intensity": round(self.intensity, 2),
            "n_points": len(self.points),
        }


def _lookup_corrected(
    corrected: list[CorrectedForecast],
    seq: int,
    variable: Variable,
) -> float | None:
    for row in corrected:
        if row.waypoint_seq == seq and row.variable is variable:
            return row.corrected
    return None


def score_track(
    name: str,
    points: list[LatLon],
    fl: float,
    *,
    offset_nm: float,
    winds_kt: list[float],
    winds_from: list[float],
    temps_c: list[float],
) -> RouteCandidate:
    if not (len(points) == len(winds_kt) == len(winds_from) == len(temps_c)):
        raise ValueError("track weather series length mismatch")
    fuel = 0.0
    time = 0.0
    tw_sum = 0.0
    isa_sum = 0.0
    segs: list[float] = []
    nseg = 0
    for i in range(len(points) - 1):
        dist = haversine_nm(points[i], points[i + 1])
        track = initial_bearing_deg(points[i], points[i + 1])
        oat = temps_c[i]
        tas = tas_kt(0.84, oat)
        tw = along_track_wind_kt(winds_kt[i], winds_from[i], track)
        gs = ground_speed_kt(tas, tw)
        ff = cruise_fuel_flow_kg_h(fl, oat)
        seg = segment_fuel_kg(dist, gs, ff)
        fuel += seg
        time += segment_time_h(dist, gs)
        segs.append(seg)
        tw_sum += tw
        isa_sum += isa_deviation_k(oat, fl * 100.0)
        nseg += 1
    mean_tw = tw_sum / max(nseg, 1)
    mean_isa = isa_sum / max(nseg, 1)
    intensity = abs(mean_tw) + 8.0 * abs(mean_isa)
    return RouteCandidate(
        name=name,
        offset_nm=offset_nm,
        fl=fl,
        points=points,
        fuel_kg=fuel,
        time_h=time,
        mean_tailwind_kt=mean_tw,
        mean_isa_dev_k=mean_isa,
        intensity=intensity,
        segment_fuels=segs,
    )


def _weather_at_points(
    points: list[LatLon],
    sample_points: list[LatLon],
    winds_kt: list[float],
    winds_from: list[float],
    temps_c: list[float],
) -> tuple[list[float], list[float], list[float]]:
    """Nearest-neighbour sample of the GC weather field onto a parallel track."""
    out_w, out_d, out_t = [], [], []
    for p in points:
        j = min(range(len(sample_points)), key=lambda i: haversine_nm(p, sample_points[i]))
        out_w.append(winds_kt[j])
        out_d.append(winds_from[j])
        out_t.append(temps_c[j])
    return out_w, out_d, out_t


def plan_routes(
    origin: LatLon,
    dest: LatLon,
    *,
    gc_points: list[LatLon],
    winds_kt: list[float],
    winds_from: list[float],
    temps_c: list[float],
    offsets_nm: tuple[float, ...] = DEFAULT_OFFSETS_NM,
    flight_levels: tuple[float, ...] = DEFAULT_FLS,
    n: int | None = None,
) -> list[RouteCandidate]:
    n = n or len(gc_points)
    candidates: list[RouteCandidate] = []
    for offset in offsets_nm:
        pts = parallel_track(origin, dest, offset, n)
        w, d, t = _weather_at_points(pts, gc_points, winds_kt, winds_from, temps_c)
        side = "GC" if offset == 0 else ("N" if offset > 0 else "S")
        mag = "" if offset == 0 else str(int(abs(offset)))
        for fl in flight_levels:
            # Cooler ISA at higher FL is already in temps; if only one temp series
            # was provided, apply a standard lapse so FL options differ.
            lapse = (fl - 350.0) * 0.2  # °C per FL step vs the sampled 350-ish field
            temps_fl = [tv - lapse for tv in t]
            name = f"{side}{mag} FL{int(fl)}"
            candidates.append(
                score_track(name, pts, fl, offset_nm=offset, winds_kt=w, winds_from=d, temps_c=temps_fl)
            )
    candidates.sort(key=lambda c: (c.fuel_kg, c.time_h))
    return candidates


def optimal_route(candidates: list[RouteCandidate]) -> RouteCandidate:
    if not candidates:
        raise ValueError("no route candidates")
    return candidates[0]
