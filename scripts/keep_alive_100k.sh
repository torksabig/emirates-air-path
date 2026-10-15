#!/usr/bin/env bash
# Keep the 100k free extract running until the queue drains.
# Auto-restarts on crash; resets stuck "running" jobs between attempts.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${AIRPATH_PYTHON:-/Users/teodor/.local/bin/python3.11}"
LOG_DIR="$ROOT/logs/ek100k"
mkdir -p "$LOG_DIR"
export PYTHONPATH="$ROOT"
unset FLIGHTAWARE_API_KEY FR24_API_TOKEN OAG_API_KEY IBM_WEATHER_API_KEY METEOBLUE_API_KEY CDSAPI_KEY

WORKERS="${WORKERS:-20}"
BATCH="${BATCH:-40}"
TARGET="${TARGET:-100000}"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] keep_alive start workers=$WORKERS target=$TARGET" | tee -a "$LOG_DIR/keep_alive.log"

while true; do
  # Reset orphaned running rows
  "$PY" - <<'PY' >>"$LOG_DIR/keep_alive.log" 2>&1
import sqlite3
from pathlib import Path
db = Path("data/bulk/ek100k/jobs.sqlite")
if not db.exists():
    raise SystemExit(0)
conn = sqlite3.connect(str(db))
n = conn.execute("UPDATE jobs SET status='pending' WHERE status='running'").rowcount
conn.commit()
c = dict(conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status"))
print(f"reset_running={n} counts={c}", flush=True)
pending = c.get("pending", 0)
ok = c.get("ok", 0) + c.get("empty", 0) + c.get("error", 0)
if pending == 0 and ok >= 100000:
    raise SystemExit(42)
PY
  rc=$?
  if [ "$rc" -eq 42 ]; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] queue complete — keep_alive exit" | tee -a "$LOG_DIR/keep_alive.log"
    # ntfy done
    curl -s -H "Title: Emirates extract - DONE" -H "Priority: high" -H "Tags: tada" \
      -d "100k queue drained via keep_alive." \
      "https://ntfy.sh/emirates-airpath-teodor-rate-drop" >/dev/null || true
    exit 0
  fi

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] launching extract_100k workers=$WORKERS" | tee -a "$LOG_DIR/keep_alive.log"
  "$PY" -u scripts/extract_100k.py \
    --target "$TARGET" \
    --workers "$WORKERS" \
    --batch "$BATCH" \
    --out-dir data/bulk/ek100k \
    --db data/bulk/ek100k/jobs.sqlite \
    >>"$LOG_DIR/supervisor.log" 2>&1
  code=$?
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] extract exited code=$code — restart in 5s" | tee -a "$LOG_DIR/keep_alive.log"
  curl -s -H "Title: Emirates extract - RESTART" -H "Priority: default" -H "Tags: arrows_counterclockwise" \
    -d "extract_100k exited ($code); keep_alive relaunching in 5s." \
    "https://ntfy.sh/emirates-airpath-teodor-rate-drop" >/dev/null || true
  sleep 5
done
