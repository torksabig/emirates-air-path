# Emirates Air Path / Intensity

Route fuel optimization from realized flight data: ADS-B tracks, weather archives, ISA deviation, aircraft sensors, and forecast correction.

Standalone package (not part of the Nordic SDR outreach pipeline).

| | |
|---|---|
| **Local path** | `nordic-sdr/emirates-air-path/` |
| **Branch** | `emirates-air-path-publish` / `cursor/emirates-air-path-publish-0eaf` |
| **Parent repo** | [torksabig/nordic-sdr](https://github.com/torksabig/nordic-sdr) |
| **Share / PR** | [PR #4](https://github.com/torksabig/nordic-sdr/pull/4) |
| **Tree** | [emirates-air-path on publish branch](https://github.com/torksabig/nordic-sdr/tree/cursor/emirates-air-path-publish-0eaf/emirates-air-path) |
| **Dedicated repo** | `github.com/torksabig/emirates-air-path` — **not created yet** (403) |
| **Latest commit** | `0fca9db` — Expand Emirates free extracts: 15+ new OMDB city pairs + EK001 refresh |
| **Size** | ~167 files · 29 code · 121 data · 11 tests |

---

## Why two phases

You cannot rank routes from a raw forecast. First verify which measurements held true, how severe the error was, and which correction equation improves that source. Only then is the forecast safe for fuel cost.

| Phase | What | Output |
|-------|------|--------|
| **1 — Realized flight** | Forecast vs QAR / METAR / PIREP / ERA5 / ADS-B | Holds true? Severity? Suitability? Improvement equation |
| **2 — Route rank** | Corrected forecast → parallel tracks × flight levels | Min fuel ranking |

Every `(source, variable)` pair has:

```text
corrected = a + b * forecast
```

Too few samples → identity (`corrected = forecast`). MOS kept only if RMSE does not get worse.

---

## Requirements

- Python 3.12+
- Stdlib only (no pip for the core pipeline)
- Network optional (demo offline; live extract needs HTTP)

```bash
cd emirates-air-path
PYTHONPATH=. python3 -m unittest discover -s tests -v
PYTHONPATH=. python3 -m airpath demo
```

---

## Layout

```text
emirates-air-path/
├── README.md              Full operator guide
├── PUBLISH.txt            Coworker share note
├── PROJECT.md             This overview
├── LICENSE
├── airpath/               Core package
│   ├── cli.py             CLI entry
│   ├── demo.py            Offline demo
│   ├── forecast.py        Forecast correction
│   ├── fuel.py            Fuel / intensity
│   ├── verify.py          Phase 1 verification
│   ├── route.py           Phase 2 route ranking
│   ├── timeline.py        Along-track weather
│   ├── ingest.py          Flight ingest
│   ├── weather.py / isa.py / equations.py / …
│   └── providers/         Data sources
│       ├── opensky (via tracks) · iowa · awc · ncei
│       ├── ecmwf · openmeteo · commercial (FA/FR24/OAG)
│       └── match.py / catalog.py / http.py
├── data/
│   ├── ek001-omdb-egll.json
│   └── live/              Free-provider extracts (~46 flights, 5520 obs)
├── scripts/
│   ├── batch_free_extract.py
│   └── hermes_live.py
└── tests/                 Unit tests (equations, fuel, ISA, pipeline, …)
```

---

## Quick start

### 1. List providers

```bash
PYTHONPATH=. python3 -m airpath sources
```

### 2. Preview URLs (no HTTP)

```bash
PYTHONPATH=. python3 -m airpath track \
  --ident EK001 --origin OMDB --dest EGLL \
  --departure 2026-08-10T06:00:00Z --dry-run

PYTHONPATH=. python3 -m airpath match \
  --flight data/ek001-omdb-egll.json --dry-run
```

### 3. Pull flown track (ADS-B)

```bash
# Free (OpenSky)
PYTHONPATH=. python3 -m airpath track \
  --ident EK001 --origin OMDB --dest EGLL \
  --departure 2026-08-10T06:00:00Z \
  --providers opensky \
  --out /tmp/ek001-flown.json \
  --json /tmp/ek001-track-meta.json

# Paid (optional)
export FLIGHTAWARE_API_KEY=...
export FR24_API_TOKEN=...
export OAG_API_KEY=...

PYTHONPATH=. python3 -m airpath track \
  --flight data/ek001-omdb-egll.json \
  --providers opensky,flightaware,fr24,oag \
  --out /tmp/ek001-flown.json
```

### 4. Attach weather along the track

```bash
PYTHONPATH=. python3 -m airpath match \
  --flight /tmp/ek001-flown.json \
  --providers iowa,awc,ncei,era5,ecmwf_ifs,gfs \
  --out /tmp/ek001-wx.json \
  --json /tmp/ek001-match.json
```

### 5. Phase 1 verify + Phase 2 rank

```bash
PYTHONPATH=. python3 -m airpath phase1 \
  --flight /tmp/ek001-wx.json --pairing auto --json /tmp/p1.json

PYTHONPATH=. python3 -m airpath phase2 \
  --flight /tmp/ek001-wx.json --json /tmp/p2.json
```

### 6. Along-track timeline

```bash
PYTHONPATH=. python3 -m airpath along-track \
  --flight /tmp/ek001-wx.json \
  --json /tmp/ek001-along-track.json
```

---

## Free extract inventory (`data/live/`)

- **46** flight files · **5520** total observations
- Providers typically: `opensky`, `iowa`, `awc`, `ncei`, `era5`, `ecmwf_ifs`, `gfs`, `ecmwf`
- Flights include: EK001, EK002, EK003, EK005, EK007, EK009, EK011, EK031, EK041, EK091, EK097, EK123, EK145, EK151, EK157, EK201, EK206, EK215, EK225, EK231, EK235, EK241, EK261, EK302, EK306, EK311, EK332, EK384, EK404, EK413, EK414, EK503, EK512, EK716, EK719, EK811, EK837, EK927
- Index: `data/live/EXTRACT_INDEX.txt`
- Batch summaries: `_batch_summary_20260826T055334Z.json`, `_batch_summary_20260826T074155Z.json`

---

## Output file types

| Pattern | Meaning |
|---------|---------|
| `*-flown.json` | Flight + ADS-B waypoints / ground speed |
| `*-wx.json` / `*_flight.json` | Flight + weather observations |
| `*_along_track.json` | Where/when weather changes along route |
| `*_phase1.json` | Phase 1 verification results |
| `*_matched_*.json` | Matched provider sample outputs |

---

## Modules (`airpath/`)

| File | Role |
|------|------|
| `cli.py` / `__main__.py` | Commands: `demo`, `sources`, `track`, `match`, `phase1`, `phase2`, `along-track` |
| `demo.py` | Offline demo run |
| `ingest.py` | Flight JSON ingest |
| `providers/` | ADS-B + weather source adapters |
| `forecast.py` | MOS / correction equations |
| `verify.py` | Phase 1 gate |
| `route.py` | Phase 2 fuel ranking |
| `fuel.py` / `equations.py` / `isa.py` | Physics & intensity |
| `timeline.py` | Along-track change detection |
| `automation.py` | Batch / Hermes hooks |

---

## Publish note

Dedicated repo still missing. Coworkers should use this folder on **nordic-sdr** until `emirates-air-path` is created under the user account.

Synced from standalone `/home/ubuntu/emirates-air-path` (`cursor/free-extract-batch-9080` @ `455c256`). Refreshed UTC: **2026-08-26T07:43:10Z**.
