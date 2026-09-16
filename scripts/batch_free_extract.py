#!/usr/bin/env python3
"""Run a substantial free-provider live extract batch.

Usage (from repo root):
  PYTHONPATH=. python3 scripts/batch_free_extract.py
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from airpath.automation import LIVE_FREE_PROVIDERS, run_live_once  # noqa: E402
from airpath.providers.tracks import AIRPORT_LL  # noqa: E402

# Refresh + new OMDB city-pairs whose dest coords exist in AIRPORT_LL and
# were not covered by the previous free-extract wave.
FLIGHTS: list[tuple[str, str, str]] = [
    ("EK001", "OMDB", "EGLL"),  # refresh
    ("EK041", "OMDB", "CYYZ"),
    ("EK151", "OMDB", "EKCH"),
    ("EK157", "OMDB", "ESSA"),
    ("EK927", "OMDB", "HECA"),
    ("EK719", "OMDB", "HKJK"),
    ("EK231", "OMDB", "KIAD"),
    ("EK235", "OMDB", "KORD"),
    ("EK225", "OMDB", "KSFO"),
    ("EK091", "OMDB", "LIMC"),
    ("EK837", "OMDB", "OBBI"),
    ("EK811", "OMDB", "OERK"),
    ("EK332", "OMDB", "RPLL"),
    ("EK261", "OMDB", "SBGR"),
    ("EK512", "OMDB", "VIDP"),
    ("EK306", "OMDB", "ZBAA"),
    ("EK302", "OMDB", "ZSPD"),
    # Extra volume / other hubs with coords (still free providers only)
    ("EK002", "EGLL", "OMDB"),
    ("EK206", "OMDB", "KJFK"),  # refresh-ish long-haul already had once; still useful
    ("EK414", "OMDB", "WSSS"),
]


def _providers_count(match) -> dict[str, int]:
    c: Counter[str] = Counter()
    for req in match.requests:
        c[req.provider] += 1
    return dict(c)


def main() -> int:
    out_dir = ROOT / "data" / "live"
    out_dir.mkdir(parents=True, exist_ok=True)
    providers = list(LIVE_FREE_PROVIDERS)
    results = []
    t0 = time.time()
    for ident, origin, dest in FLIGHTS:
        if origin not in AIRPORT_LL or dest not in AIRPORT_LL:
            print(f"SKIP {ident} {origin}-{dest}: missing AIRPORT_LL coords", flush=True)
            continue
        started = time.time()
        print(f"=== {ident} {origin}-{dest} providers={','.join(providers)} ===", flush=True)
        try:
            run = run_live_once(
                ident=ident,
                origin=origin,
                dest=dest,
                providers=providers,
                out_dir=out_dir,
            )
            match = run.match
            flight = match.flight
            n_obs = len(match.observations) if match.observations else 0
            if flight is not None:
                n_obs = max(n_obs, len(flight.observations or []))
            row = {
                "ident": ident,
                "route": f"{origin}-{dest}",
                "stamp": run.stamp,
                "obs": n_obs,
                "flight": str(run.flight_path) if run.flight_path else None,
                "meta": str(run.out_path) if run.out_path else None,
                "errors": list(match.errors),
                "providers": _providers_count(match),
                "elapsed_s": round(time.time() - started, 1),
            }
            print(
                f"  ok stamp={run.stamp} obs={n_obs} errors={len(match.errors)} "
                f"elapsed={row['elapsed_s']}s",
                flush=True,
            )
            for err in match.errors[:8]:
                print(f"    error {err}", flush=True)
        except Exception as exc:  # noqa: BLE001 — keep batch going
            row = {
                "ident": ident,
                "route": f"{origin}-{dest}",
                "stamp": None,
                "obs": 0,
                "flight": None,
                "meta": None,
                "errors": [f"batch_exception: {exc}"],
                "providers": {},
                "elapsed_s": round(time.time() - started, 1),
            }
            print(f"  FAIL {exc}", flush=True)
        results.append(row)
        # Soft pause between flights to ease Iowa/OpenSky rate limits.
        time.sleep(2.0)
        if time.time() - t0 > 28 * 60:
            print("Stopping early: ~28 minutes elapsed", flush=True)
            break

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary_path = out_dir / f"_batch_summary_{stamp}.json"
    summary_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for r in results if r.get("obs", 0) > 0)
    print(
        f"DONE flights={len(results)} with_obs={ok} "
        f"total_obs={sum(r.get('obs', 0) for r in results)} "
        f"elapsed={time.time() - t0:.0f}s summary={summary_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
