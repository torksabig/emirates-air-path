Emirates Air Path / Intensity
=============================

Route fuel optimization from realized flight data: ADS-B tracks, weather
archives, ISA deviation, aircraft sensors, and forecast correction.

Standalone project. Not part of the Nordic SDR outreach pipeline.


Why two phases
--------------

You cannot rank routes from a raw forecast. First you must know which
measurement points held true, how severe the error was, and which
improvement equation corrects that source. Only then is the forecast
safe for fuel cost.

  Phase 1  realized flight
     forecast  vs  QAR / METAR / PIREP / ERA5 / ADS-B
     -> holds true? severity? suitability? improvement equation

  Phase 2  only if Phase 1 gate passes
     corrected forecast -> parallel tracks x flight levels -> min fuel

Every (source, variable) pair always has an equation:

  corrected = a + b * forecast

With too few samples the equation is identity (corrected = forecast).
MOS is kept only if RMSE does not get worse.


Requirements
------------

- Python 3.12+
- Stdlib only -- no pip install for the core pipeline
- Network optional (demo runs offline; live extract needs HTTP)

  PYTHONPATH=. python3 -m unittest discover -s tests -v
  PYTHONPATH=. python3 -m airpath demo


Quick start -- extract data
---------------------------

1. List providers

  PYTHONPATH=. python3 -m airpath sources

2. Preview URLs (no HTTP)

  PYTHONPATH=. python3 -m airpath track \
    --ident EK001 --origin OMDB --dest EGLL \
    --departure 2026-08-10T06:00:00Z --dry-run

  PYTHONPATH=. python3 -m airpath match \
    --flight data/ek001-omdb-egll.json --dry-run

3. Pull the flown track (ADS-B)

  Free (OpenSky, no key):

  PYTHONPATH=. python3 -m airpath track \
    --ident EK001 --origin OMDB --dest EGLL \
    --departure 2026-08-10T06:00:00Z \
    --providers opensky \
    --out /tmp/ek001-flown.json \
    --json /tmp/ek001-track-meta.json

  Paid (set keys first):

  export FLIGHTAWARE_API_KEY=...
  export FR24_API_TOKEN=...
  export OAG_API_KEY=...

  PYTHONPATH=. python3 -m airpath track \
    --flight data/ek001-omdb-egll.json \
    --providers opensky,flightaware,fr24,oag \
    --out /tmp/ek001-flown.json

  ADS-B points replace great-circle waypoints so weather is sampled on
  the realized path.

4. Attach weather along the track

  PYTHONPATH=. python3 -m airpath match \
    --flight /tmp/ek001-flown.json \
    --providers iowa,awc,ncei,era5,ecmwf_ifs,gfs \
    --out /tmp/ek001-wx.json \
    --json /tmp/ek001-match.json

5. Verify (Phase 1) and rank routes (Phase 2)

  PYTHONPATH=. python3 -m airpath phase1 \
    --flight /tmp/ek001-wx.json --pairing auto --json /tmp/p1.json

  PYTHONPATH=. python3 -m airpath phase2 \
    --flight /tmp/ek001-wx.json --json /tmp/p2.json

6. Along-track timeline (where / when weather changes)

  PYTHONPATH=. python3 -m airpath along-track \
    --flight /tmp/ek001-wx.json \
    --json /tmp/ek001-along-track.json

  PYTHONPATH=. python3 -m airpath along-track \
    --flight /tmp/ek001-wx.json \
    --sources gfs,era5 --variables wind_kt,temp_c \
    --changes-only


Output files
------------

  *-flown.json
      Flight with flown waypoints + ADS-B ground speed

  *-wx.json
      Same flight + weather observations

  *-track-meta.json / *-match.json
      Request URLs, track points, schedules, errors

  *-along-track.json
      Plain per-waypoint route + matched weather + deltas / changes

  p1.json
      Holds-true, severity, suitability, MOS equations

  p2.json
      Fuel-ranked parallel tracks


