"""CLI: python3 -m airpath demo | sources | match | track | live | along-track | phase1 | phase2 | stats."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .automation import LIVE_FREE_PROVIDERS, run_live
from .demo import format_report, run_demo
from .ingest import dump_json, load_flight, save_flight
from .providers import list_providers, match_flight
from .providers.match import attach_observations
from .providers.tracks import skeleton_flight
from .route import optimal_route, plan_routes
from .stats import phase1_ready, score_verifications, summarize
from .timeline import build_timeline
from .verify import equations_from_verifications, verify_flight

PHASE2_LOOKUP = [
    "ecmwf_ifs",
    "ecmwf_aifs",
    "gfs",
    "weather_model",
    "ibm_aviation",
    "meteoblue",
    "awc_winds",
]


def _print(text: str) -> None:
    sys.stdout.write(text if text.endswith("\n") else text + "\n")


def cmd_demo(args: argparse.Namespace) -> int:
    payload = run_demo()
    _print(format_report(payload))
    if args.json:
        dump_json(args.json, payload)
        _print(f"Wrote {args.json}")
    return 0


def cmd_phase1(args: argparse.Namespace) -> int:
    flight = load_flight(args.flight)
    points = verify_flight(flight, pairing=args.pairing)
    scores = score_verifications(points)
    payload = {
        "flight_id": flight.flight_id,
        "phase1": summarize(scores),
        "phase1_ready": phase1_ready(scores),
        "verifications": [p.to_dict() for p in points],
    }
    if args.json:
        dump_json(args.json, payload)
    for src in payload["phase1"]["sources"]:
        truth = src.get("truth_source", src["source"])
        tag = src["source"] if truth == src["source"] else f"{src['source']}→{truth}"
        _print(
            f"{tag} {src['variable']} n={src['n']} "
            f"RMSE {src['rmse']:.2f}→{src['rmse_corrected']:.2f} "
            f"suit={src['suitability']:.2f} eq={src['equation']['form']}"
        )
    _print(f"phase1_ready={payload['phase1_ready']}")
    return 0 if payload["phase1_ready"] or args.allow_partial else 2


def cmd_phase2(args: argparse.Namespace) -> int:
    flight = load_flight(args.flight)
    points = verify_flight(flight, pairing=args.pairing)
    scores = score_verifications(points)
    if not phase1_ready(scores) and not args.allow_partial:
        _print("Phase 1 not ready (need a suitable forecast-product wind or temp).")
        return 2
    equations = equations_from_verifications(points)
    gc = [wp.position for wp in flight.waypoints]
    winds_kt, winds_from, temps = [], [], []
    for wp in flight.waypoints:
        w = _lookup(points, wp.seq, "wind_kt")
        d = _lookup(points, wp.seq, "wind_from_deg")
        t = _lookup(points, wp.seq, "temp_c")
        if w is None or d is None or t is None:
            _print(f"Missing corrected weather at waypoint {wp.seq}")
            return 2
        winds_kt.append(w)
        winds_from.append(d)
        temps.append(t)
    candidates = plan_routes(
        flight.origin,
        flight.dest,
        gc_points=gc,
        winds_kt=winds_kt,
        winds_from=winds_from,
        temps_c=temps,
    )
    best = optimal_route(candidates)
    _print(
        f"optimal {best.name}  fuel={best.fuel_kg:.0f} kg  time={best.time_h:.2f} h  "
        f"TW={best.mean_tailwind_kt:+.1f} kt"
    )
    if args.json:
        dump_json(
            args.json,
            {
                "optimal": best.to_dict(),
                "candidates": [c.to_dict() for c in candidates],
                "equations": {
                    f"{s.value}:{v.value}": eq.to_dict() for (s, v), eq in equations.items()
                },
            },
        )
    return 0


def _value(points, seq, source, variable, prefer="corrected"):
    for p in points:
        if p.waypoint_seq == seq and p.source.value == source and p.variable.value == variable:
            return p.corrected if prefer == "corrected" else p.actual
    return None


def _lookup(points, seq, variable):
    for source in PHASE2_LOOKUP:
        value = _value(points, seq, source, variable, prefer="corrected")
        if value is not None:
            return value
    return None


def cmd_stats(args: argparse.Namespace) -> int:
    if args.json_in:
        payload = json.loads(Path(args.json_in).read_text(encoding="utf-8"))
        _print(
            format_report(payload)
            if "phase1" in payload and "flight_id" in payload
            else json.dumps(payload, indent=2)
        )
        return 0
    return cmd_demo(args)


def cmd_sources(_args: argparse.Namespace) -> int:
    for item in list_providers():
        phases = ",".join(item["phase"])
        _print(
            f"{item['id']:12}  {item['title']}\n"
            f"             phase={phases}  auth={item['auth']}\n"
            f"             {item['docs_url']}\n"
            f"             {item['notes']}"
        )
    return 0


def cmd_track(args: argparse.Namespace) -> int:
    if args.flight:
        flight = load_flight(args.flight)
    elif args.ident and args.origin and args.dest and args.departure:
        flight = skeleton_flight(args.ident, args.origin, args.dest, args.departure)
    else:
        _print("Need --flight JSON or --ident --origin --dest --departure")
        return 2
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    result = match_flight(
        flight,
        providers,
        dry_run=args.dry_run,
        ident=args.ident,
        icao24=args.icao24,
        apply_track=not args.keep_plan,
    )
    _print(
        f"planned={len(result.requests)} track_points={len(result.track_points)} "
        f"schedules={len(result.schedules)} skipped={len(result.skipped)} "
        f"errors={len(result.errors)} applied={result.applied_to_flight}"
    )
    for skip in result.skipped:
        _print(f"  skip {skip['provider']}: {skip['reason']}")
    for err in result.errors:
        _print(f"  error {err}")
    if args.dry_run:
        for req in result.requests:
            _print(f"  {req.provider}/{req.product}  {req.url}")
        if args.json:
            dump_json(args.json, result.to_dict())
        return 0
    out_flight = result.flight or flight
    attach_observations(out_flight, result.observations)
    if args.out:
        save_flight(args.out, out_flight)
        _print(f"Wrote flown-path flight {args.out}  n_wp={len(out_flight.waypoints)}")
    if args.json:
        dump_json(args.json, result.to_dict())
    return 0 if not result.errors else 1


def cmd_match(args: argparse.Namespace) -> int:
    flight = load_flight(args.flight)
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    result = match_flight(
        flight,
        providers,
        dry_run=args.dry_run,
        historical=not args.live_forecast,
        ident=args.ident,
        icao24=args.icao24,
        apply_track=not args.keep_plan,
    )
    _print(
        f"planned={len(result.requests)} observations={len(result.observations)} "
        f"track_points={len(result.track_points)} skipped={len(result.skipped)} "
        f"errors={len(result.errors)} applied={result.applied_to_flight}"
    )
    for skip in result.skipped:
        _print(f"  skip {skip['provider']}: {skip['reason']}")
    for err in result.errors:
        _print(f"  error {err}")
    if args.dry_run:
        for req in result.requests:
            _print(f"  {req.provider}/{req.product}  {req.url}")
        if args.json:
            dump_json(args.json, result.to_dict())
        return 0
    flight = result.flight or flight
    attach_observations(flight, result.observations)
    if args.out:
        save_flight(args.out, flight)
        _print(f"Wrote enriched flight {args.out}")
    points = verify_flight(flight, pairing="auto")
    scores = score_verifications(points)
    _print(f"phase1_ready={phase1_ready(scores)} pairs={len(points)}")
    if args.json:
        dump_json(
            args.json,
            {
                "match": result.to_dict(),
                "phase1": summarize(scores),
                "verifications": [p.to_dict() for p in points],
            },
        )
    return 0 if not result.errors else 1


def cmd_live(args: argparse.Namespace) -> int:
    """Continuous (or one-shot) free-source live extraction."""
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    try:
        results = run_live(
            flight_path=args.flight,
            ident=args.ident,
            origin=args.origin,
            dest=args.dest,
            departure=args.departure,
            providers=providers,
            out_dir=args.out_dir,
            dry_run=args.dry_run,
            loop=args.loop,
            every=args.every,
            max_runs=args.max_runs,
            icao24=args.icao24,
            keep_plan=args.keep_plan,
        )
    except ValueError as exc:
        _print(str(exc))
        return 2
    last_code = 0
    for i, run in enumerate(results, start=1):
        m = run.match
        _print(
            f"[{i}] stamp={run.stamp} planned={len(m.requests)} "
            f"obs={len(m.observations)} track={len(m.track_points)} "
            f"skipped={len(m.skipped)} errors={len(m.errors)} "
            f"applied={m.applied_to_flight}"
        )
        if run.out_path:
            _print(f"  wrote {run.out_path}")
        if run.flight_path:
            _print(f"  flight {run.flight_path}")
        for skip in m.skipped:
            _print(f"  skip {skip['provider']}: {skip['reason']}")
        for err in m.errors:
            _print(f"  error {err}")
            last_code = 1
        if args.dry_run:
            for req in m.requests:
                _print(f"  {req.provider}/{req.product}  {req.url}")
    return last_code


def cmd_along_track(args: argparse.Namespace) -> int:
    """Plain route + time-matched weather timeline with change points."""
    flight = load_flight(args.flight)
    sources = [s.strip() for s in (args.sources or "").split(",") if s.strip()] or None
    variables = [v.strip() for v in (args.variables or "").split(",") if v.strip()] or None
    thresholds: dict[str, float] | None = None
    if args.wind_kt_change is not None or args.temp_c_change is not None:
        thresholds = {}
        if args.wind_kt_change is not None:
            thresholds["wind_kt"] = float(args.wind_kt_change)
        if args.temp_c_change is not None:
            thresholds["temp_c"] = float(args.temp_c_change)
    payload = build_timeline(
        flight,
        sources=sources,
        variables=variables,
        change_thresholds=thresholds,
    )
    _print(
        f"flight={payload['flight_id']} waypoints={payload['n_waypoints']} "
        f"obs={payload['n_observations']} changes={payload['n_changes']}"
    )
    if args.changes_only:
        for ch in payload["changes"]:
            _print(
                f"  seq={ch['seq']} {ch['time_utc']} "
                f"lat={ch['lat']:.3f} lon={ch['lon']:.3f} "
                f"{ch['source']}/{ch['variable']} "
                f"{ch['from_value']:.1f}->{ch['to_value']:.1f} "
                f"d={ch['delta']:+.1f}"
            )
    else:
        for pt in payload["points"]:
            n_wx = len(pt["weather"])
            n_sig = sum(1 for d in pt["deltas"] if d.get("significant"))
            _print(
                f"  seq={pt['seq']} {pt['time_utc']} "
                f"FL{pt['fl']:.0f} lat={pt['lat']:.3f} lon={pt['lon']:.3f} "
                f"wx={n_wx} changes={n_sig}"
            )
    out_path = args.json or args.out
    if out_path:
        dump_json(out_path, payload)
        _print(f"Wrote {out_path}")
    return 0


def _add_pairing(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pairing",
        choices=("same", "crosswalk", "auto"),
        default="same",
        help="same=self-check; crosswalk=GFS vs ERA5/IFS/PIREP; auto=both",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="airpath", description="Emirates Air Path / Intensity")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="Run synthetic EK001 OMDB-EGLL Phase 1+2")
    d.add_argument("--json", help="Write full payload JSON")
    d.set_defaults(func=cmd_demo)

    src = sub.add_parser("sources", help="List weather archives, ADS-B, and schedule APIs")
    src.set_defaults(func=cmd_sources)

    mt = sub.add_parser("match", help="Attach archive/forecast weather to a flight track")
    mt.add_argument("--flight", required=True)
    mt.add_argument(
        "--providers",
        default=",".join(LIVE_FREE_PROVIDERS),
        help="Comma-separated provider ids (default: all free LIVE_FREE_PROVIDERS)",
    )
    mt.add_argument("--dry-run", action="store_true", help="Print URLs, no HTTP")
    mt.add_argument("--live-forecast", action="store_true", help="Use live GFS instead of historical")
    mt.add_argument("--ident", help="Override callsign / flight number for ADS-B lookup")
    mt.add_argument("--icao24", help="OpenSky ICAO24 hex for /tracks/all")
    mt.add_argument("--keep-plan", action="store_true", help="Do not replace waypoints with ADS-B path")
    mt.add_argument("--out", help="Write enriched flight JSON")
    mt.add_argument("--json", help="Write match + Phase 1 JSON")
    mt.set_defaults(func=cmd_match)

    tr = sub.add_parser("track", help="Pull ADS-B / schedule / FIDS and write a flown-path flight JSON")
    tr.add_argument("--flight", help="Existing flight JSON (waypoints used for bbox)")
    tr.add_argument("--ident", help="Callsign / flight number (e.g. EK001)")
    tr.add_argument("--origin", help="Origin ICAO or IATA")
    tr.add_argument("--dest", help="Destination ICAO or IATA")
    tr.add_argument("--departure", help="Departure UTC ISO-8601")
    tr.add_argument(
        "--providers",
        default="opensky",
        help="opensky,flightaware,fr24,oag,flightsfrom,flighty",
    )
    tr.add_argument("--icao24", help="OpenSky ICAO24 hex")
    tr.add_argument("--keep-plan", action="store_true", help="Keep planned waypoints")
    tr.add_argument("--dry-run", action="store_true", help="Print URLs, no HTTP")
    tr.add_argument("--out", help="Write flown-path flight JSON")
    tr.add_argument("--json", help="Write track match JSON")
    tr.set_defaults(func=cmd_track)

    live = sub.add_parser(
        "live",
        help="Extract live free-source track + weather (once or on an interval)",
    )
    live.add_argument("--flight", help="Existing flight JSON")
    live.add_argument("--ident", help="Callsign / flight number (e.g. EK001)")
    live.add_argument("--origin", help="Origin ICAO or IATA")
    live.add_argument("--dest", help="Destination ICAO or IATA")
    live.add_argument(
        "--departure",
        help="Departure UTC ISO-8601 (default: now when using --ident)",
    )
    live.add_argument(
        "--providers",
        default=",".join(LIVE_FREE_PROVIDERS),
        help="Comma-separated free provider ids (default: opensky + free weather)",
    )
    live.add_argument("--icao24", help="OpenSky ICAO24 hex")
    live.add_argument("--keep-plan", action="store_true", help="Keep planned waypoints")
    live.add_argument(
        "--out-dir",
        default="data/live",
        help="Directory for dated JSON snapshots (default: data/live)",
    )
    live.add_argument("--dry-run", action="store_true", help="Print URLs, no HTTP")
    live.add_argument(
        "--loop",
        action="store_true",
        help="Repeat extraction until interrupted (or --max-runs)",
    )
    live.add_argument(
        "--every",
        type=float,
        default=300.0,
        help="Seconds between loop ticks (default: 300)",
    )
    live.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Stop after N ticks when using --loop (useful for tests)",
    )
    live.set_defaults(func=cmd_live)

    at = sub.add_parser(
        "along-track",
        help="Plain route + time-matched weather timeline / change points",
    )
    at.add_argument("--flight", required=True, help="Enriched flight JSON (track + weather)")
    at.add_argument(
        "--sources",
        default="",
        help="Optional comma filter (e.g. gfs,era5,ecmwf_ifs)",
    )
    at.add_argument(
        "--variables",
        default="",
        help="Optional comma filter (e.g. wind_kt,temp_c)",
    )
    at.add_argument(
        "--wind-kt-change",
        type=float,
        default=None,
        help="Override |delta| kt that marks a wind change (default: Phase 1 moderate)",
    )
    at.add_argument(
        "--temp-c-change",
        type=float,
        default=None,
        help="Override |delta| C that marks a temp change (default: Phase 1 moderate)",
    )
    at.add_argument(
        "--changes-only",
        action="store_true",
        help="Print only significant change points to stdout",
    )
    at.add_argument("--json", help="Write along-track timeline JSON")
    at.add_argument("--out", help="Alias for --json")
    at.set_defaults(func=cmd_along_track)

    p1 = sub.add_parser("phase1", help="Verify forecasts on a realized flight JSON")
    p1.add_argument("--flight", required=True)
    p1.add_argument("--json", help="Write verification JSON")
    p1.add_argument("--allow-partial", action="store_true")
    _add_pairing(p1)
    p1.set_defaults(func=cmd_phase1)

    p2 = sub.add_parser("phase2", help="Correct forecasts and rank routes")
    p2.add_argument("--flight", required=True)
    p2.add_argument("--json", help="Write route JSON")
    p2.add_argument("--allow-partial", action="store_true")
    _add_pairing(p2)
    p2.set_defaults(func=cmd_phase2)

    st = sub.add_parser("stats", help="Print demo stats (or --json-in report)")
    st.add_argument("--json-in", help="Existing demo JSON")
    st.add_argument("--json", help="Write demo JSON")
    st.set_defaults(func=cmd_stats)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))
