#!/usr/bin/env python3
"""Watch ek100k extract rate and push phone alerts via ntfy.sh when it drops.

Setup (once):
  1. Install the free ntfy app (iOS / Android): https://ntfy.sh
  2. Subscribe to the topic printed at startup (or --topic).

Usage (repo root):
  PYTHONPATH=. python3 scripts/watch_rate_ntfy.py
  PYTHONPATH=. python3 scripts/watch_rate_ntfy.py --topic your-secret-topic
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data/bulk/ek100k/jobs.sqlite"
DEFAULT_PROGRESS = ROOT / "data/bulk/ek100k/progress.json"
DEFAULT_TOPIC = "emirates-airpath-teodor-rate-drop"
NTFY_BASE = "https://ntfy.sh"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def push(topic: str, title: str, message: str, *, priority: str = "default", tags: str = "warning") -> None:
    url = f"{NTFY_BASE}/{topic}"
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        method="POST",
        headers={
            "Title": title,
            "Priority": priority,
            "Tags": tags,
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        resp.read()


def job_counts(db: Path) -> dict[str, int]:
    if not db.exists():
        return {}
    conn = sqlite3.connect(str(db), timeout=30)
    out: dict[str, int] = {"total": 0}
    for status, n in conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status"):
        out[str(status)] = int(n)
        out["total"] += int(n)
    row = conn.execute(
        "SELECT COALESCE(SUM(obs),0) FROM jobs WHERE status='ok'"
    ).fetchone()
    out["total_obs"] = int(row[0] if row else 0)
    conn.close()
    return out


def supervisor_alive(pid_path: Path) -> bool:
    """True if pidfile process is up, or any extract_100k.py is running."""
    try:
        import os
        import subprocess

        if pid_path.exists():
            try:
                pid = int(pid_path.read_text().strip())
                os.kill(pid, 0)
                return True
            except (ValueError, OSError):
                pass
        # Fallback: match running extractor by cmdline
        out = subprocess.check_output(["pgrep", "-f", "scripts/extract_100k.py"], text=True)
        return bool(out.strip())
    except (OSError, subprocess.CalledProcessError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--topic", default=DEFAULT_TOPIC)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--progress", type=Path, default=DEFAULT_PROGRESS)
    ap.add_argument("--pid-file", type=Path, default=ROOT / "logs/ek100k/supervisor.pid")
    ap.add_argument("--every", type=float, default=120.0, help="Seconds between checks")
    ap.add_argument(
        "--drop-ratio",
        type=float,
        default=0.45,
        help="Alert when rate < peak * this ratio (default 0.45)",
    )
    ap.add_argument(
        "--min-rate",
        type=float,
        default=800.0,
        help="Also alert when rate/h falls below this absolute floor after warm-up",
    )
    ap.add_argument("--warmup", type=int, default=3, help="Samples before drop alerts arm")
    ap.add_argument("--cooldown", type=float, default=900.0, help="Seconds between repeat drop alerts")
    ap.add_argument("--test", action="store_true", help="Send a test push and exit")
    args = ap.parse_args()

    topic_url = f"{NTFY_BASE}/{args.topic}"
    print(f"[{_utc()}] ntfy topic: {topic_url}", flush=True)
    print(f"[{_utc()}] Install ntfy app → Subscribe to topic → enable notifications", flush=True)

    if args.test:
        push(
            args.topic,
            "Emirates extract - test",
            "Phone alerts are wired. You'll get a push if extract rate drops.",
            priority="high",
            tags="white_check_mark",
        )
        print(f"[{_utc()}] test push sent to {topic_url}", flush=True)
        return 0

    # Announce watch start (quiet priority).
    try:
        push(
            args.topic,
            "Emirates extract - watching",
            "Rate-drop alerts armed for the 100k free extract run.",
            priority="low",
            tags="eyes",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[{_utc()}] warn: could not send start push: {exc}", flush=True)

    prev_ok = None
    prev_t = None
    peak_rate = 0.0
    samples = 0
    last_drop_alert = 0.0
    dead_alerted = False
    done_alerted = False

    while True:
        now = time.time()
        counts = job_counts(args.db)
        ok = int(counts.get("ok", 0) or 0)
        pending = int(counts.get("pending", 0) or 0)
        alive = supervisor_alive(args.pid_file)

        rate = None
        if prev_ok is not None and prev_t is not None:
            dt = max(now - prev_t, 1.0)
            rate = max(0.0, (ok - prev_ok) * 3600.0 / dt)
            samples += 1
            if rate > peak_rate:
                peak_rate = rate

        # Persist a small watch snapshot next to progress.json
        snap = {
            "updated": _utc(),
            "ok": ok,
            "pending": pending,
            "rate_per_hour": None if rate is None else round(rate, 1),
            "peak_rate_per_hour": round(peak_rate, 1),
            "supervisor_alive": alive,
            "topic": args.topic,
        }
        watch_path = args.progress.parent / "watch_rate.json"
        try:
            watch_path.parent.mkdir(parents=True, exist_ok=True)
            watch_path.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass

        if rate is not None:
            print(
                f"[{_utc()}] ok={ok} pending={pending} rate={rate:.0f}/h "
                f"peak={peak_rate:.0f}/h alive={alive}",
                flush=True,
            )

        # Supervisor died
        if not alive and ok < (counts.get("total") or 100000) and not dead_alerted:
            try:
                push(
                    args.topic,
                    "Emirates extract - STOPPED",
                    f"Supervisor not running. ok={ok} pending={pending}. Check logs/ek100k/.",
                    priority="urgent",
                    tags="rotating_light,x",
                )
                dead_alerted = True
                print(f"[{_utc()}] ALERT: supervisor dead", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[{_utc()}] push failed: {exc}", flush=True)

        if alive:
            dead_alerted = False

        # Queue drained / done
        if pending == 0 and ok > 0 and not done_alerted:
            try:
                push(
                    args.topic,
                    "Emirates extract - DONE",
                    f"Queue drained. ok={ok} total_obs={counts.get('total_obs', 0)}",
                    priority="high",
                    tags="tada,white_check_mark",
                )
                done_alerted = True
            except Exception as exc:  # noqa: BLE001
                print(f"[{_utc()}] push failed: {exc}", flush=True)

        # Rate drop
        if (
            rate is not None
            and samples >= args.warmup
            and peak_rate > 0
            and now - last_drop_alert >= args.cooldown
        ):
            ratio_hit = rate < peak_rate * args.drop_ratio
            floor_hit = rate < args.min_rate and peak_rate >= args.min_rate
            if ratio_hit or floor_hit:
                try:
                    push(
                        args.topic,
                        "Emirates extract - RATE DROP",
                        (
                            f"Rate {rate:.0f}/h (peak {peak_rate:.0f}/h). "
                            f"ok={ok} pending={pending} workers watch active."
                        ),
                        priority="high",
                        tags="chart_with_downwards_trend,warning",
                    )
                    last_drop_alert = now
                    print(f"[{_utc()}] ALERT: rate drop {rate:.0f}/h vs peak {peak_rate:.0f}/h", flush=True)
                except Exception as exc:  # noqa: BLE001
                    print(f"[{_utc()}] push failed: {exc}", flush=True)

        prev_ok = ok
        prev_t = now
        time.sleep(args.every)


if __name__ == "__main__":
    raise SystemExit(main())