CLI commands
------------

  demo         Synthetic EK001 OMDB-EGLL Phase 1+2 (offline)
  sources      List weather + flight-data providers
  track        Extract ADS-B / schedules / FIDS -> flight JSON
  match        Attach archive + forecast weather to waypoints
  live         Free-source live track + weather (once or loop)
  along-track  Plain route + time-matched weather timeline / changes
  phase1       Forecast vs truth, equations, suitability gate
  phase2       Correct forecasts and rank routes by fuel
  stats        Print demo or existing report JSON


Along-track weather timeline
----------------------------

Best workflow to get plain route data paired with weather at the right
time, then see where conditions change:

1. Get the route with real times

  Prefer a flown ADS-B path so each waypoint carries the fix timestamp
  as eta_utc (not a single departure stamp on a great-circle skeleton):

  PYTHONPATH=. python3 -m airpath track \
    --ident EK001 --origin OMDB --dest EGLL \
    --departure 2026-08-10T06:00:00Z \
    --providers opensky \
    --out /tmp/ek001-flown.json

  Or use an existing enriched / planned flight JSON that already has
  per-waypoint eta_utc values.

2. Attach weather (time match happens here)

  PYTHONPATH=. python3 -m airpath match \
    --flight /tmp/ek001-flown.json \
    --providers iowa,awc,ncei,era5,ecmwf_ifs,gfs \
    --out /tmp/ek001-wx.json

  Matching rule: for each waypoint, providers request the archive /
  forecast day for that eta_utc, then pick the nearest hourly sample
  (timeutil.nearest_index). The observation's issued_at_utc (and
  meta.valid_time when present) is that archive hour. waypoint_seq
  ties the sample back to lat/lon/fl/time_utc on the route.

  ADS-B path: TrackPoint.time_utc -> Waypoint.eta_utc -> nearest hour.
  Planned path: scheduled ETA along the city-pair -> nearest hour.

3. Extract the plain timeline + change points

  PYTHONPATH=. python3 -m airpath along-track \
    --flight /tmp/ek001-wx.json \
    --json /tmp/ek001-along-track.json

  Or filter and print only significant jumps:

  PYTHONPATH=. python3 -m airpath along-track \
    --flight /tmp/ek001-wx.json \
    --sources gfs,era5 --variables wind_kt,temp_c \
    --changes-only

  Defaults for "significant" use Phase 1 moderate thresholds
  (wind_kt 5, temp_c 2, wind_from_deg 15, ...). Override with
  --wind-kt-change / --temp-c-change.

JSON shape (kind=airpath_along_track):

  points[]
      seq, lat, lon, fl, time_utc
      weather[]  source, variable, value, issued_at_utc,
                 valid_time_utc, is_forecast, meta
      deltas[]   vs previous waypoint (same source+variable),
                 including significant flag

  changes[]
      Same fields as a significant delta, plus lat/lon/fl/time_utc
      so you can point at the exact place and time weather shifted.

Offline only: along-track never calls the network; it reorganizes an
already-matched flight JSON. For continuous live extracts, run
`airpath live` then along-track on the dated *_flight.json.


Live free-source automation
---------------------------

Pull near-live ADS-B and free weather for a flight ident or city pair,
write dated JSON under a configurable output directory, and optionally
repeat on an interval. Default providers are free only:

  opensky, iowa, awc, ncei, era5, ecmwf_ifs, gfs, ecmwf

Paid sources (FlightAware, FR24, OAG, IBM, Meteoblue, CDS) are not
called unless you pass them explicitly and the matching API keys exist.
FlightsFrom / Flighty stay URL-only (never scraped). ECMWF Open Data
GRIB URLs are recorded for planning; GRIB is not auto-downloaded.

Hermes Agent (Nous Research) is a separate self-hosted agent with cron /
script-only jobs. It is not installed in this environment and is not
required. The built-in loop covers continuous extraction. If you deploy
Hermes later, wrap the same command as a no-agent cron job, for example:

  hermes cron create "every 5m" --no-agent \\
    --script hermes_live.py --name airpath-ek001

