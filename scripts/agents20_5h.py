#!/usr/bin/env python3
"""Run 20 free (€0) live-extract agents for ~5 hours.

Each agent loops one city-pair. Starts are staggered so OpenSky/Iowa
are not hit by all 20 at once.

Usage (repo root):
  PYTHONPATH=. python3 scripts/agents20_5h.py
  PYTHONPATH=. python3 scripts/agents20_5h.py --every 900 --hours 5
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = os.environ.get("AIRPATH_PYTHON", sys.executable)

FLIGHTS: list[tuple[str, str, str]] = [
    ("EK001", "OMDB", "EGLL"),
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
    ("EK002", "EGLL", "OMDB"),
    ("EK206", "OMDB", "KJFK"),
    ("EK414", "OMDB", "WSSS"),
]


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hours", type=float, default=5.0, help="Wall-clock duration (default 5)")
    ap.add_argument(
        "--every",
        type=float,
        default=900.0,
        help="Seconds between ticks per agent (default 900 = 15m)",
    )
    ap.add_argument(
        "--stagger",
        type=float,
        default=45.0,
        help="Seconds between agent process starts (default 45)",
    )
    ap.add_argument("--out-dir", default="data/live")
    ap.add_argument("--log-dir", default="logs/agents20_5h")
    args = ap.parse_args()

    assert len(FLIGHTS) == 20
    duration_s = int(args.hours * 3600)
    # Cap ticks so each agent stops near the 5h mark even without timeout.
    max_runs = max(1, int(duration_s // args.every) + 1)

    out_dir = ROOT / args.out_dir
    log_dir = ROOT / args.log_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Clear paid keys in child env — €0 free providers only.
    env = os.environ.copy()
    for key in (
        "FLIGHTAWARE_API_KEY",
        "FR24_API_TOKEN",
        "OAG_API_KEY",
        "IBM_WEATHER_API_KEY",
        "METEOBLUE_API_KEY",
        "CDSAPI_KEY",
    ):
        env.pop(key, None)
    env["PYTHONPATH"] = str(ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    status_path = log_dir / "status.json"
    procs: list[dict] = []

    print(
        f"[{_utc()}] START agents=20 hours={args.hours} every={args.every}s "
        f"max_runs={max_runs} stagger={args.stagger}s out={out_dir}",
        flush=True,
    )

    for i, (ident, origin, dest) in enumerate(FLIGHTS):
        if i:
            time.sleep(args.stagger)
        log_path = log_dir / f"agent_{i+1:02d}_{ident}.log"
        # max_runs alone caps the run (~5h); supervisor also SIGTERMs at deadline.
        cmd = [
            PY,
            "-m",
            "airpath",
            "live",
            "--ident",
            ident,
            "--origin",
            origin,
            "--dest",
            dest,
            "--out-dir",
            str(out_dir),
            "--loop",
            "--every",
            str(args.every),
            "--max-runs",
            str(max_runs),
        ]
        log_f = open(log_path, "w", encoding="utf-8")  # noqa: SIM115 — held for subprocess life
        log_f.write(f"# agent {i+1}/20 {ident} {origin}-{dest} started {_utc()}\n")
        log_f.write(f"# cmd: {' '.join(cmd)}\n")
        log_f.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        row = {
            "agent": i + 1,
            "ident": ident,
            "route": f"{origin}-{dest}",
            "pid": proc.pid,
            "log": str(log_path),
            "started": _utc(),
            "max_runs": max_runs,
            "every": args.every,
        }
        procs.append({"meta": row, "proc": proc, "log_f": log_f})
        print(
            f"[{_utc()}] agent {i+1:02d}/20 START {ident} {origin}-{dest} pid={proc.pid}",
            flush=True,
        )
        status_path.write_text(
            json.dumps(
                {
                    "started": procs[0]["meta"]["started"],
                    "hours": args.hours,
                    "every": args.every,
                    "agents": [p["meta"] for p in procs],
                    "updated": _utc(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    # Wall clock from first launch; allow stagger window so agent 20 still gets full hours.
    deadline = time.time() + duration_s + args.stagger * (len(FLIGHTS) - 1)
    print(f"[{_utc()}] all 20 launched; supervising until ~{_utc_plus(deadline)}", flush=True)

    def _stop_all(sig: int = signal.SIGTERM) -> None:
        for p in procs:
            if p["proc"].poll() is None:
                try:
                    os.killpg(p["proc"].pid, sig)
                except (ProcessLookupError, PermissionError):
                    try:
                        p["proc"].send_signal(sig)
                    except ProcessLookupError:
                        pass

    try:
        while time.time() < deadline:
            alive = sum(1 for p in procs if p["proc"].poll() is None)
            status_path.write_text(
                json.dumps(
                    {
                        "started": procs[0]["meta"]["started"],
                        "hours": args.hours,
                        "every": args.every,
                        "deadline": _utc_plus(deadline),
                        "alive": alive,
                        "agents": [
                            {
                                **p["meta"],
                                "exit": p["proc"].poll(),
                                "running": p["proc"].poll() is None,
                            }
                            for p in procs
                        ],
                        "updated": _utc(),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            if alive == 0:
                print(f"[{_utc()}] all agents exited early", flush=True)
                break
            time.sleep(30.0)
        else:
            print(f"[{_utc()}] deadline reached — stopping agents", flush=True)
            _stop_all(signal.SIGTERM)
    except KeyboardInterrupt:
        print(f"[{_utc()}] interrupt — stopping agents", flush=True)
        _stop_all(signal.SIGTERM)

    # Final reap
    for p in procs:
        try:
            p["proc"].wait(timeout=60)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p["proc"].pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                p["proc"].kill()
        p["log_f"].close()

    results = []
    for p in procs:
        meta = dict(p["meta"])
        meta["exit"] = p["proc"].returncode
        results.append(meta)
    done_path = log_dir / f"done_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    done_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"[{_utc()}] DONE summary={done_path}", flush=True)
    return 0


def _utc_plus(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
