"""Live free-source extraction automation (track + weather).

Pulls OpenSky ADS-B and free weather archives/forecasts on a schedule.
Hermes Agent (Nous Research) is not required; the same CLI can be wrapped
by Hermes cron later if you deploy it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .ingest import dump_json, load_flight, save_flight
from .providers.match import MatchResult, attach_observations, match_flight
from .providers.tracks import skeleton_flight
from .timeutil import iso_z

# Free sources only. ECMWF Open Data GRIB URLs are planned; GRIB is not
# auto-downloaded (needs eccodes). Paid APIs are omitted unless the caller
# passes them explicitly and keys are present.
LIVE_FREE_PROVIDERS: tuple[str, ...] = (
    "opensky",
    "iowa",
    "awc",
    "ncei",
    "era5",
    "ecmwf_ifs",
    "gfs",
    "ecmwf",
)

SleepFn = Callable[[float], None]
ClockFn = Callable[[], datetime]


@dataclass
class LiveRunResult:
    """One extraction tick."""

    stamp: str
    out_path: Path | None
    flight_path: Path | None
    dry_run: bool
    match: MatchResult
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


def default_providers() -> list[str]:
    return list(LIVE_FREE_PROVIDERS)


def resolve_flight(
    *,
    flight_path: str | None = None,
    ident: str | None = None,
    origin: str | None = None,
    dest: str | None = None,
    departure: str | None = None,
    now: ClockFn | None = None,
):
    """Build a Flight from JSON or city-pair / ident args."""
    if flight_path:
        return load_flight(flight_path)
    if ident and origin and dest:
        clock = now or (lambda: datetime.now(timezone.utc))
        dep = departure or iso_z(clock())
        return skeleton_flight(ident, origin, dest, dep)
    raise ValueError("Need --flight JSON or --ident --origin --dest")


def snapshot_basename(flight_id: str, stamp: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in flight_id)
    return f"{safe}_{stamp}"


def write_live_outputs(
    out_dir: Path,
    flight_id: str,
    stamp: str,
    match: MatchResult,
    *,
    dry_run: bool,
) -> tuple[Path, Path | None]:
    """Write dated snapshot JSON (+ optional enriched flight) under out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    base = snapshot_basename(flight_id, stamp)
    out_path = out_dir / f"{base}.json"
    flight_path: Path | None = None
    flight = match.flight
    if flight is not None and not dry_run:
        # Copy observations onto a saved flight even when ADS-B did not replace
        # the path (planned/skeleton route still gets free weather).
        if match.observations:
            attach_observations(flight, match.observations)
        flight_path = out_dir / f"{base}_flight.json"
        save_flight(flight_path, flight)
    payload = {
        "kind": "airpath_live",
        "stamp_utc": stamp,
        "flight_id": flight_id,
        "dry_run": dry_run,
        "providers_default": list(LIVE_FREE_PROVIDERS),
        "out_flight": str(flight_path) if flight_path else None,
        "match": match.to_dict(),
    }
    dump_json(out_path, payload)
    return out_path, flight_path


def run_live_once(
    *,
    flight_path: str | None = None,
    ident: str | None = None,
    origin: str | None = None,
    dest: str | None = None,
    departure: str | None = None,
    providers: list[str] | None = None,
    out_dir: str | Path = "data/live",
    dry_run: bool = False,
    icao24: str | None = None,
    keep_plan: bool = False,
    fetch=None,
    now: ClockFn | None = None,
) -> LiveRunResult:
    """Extract live (or near-live) track + weather once; write dated JSON."""
    clock = now or (lambda: datetime.now(timezone.utc))
    stamp = iso_z(clock()).replace(":", "")
    flight = resolve_flight(
        flight_path=flight_path,
        ident=ident,
        origin=origin,
        dest=dest,
        departure=departure,
        now=now,
    )
    wanted = providers if providers is not None else default_providers()
    match = match_flight(
        flight,
        wanted,
        fetch=fetch,
        dry_run=dry_run,
        historical=False,
        ident=ident,
        icao24=icao24,
        apply_track=not keep_plan,
    )
    # Always write a snapshot (dry-run records planned URLs only).
    out_path, flight_out = write_live_outputs(
        Path(out_dir),
        flight.flight_id,
        stamp,
        match,
        dry_run=dry_run,
    )
    payload = {
        "kind": "airpath_live",
        "stamp_utc": stamp,
        "flight_id": flight.flight_id,
        "dry_run": dry_run,
        "out_path": str(out_path) if out_path else None,
        "out_flight": str(flight_out) if flight_out else None,
        "match": match.to_dict(),
    }
    return LiveRunResult(
        stamp=stamp,
        out_path=out_path,
        flight_path=flight_out,
        dry_run=dry_run,
        match=match,
        payload=payload,
    )


def run_live(
    *,
    flight_path: str | None = None,
    ident: str | None = None,
    origin: str | None = None,
    dest: str | None = None,
    departure: str | None = None,
    providers: list[str] | None = None,
    out_dir: str | Path = "data/live",
    dry_run: bool = False,
    loop: bool = False,
    every: float = 300.0,
    max_runs: int | None = None,
    icao24: str | None = None,
    keep_plan: bool = False,
    fetch=None,
    sleep: SleepFn | None = None,
    now: ClockFn | None = None,
) -> list[LiveRunResult]:
    """Run once, or loop every N seconds until max_runs (if set).

    dry_run always executes a single planning pass (no sleep / no loop).
    """
    sleeper = sleep or time.sleep
    if dry_run:
        loop = False
        max_runs = 1

    results: list[LiveRunResult] = []
    runs = 0
    while True:
        results.append(
            run_live_once(
                flight_path=flight_path,
                ident=ident,
                origin=origin,
                dest=dest,
                departure=departure,
                providers=providers,
                out_dir=out_dir,
                dry_run=dry_run,
                icao24=icao24,
                keep_plan=keep_plan,
                fetch=fetch,
                now=now,
            )
        )
        runs += 1
        if not loop:
            break
        if max_runs is not None and runs >= max_runs:
            break
        sleeper(max(0.0, float(every)))
    return results


__all__ = [
    "LIVE_FREE_PROVIDERS",
    "LiveRunResult",
    "default_providers",
    "resolve_flight",
    "run_live",
    "run_live_once",
    "snapshot_basename",
    "write_live_outputs",
]