Or schedule OS cron / systemd against the CLI below.

One-shot dry-run (prints planned URLs, no HTTP):

  PYTHONPATH=. python3 -m airpath live \\
    --ident EK001 --origin OMDB --dest EGLL \\
    --out-dir data/live --dry-run

One-shot live extract:

  PYTHONPATH=. python3 -m airpath live \\
    --ident EK001 --origin OMDB --dest EGLL \\
    --out-dir data/live

Continuous extract every 5 minutes (Ctrl-C to stop):

  PYTHONPATH=. python3 -m airpath live \\
    --ident EK001 --origin OMDB --dest EGLL \\
    --out-dir data/live --loop --every 300

From an existing flight JSON:

  PYTHONPATH=. python3 -m airpath live \\
    --flight data/ek001-omdb-egll.json \\
    --out-dir data/live --dry-run

Thin Hermes-oriented wrapper (defaults argv to `live`):

  PYTHONPATH=. python3 scripts/hermes_live.py \\
    --ident EK001 --origin OMDB --dest EGLL --dry-run

Outputs (under --out-dir, gitignored *.json):

  {ident}_{stamp}.json
      Snapshot: planned URLs, track meta, errors, observation counts

  {ident}_{stamp}_flight.json
      Enriched flight (track + weather) when not --dry-run and a track
      or observations were attached

Implementation: airpath/automation.py (stdlib). Tests mock fetch so CI
needs no network.


Data providers
--------------

Flight tracking and schedules

  opensky       OpenSky Network. No auth. Free ADS-B states,
                departures, icao24 track.

  flightaware   FlightAware AeroAPI. Auth: FLIGHTAWARE_API_KEY.
                Ident feed, position history, airport FIDS.

  fr24          Flightradar24. Auth: FR24_API_TOKEN.
                Live map / flight positions.

  oag           OAG Aviation. Auth: OAG_API_KEY.
                Forward schedules and historical analytics.

  flightsfrom   FlightsFrom.com. No auth.
                Route-network URL only (never scraped).

  flighty       Flighty. No auth. Consumer FIDS pointer;
                machine boards via FlightAware airport_fids.

Weather archives and forecasts

  iowa          Phase 1 actual. METAR/ASOS, PIREP, RAOB.

  awc           Actual + FD forecast. METAR, PIREP (<=15 days),
                winds/temps.

  ncei          Phase 1 actual. ISD global-hourly TMP/WND.

  ecmwf         Official ECMWF. Optional CDSAPI_KEY for ERA5 3D.
                Open Data IFS/AIFS GRIB URLs + MARS + ERA5 CDS.

  era5          Phase 1 truth. Surface via Open-Meteo; 3D via ecmwf.

  ecmwf_ifs     IFS analysis hours. Pressure-level wind/temp (JSON).

  gfs           Forecast + Phase 2. GFS winds aloft.

  ibm           Commercial. Auth: IBM_WEATHER_API_KEY.
                Turbulence, icing, high-alt winds.

  meteoblue     Commercial. Auth: METEOBLUE_API_KEY.
                FL fields through FL550.

Providers without keys are skipped, not failed. HTML pages
(flightsfrom, flighty) are never fetched. ECMWF Open Data GRIB is
recorded as URL/MARS by default (decode needs eccodes).


Observation source labels (in flight JSON)
------------------------------------------

  gfs / era5 / ecmwf_ifs / ecmwf_aifs
      Model fields

  metar / pirep / ncei / awc_winds
      Observations

  ibm_aviation / meteoblue
      Commercial aviation weather

  aircraft_sensor
      QAR / FDR actuals

  ads_b
      Ground speed from track providers

  simulation
      ISA book fuel, no wind

  weather_model
      Generic / demo model


Forecast to truth crosswalk
---------------------------

