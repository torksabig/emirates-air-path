#!/usr/bin/env python3
"""Resumable free (€0) extract of N flight snapshots (default 100_000).

Builds a queue of hub city-pairs × historical departure hours, then drains
it with a worker pool. Progress is checkpointed in SQLite so the run can
stop/restart safely.

Usage (repo root):
  PYTHONPATH=. python3 scripts/extract_100k.py
  PYTHONPATH=. python3 scripts/extract_100k.py --target 100000 --workers 6
  PYTHONPATH=. python3 scripts/extract_100k.py --status
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from airpath.automation import write_live_outputs  # noqa: E402
from airpath.providers.match import match_flight  # noqa: E402
from airpath.providers.tracks import AIRPORT_LL, skeleton_flight  # noqa: E402
from airpath.timeutil import iso_z  # noqa: E402

# Free providers that usually return data. Skip ncei (frequent 400) and
# ecmwf GRIB stubs for bulk throughput on a €0 budget.
BULK_PROVIDERS: tuple[str, ...] = (
    "opensky",
    "iowa",
    "awc",
    "era5",
    "ecmwf_ifs",
    "gfs",
)

# Seed idents reused across city-pairs (Emirates-style).
IDENT_POOL: tuple[str, ...] = (
    "EK001",
    "EK002",
    "EK003",
    "EK005",
    "EK007",
    "EK009",
    "EK011",
    "EK031",
    "EK041",
    "EK091",
    "EK097",
    "EK123",
    "EK145",
    "EK151",
    "EK157",
    "EK201",
    "EK206",
    "EK215",
    "EK225",
    "EK231",
    "EK235",
    "EK241",
    "EK261",
    "EK302",
    "EK306",
    "EK311",
    "EK332",
    "EK384",
    "EK404",
    "EK413",
    "EK414",
    "EK503",
    "EK512",
    "EK716",
    "EK719",
    "EK811",
    "EK837",
    "EK927",
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_routes() -> list[tuple[str, str, str]]:
    """OMDB hub ↔ every other airport in AIRPORT_LL (both directions)."""
    hubs = ("OMDB",)
    others = [icao for icao in sorted(AIRPORT_LL) if icao not in hubs]
    routes: list[tuple[str, str, str]] = []
    i = 0
    for hub in hubs:
        for dest in others:
            routes.append((IDENT_POOL[i % len(IDENT_POOL)], hub, dest))
            i += 1
            routes.append((IDENT_POOL[i % len(IDENT_POOL)], dest, hub))
            i += 1
    return routes


def ensure_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=60, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY,
            ident TEXT NOT NULL,
            origin TEXT NOT NULL,
            dest TEXT NOT NULL,
            departure_utc TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            obs INTEGER,
            stamp TEXT,
            flight_path TEXT,
            errors TEXT,
            elapsed_s REAL,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def seed_jobs(conn: sqlite3.Connection, target: int) -> int:
    existing = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    if existing >= target:
        return existing
    routes = build_routes()
    if not routes:
        raise SystemExit("no routes — AIRPORT_LL empty?")
    # Walk hours backward from "now" rounded down to the hour.
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    hour = 0
    batch: list[tuple[Any, ...]] = []
    next_id = existing + 1
    while next_id <= target:
        dep = now - timedelta(hours=hour)
        dep_s = iso_z(dep)
        for ident, origin, dest in routes:
            if next_id > target:
                break
            batch.append(
                (next_id, ident, origin, dest, dep_s, "pending", None, None, None, None, None, _utc())
            )
            next_id += 1
            if len(batch) >= 2000:
                conn.executemany(
                    "INSERT OR IGNORE INTO jobs "
                    "(id,ident,origin,dest,departure_utc,status,obs,stamp,flight_path,errors,elapsed_s,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    batch,
                )
                conn.commit()
                batch.clear()
        hour += 1
        if hour > 24 * 400:  # safety ~400 days
            break
    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO jobs "
            "(id,ident,origin,dest,departure_utc,status,obs,stamp,flight_path,errors,elapsed_s,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            batch,
        )
        conn.commit()
    conn.execute(
        "INSERT OR REPLACE INTO meta(key,value) VALUES('target',?)", (str(target),)
    )
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]


def claim_jobs(conn: sqlite3.Connection, n: int) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status='pending' ORDER BY id LIMIT ?",
        (n,),
    ).fetchall()
    ids = [r["id"] for r in rows]
    if not ids:
        return []
    conn.executemany(
        "UPDATE jobs SET status='running', updated_at=? WHERE id=?",
        [(_utc(), i) for i in ids],
    )
    conn.commit()
    return rows


def mark_done(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    status: str,
    obs: int,
    stamp: str | None,
    flight_path: str | None,
    errors: list[str],
    elapsed_s: float,
) -> None:
    conn.execute(
        "UPDATE jobs SET status=?, obs=?, stamp=?, flight_path=?, errors=?, "
        "elapsed_s=?, updated_at=? WHERE id=?",
        (
            status,
            obs,
            stamp,
            flight_path,
            json.dumps(errors[:20]),
            elapsed_s,
            _utc(),
            job_id,
        ),
    )
    conn.commit()


def extract_one(row: sqlite3.Row, out_dir: Path, providers: list[str]) -> dict[str, Any]:
    t0 = time.time()
    ident = row["ident"]
    origin = row["origin"]
    dest = row["dest"]
    departure = row["departure_utc"]
    try:
        flight = skeleton_flight(ident, origin, dest, departure)
        match = match_flight(
            flight,
            providers,
            dry_run=False,
            historical=True,
            ident=ident,
            apply_track=True,
        )
        stamp = iso_z(datetime.now(timezone.utc)).replace(":", "")
        # Disambiguate concurrent same-ident writes.
        stamp = f"{stamp}_j{row['id']}"
        out_path, flight_out = write_live_outputs(
            out_dir, flight.flight_id, stamp, match, dry_run=False
        )
        n_obs = 0
        if match.flight is not None:
            n_obs = len(match.flight.observations or [])
        elif match.observations:
            n_obs = len(match.observations)
        return {
            "id": row["id"],
            "status": "ok" if n_obs > 0 else "empty",
            "obs": n_obs,
            "stamp": stamp,
            "flight_path": str(flight_out) if flight_out else None,
            "errors": list(match.errors),
            "elapsed_s": round(time.time() - t0, 2),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "id": row["id"],
            "status": "error",
            "obs": 0,
            "stamp": None,
            "flight_path": None,
            "errors": [f"exception: {exc}"],
            "elapsed_s": round(time.time() - t0, 2),
        }


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    out = {"total": 0, "pending": 0, "running": 0, "ok": 0, "empty": 0, "error": 0}
    for status, n in conn.execute(
        "SELECT status, COUNT(*) FROM jobs GROUP BY status"
    ):
        out[status] = n
        out["total"] += n
    row = conn.execute("SELECT COALESCE(SUM(obs),0) FROM jobs WHERE status='ok'").fetchone()
    out["total_obs"] = int(row[0] if row else 0)
    return out


def write_progress(path: Path, conn: sqlite3.Connection, extra: dict[str, Any]) -> None:
    payload = {"updated": _utc(), "counts": counts(conn), **extra}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def cmd_status(db: Path) -> int:
    if not db.exists():
        print(f"no db at {db}")
        return 1
    conn = ensure_db(db)
    c = counts(conn)
    print(json.dumps({"db": str(db), "updated": _utc(), "counts": c}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", type=int, default=100_000)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--batch", type=int, default=24, help="Jobs claimed per refill")
    ap.add_argument(
        "--out-dir",
        default="data/bulk/ek100k",
        help="Output directory for flight JSON",
    )
    ap.add_argument(
        "--db",
        default="data/bulk/ek100k/jobs.sqlite",
        help="SQLite checkpoint path",
    )
    ap.add_argument("--status", action="store_true", help="Print progress and exit")
    ap.add_argument("--seed-only", action="store_true", help="Seed queue then exit")
    ap.add_argument(
        "--max-hours",
        type=float,
        default=0.0,
        help="Optional wall-clock stop (0 = run until target drained)",
    )
    args = ap.parse_args()

    db_path = ROOT / args.db
    out_dir = ROOT / args.out_dir
    progress_path = out_dir / "progress.json"
    out_dir.mkdir(parents=True, exist_ok=True)

    # €0 — never send paid keys.
    for key in (
        "FLIGHTAWARE_API_KEY",
        "FR24_API_TOKEN",
        "OAG_API_KEY",
        "IBM_WEATHER_API_KEY",
        "METEOBLUE_API_KEY",
        "CDSAPI_KEY",
    ):
        os.environ.pop(key, None)

    if args.status:
        return cmd_status(db_path)

    conn = ensure_db(db_path)
    n = seed_jobs(conn, args.target)
    print(f"[{_utc()}] seeded/have jobs={n} target={args.target} routes={len(build_routes())}", flush=True)
    write_progress(progress_path, conn, {"phase": "seeded", "workers": args.workers})
    if args.seed_only:
        return 0

    providers = list(BULK_PROVIDERS)
    t0 = time.time()
    deadline = t0 + args.max_hours * 3600 if args.max_hours > 0 else None
    done_since_start = 0

    print(
        f"[{_utc()}] START workers={args.workers} providers={providers} out={out_dir}",
        flush=True,
    )

    while True:
        c = counts(conn)
        if c.get("pending", 0) == 0 and c.get("running", 0) == 0:
            print(f"[{_utc()}] queue drained {c}", flush=True)
            break
        if c.get("ok", 0) + c.get("empty", 0) + c.get("error", 0) >= args.target:
            print(f"[{_utc()}] target reached {c}", flush=True)
            break
        if deadline is not None and time.time() >= deadline:
            print(f"[{_utc()}] max-hours reached {c}", flush=True)
            break

        batch = claim_jobs(conn, args.batch)
        if not batch:
            # Wait for any running leftovers
            time.sleep(2.0)
            # Reset stuck running > 30 min
            conn.execute(
                "UPDATE jobs SET status='pending' WHERE status='running' "
                "AND updated_at < ?",
                (
                    (datetime.now(timezone.utc) - timedelta(minutes=30)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                ),
            )
            conn.commit()
            continue

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {
                pool.submit(extract_one, row, out_dir, providers): row for row in batch
            }
            for fut in as_completed(futs):
                result = fut.result()
                mark_done(
                    conn,
                    result["id"],
                    status=result["status"],
                    obs=result["obs"],
                    stamp=result["stamp"],
                    flight_path=result["flight_path"],
                    errors=result["errors"],
                    elapsed_s=result["elapsed_s"],
                )
                done_since_start += 1
                if done_since_start % 10 == 0 or result["status"] == "error":
                    c = counts(conn)
                    rate = done_since_start / max(time.time() - t0, 1.0)
                    eta_h = (c.get("pending", 0) / rate / 3600.0) if rate > 0 else None
                    eta_s = f"{eta_h:.1f}" if eta_h is not None else "?"
                    print(
                        f"[{_utc()}] job={result['id']} {result['status']} "
                        f"obs={result['obs']} ok={c.get('ok', 0)} "
                        f"pending={c.get('pending', 0)} "
                        f"rate={rate * 3600:.0f}/h eta_h={eta_s}",
                        flush=True,
                    )
                    write_progress(
                        progress_path,
                        conn,
                        {
                            "phase": "running",
                            "workers": args.workers,
                            "rate_per_hour": round(rate * 3600, 1),
                            "eta_hours": round(eta_h, 2) if eta_h is not None else None,
                            "elapsed_s": round(time.time() - t0, 1),
                        },
                    )
        # Soft pause between batches to ease OpenSky/Iowa rate limits.
        time.sleep(1.5)

    c = counts(conn)
    write_progress(
        progress_path,
        conn,
        {"phase": "done", "workers": args.workers, "elapsed_s": round(time.time() - t0, 1)},
    )
    print(f"[{_utc()}] DONE {c} elapsed_s={time.time()-t0:.0f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
