"""Synthetic EK001 OMDB–EGLL realized-data demo.

Truth weather is a westerly jet. The weather-model forecast is a known
affine bias (actual ≈ a + b·forecast) so Phase 1 must recover the
improvement equation. Sensors are noisy-truth; METAR only near airports;
simulation is ISA-nominal fuel flow.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from .forecast import correct_along_route
from .geo import LatLon, great_circle_points
from .isa import isa_deviation_k, isa_temperature_c
from .models import Flight, Observation, Source, Variable, Waypoint
from .route import optimal_route, plan_routes
from .stats import phase1_ready, score_verifications, summarize
from .verify import equations_from_verifications, verify_flight

OMDB = LatLon(25.2532, 55.3657)
EGLL = LatLon(51.4700, -0.4543)
N_POINTS = 16
CRUISE_FL = 350.0

# Known MOS: actual = A + B * forecast
WIND_A = -8.0
WIND_B = 1.12
TEMP_A = 1.4
TEMP_B = 0.94


def _truth_wind(frac: float) -> tuple[float, float]:
    speed = 55.0 + 35.0 * math.sin(math.pi * frac)
    direction = 265.0 + 12.0 * frac
    return speed, direction


def _truth_temp_c(frac: float, fl: float) -> float:
    isa = isa_temperature_c(fl * 100.0)
    return isa + 6.0 - 7.0 * frac


def build_demo_flight(departure: datetime | None = None) -> Flight:
    dep = departure or datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)
    points = great_circle_points(OMDB, EGLL, N_POINTS)
    waypoints: list[Waypoint] = []
    observations: list[Observation] = []
    issued = (dep - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    actual_at = dep.strftime("%Y-%m-%dT%H:%M:%SZ")

    for i, pos in enumerate(points):
        frac = i / (N_POINTS - 1)
        eta = dep + timedelta(hours=7.1 * frac)
        waypoints.append(
            Waypoint(
                seq=i,
                position=pos,
                fl=CRUISE_FL,
                eta_utc=eta.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        )
        wind_kt, wind_from = _truth_wind(frac)
        temp_c = _truth_temp_c(frac, CRUISE_FL)
        isa_dev = isa_deviation_k(temp_c, CRUISE_FL * 100.0)
        meta = {"fl": CRUISE_FL, "isa_dev_k": isa_dev, "alt_ft": CRUISE_FL * 100.0}

        model_wind = (wind_kt - WIND_A) / WIND_B
        model_temp = (temp_c - TEMP_A) / TEMP_B
        observations.extend(
            [
                Observation(i, Source.WEATHER_MODEL, Variable.WIND_KT, model_wind, issued, True, meta),
                Observation(i, Source.WEATHER_MODEL, Variable.WIND_KT, wind_kt, actual_at, False, meta),
                Observation(i, Source.WEATHER_MODEL, Variable.WIND_FROM_DEG, wind_from + 8.0, issued, True, meta),
                Observation(i, Source.WEATHER_MODEL, Variable.WIND_FROM_DEG, wind_from, actual_at, False, meta),
                Observation(i, Source.WEATHER_MODEL, Variable.TEMP_C, model_temp, issued, True, meta),
                Observation(i, Source.WEATHER_MODEL, Variable.TEMP_C, temp_c, actual_at, False, meta),
                Observation(i, Source.WEATHER_MODEL, Variable.ISA_DEV_K, isa_dev - 1.5, issued, True, meta),
                Observation(i, Source.WEATHER_MODEL, Variable.ISA_DEV_K, isa_dev, actual_at, False, meta),
            ]
        )

        sensor_wind = wind_kt + 1.2 * math.sin(i)
        sensor_temp = temp_c + 0.3 * math.cos(i)
        ff_truth = 6800.0 + 40.0 * isa_dev - 8.0 * (wind_kt - 70.0)
        observations.extend(
            [
                Observation(i, Source.AIRCRAFT_SENSOR, Variable.WIND_KT, sensor_wind + 4.0, issued, True, meta),
                Observation(i, Source.AIRCRAFT_SENSOR, Variable.WIND_KT, sensor_wind, actual_at, False, meta),
                Observation(i, Source.AIRCRAFT_SENSOR, Variable.TEMP_C, sensor_temp - 0.8, issued, True, meta),
                Observation(i, Source.AIRCRAFT_SENSOR, Variable.TEMP_C, sensor_temp, actual_at, False, meta),
                Observation(i, Source.AIRCRAFT_SENSOR, Variable.FUEL_FLOW_KG_H, ff_truth + 220.0, issued, True, meta),
                Observation(i, Source.AIRCRAFT_SENSOR, Variable.FUEL_FLOW_KG_H, ff_truth, actual_at, False, meta),
            ]
        )

        observations.extend(
            [
                Observation(i, Source.SIMULATION, Variable.FUEL_FLOW_KG_H, 6800.0, issued, True, meta),
                Observation(i, Source.SIMULATION, Variable.FUEL_FLOW_KG_H, ff_truth, actual_at, False, meta),
                Observation(i, Source.SIMULATION, Variable.ISA_DEV_K, 0.0, issued, True, meta),
                Observation(i, Source.SIMULATION, Variable.ISA_DEV_K, isa_dev, actual_at, False, meta),
            ]
        )

        if i in (0, 1, N_POINTS - 2, N_POINTS - 1):
            surface_t = 32.0 - 22.0 * frac
            observations.extend(
                [
                    Observation(i, Source.METAR, Variable.TEMP_C, surface_t + 2.5, issued, True, meta),
                    Observation(i, Source.METAR, Variable.TEMP_C, surface_t, actual_at, False, meta),
                    Observation(i, Source.METAR, Variable.WIND_KT, 12.0 + 3 * i, issued, True, meta),
                    Observation(i, Source.METAR, Variable.WIND_KT, 11.0 + 3 * i, actual_at, False, meta),
                ]
            )

    return Flight(
        flight_id="EK001",
        origin_icao="OMDB",
        dest_icao="EGLL",
        origin=OMDB,
        dest=EGLL,
        aircraft_type="A388",
        departure_utc=dep.strftime("%Y-%m-%dT%H:%M:%SZ"),
        waypoints=waypoints,
        observations=observations,
    )


def run_demo() -> dict:
    flight = build_demo_flight()
    points = verify_flight(flight)
    scores = score_verifications(points)
    equations = equations_from_verifications(points)
    ready = phase1_ready(scores)

    gc = [wp.position for wp in flight.waypoints]
    raw_wps = []
    for wp in flight.waypoints:
        frac = wp.seq / (N_POINTS - 1)
        wind_kt, wind_from = _truth_wind(frac)
        temp_c = _truth_temp_c(frac, CRUISE_FL)
        # Phase 2 starts from the *biased model forecast*, then corrects it.
        raw_wps.append(
            {
                "seq": wp.seq,
                "wind_kt": (wind_kt - WIND_A) / WIND_B,
                "wind_from_deg": wind_from + 8.0,
                "temp_c": (temp_c - TEMP_A) / TEMP_B,
                "fl": CRUISE_FL,
                "isa_dev_k": isa_deviation_k(temp_c, CRUISE_FL * 100.0),
            }
        )
    corrected_rows = correct_along_route(raw_wps, equations, Source.WEATHER_MODEL)

    by_seq: dict[int, dict[str, float]] = {}
    for row in corrected_rows:
        by_seq.setdefault(row.waypoint_seq, {})
        by_seq[row.waypoint_seq][row.variable.value] = row.corrected

    winds_kt = [by_seq[i]["wind_kt"] for i in range(N_POINTS)]
    winds_from = [by_seq[i]["wind_from_deg"] for i in range(N_POINTS)]
    temps_c = [by_seq[i]["temp_c"] for i in range(N_POINTS)]

    candidates = plan_routes(
        OMDB,
        EGLL,
        gc_points=gc,
        winds_kt=winds_kt,
        winds_from=winds_from,
        temps_c=temps_c,
    )
    best = optimal_route(candidates)
    baseline = next(c for c in candidates if c.offset_nm == 0.0 and c.fl == 350.0)
    fuel_delta_pct = 100.0 * (best.fuel_kg - baseline.fuel_kg) / baseline.fuel_kg

    return {
        "flight_id": flight.flight_id,
        "route": f"{flight.origin_icao}-{flight.dest_icao}",
        "aircraft": flight.aircraft_type,
        "departure_utc": flight.departure_utc,
        "n_waypoints": len(flight.waypoints),
        "n_verifications": len(points),
        "phase1": summarize(scores),
        "phase1_ready": ready,
        "phase2": {
            "optimal": best.to_dict(),
            "baseline_gc_fl350": baseline.to_dict(),
            "fuel_delta_pct_vs_gc_fl350": round(fuel_delta_pct, 3),
            "candidates": [c.to_dict() for c in candidates],
            "n_corrected_forecasts": len(corrected_rows),
        },
        "verifications": [p.to_dict() for p in points],
        "corrected_forecasts": [r.to_dict() for r in corrected_rows],
    }


def format_report(payload: dict) -> str:
    lines = [
        "Emirates Air Path / Intensity",
        f"Flight {payload['flight_id']}  {payload['route']}  {payload['aircraft']}",
        f"Departure {payload['departure_utc']}  waypoints={payload['n_waypoints']}  pairs={payload['n_verifications']}",
        "",
        "=== Phase 1 — realized vs forecast ===",
    ]
    for src in payload["phase1"]["sources"]:
        eq = src["equation"]["form"]
        lines.append(
            f"  {src['source']:16} {src['variable']:16}  "
            f"n={src['n']:2}  MAE={src['mae']:6.2f}  RMSE={src['rmse']:6.2f}→{src['rmse_corrected']:6.2f}  "
            f"hit={src['hit_rate']*100:5.1f}%  suit={src['suitability']:.2f}  "
            f"{'PHASE2' if src['suitable_for_phase2'] else 'hold':6}  "
            f"sev {src['mild']}/{src['moderate']}/{src['severe']}"
        )
        lines.append(f"                     eq: {eq}")
    lines.append(
        f"  Phase 1 gate: {'PASS' if payload['phase1_ready'] else 'FAIL'}  "
        f"suitable={payload['phase1']['suitable_count']}"
    )
    if payload["phase1_ready"]:
        p2 = payload["phase2"]
        best = p2["optimal"]
        base = p2["baseline_gc_fl350"]
        lines += [
            "",
            "=== Phase 2 — corrected forecast + route ===",
            f"  Baseline {base['name']}: {base['fuel_kg']:.0f} kg  {base['time_h']:.2f} h  "
            f"TW={base['mean_tailwind_kt']:+.1f} kt  ISA={base['mean_isa_dev_k']:+.1f} K",
            f"  Optimal  {best['name']}: {best['fuel_kg']:.0f} kg  {best['time_h']:.2f} h  "
            f"TW={best['mean_tailwind_kt']:+.1f} kt  ISA={best['mean_isa_dev_k']:+.1f} K  "
            f"Δfuel={p2['fuel_delta_pct_vs_gc_fl350']:+.2f}%",
            "  Ranked candidates:",
        ]
        for c in p2["candidates"][:8]:
            lines.append(
                f"    {c['name']:14}  {c['fuel_kg']:8.0f} kg  {c['time_h']:.2f} h  "
                f"intensity={c['intensity']:.1f}"
            )
    else:
        lines.append("  Phase 2 skipped — wait for suitable Phase 1 weather-model scores.")
    return "\n".join(lines) + "\n"