Phase 1 can pair forecasts against an independent truth (not the same
source against itself):

  gfs | ibm | meteoblue | ecmwf_ifs | ecmwf_aifs
      -> era5 / IFS analysis / pirep / QAR

Use --pairing auto on archive flights, same for the synthetic demo.


Variables and thresholds
------------------------

  wind_kt
      holds true <= 5 kt; moderate >= 5; severe >= 15

  wind_from_deg
      holds true <= 15 deg; moderate >= 15; severe >= 40

  temp_c / isa_dev_k
      holds true <= 2 K; moderate >= 2; severe >= 4

  fuel_flow_kg_h
      holds true <= 150; moderate >= 150; severe >= 400

  ground_speed_kt
      holds true <= 20 kt; moderate >= 20; severe >= 50

Suitability (0-1) blends hit rate, RMSE, and sample count. Phase 2
opens when a forecast product scores suitable wind or temp
(suitability >= 0.55, n >= 6).


Route search (Phase 2)
----------------------

- City pair stays fixed (origin / destination).
- Interior points offset +/-50 / +/-100 NM perpendicular to the great
  circle (sin taper).
- Flight levels: FL 350 / 370 / 390.
- Cost = widebody cruise fuel flow x time; GS = TAS + tailwind.
- Intensity = |tailwind| + 8 * |ISA_dev|.


Flight JSON format
------------------

CSV is gitignored (PII). Use JSON shaped like
airpath.ingest.flight_from_dict / data/ek001-omdb-egll.json:

  {
    "flight_id": "EK001",
    "origin_icao": "OMDB",
    "dest_icao": "EGLL",
    "origin": {"lat": 25.2532, "lon": 55.3657},
    "dest": {"lat": 51.47, "lon": -0.4543},
    "aircraft_type": "A388",
    "departure_utc": "2026-08-10T06:00:00Z",
    "waypoints": [
      {
        "seq": 0,
        "lat": 25.2532,
        "lon": 55.3657,
        "fl": 350,
        "eta_utc": "2026-08-10T06:00:00Z"
      }
    ],
    "observations": [
      {
        "waypoint_seq": 0,
        "source": "gfs",
        "variable": "wind_kt",
        "value": 72.0,
        "issued_at_utc": "2026-08-10T00:00:00Z",
        "is_forecast": true,
        "meta": {}
      }
    ]
  }


Package layout
--------------

  airpath/
    cli.py           demo | sources | track | match | live | along-track | ...
    automation.py    live free-source extract (once / loop)
    timeline.py      along-track route + weather deltas / changes
    models.py        Flight, Observation, equations, thresholds
    verify.py        Phase 1 pairing + MOS
    stats.py         suitability / phase1_ready gate
    route.py         parallel tracks + fuel ranking
    fuel.py / isa.py / geo.py
    ingest.py        load/save flight JSON
    providers/       weather + ADS-B / schedule adapters
  scripts/hermes_live.py
  data/ek001-omdb-egll.json
  data/live/         dated live snapshots (JSON gitignored)
  tests/
  README.md


Demo
----

Synthetic EK001 OMDB-EGLL embeds a known wind MOS bias. Phase 1 should
recover approximately:

  corrected = -8 + 1.12 * forecast

  PYTHONPATH=. python3 -m airpath demo --json /tmp/airpath-report.json


Next steps (real QAR)
---------------------

1. Import FDR/QAR into JSON as aircraft_sensor actuals.
2. Store the pre-departure forecast on the same flight
   (is_forecast: true).
3. Run phase1 --pairing auto and check suitability + equations.
4. When the gate passes, run phase2 for the next city pair.


License / attribution notes
---------------------------

- ECMWF Open Data IFS/AIFS: CC-BY-4.0 (https://www.ecmwf.int/).
  Cite ECMWF when redistributing fields.
- OpenSky, Iowa Mesonet, AWC, NCEI, Open-Meteo: respect each
  provider's terms and rate limits.
- Commercial APIs (FlightAware, FR24, OAG, IBM, Meteoblue): require
  your own subscription keys.
