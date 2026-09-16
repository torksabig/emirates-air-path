from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path

from airpath.cli import main
from airpath.demo import build_demo_flight
from airpath.geo import LatLon
from airpath.models import Source, Variable
from airpath.providers import AuthRequired, match_flight
from airpath.providers.http import PlannedRequest
from airpath.providers.tracks import (
    TrackPoint,
    downsample,
    fa_flight_id_from_flights,
    icao24_from_departures,
    parse_aeroapi_fids,
    parse_aeroapi_track,
    parse_fr24_positions,
    parse_oag_instances,
    parse_opensky_states,
    parse_opensky_track,
    plan_flightaware,
    plan_flightsfrom,
    plan_flighty,
    plan_fr24,
    plan_oag,
    plan_opensky,
    points_to_flight,
    skeleton_flight,
    to_icao,
)


class CatalogAndPlanTests(unittest.TestCase):
    def test_iata_icao_and_skeleton(self):
        self.assertEqual(to_icao("DXB"), "OMDB")
        self.assertEqual(to_icao("OMDB"), "OMDB")
        flight = skeleton_flight("EK001", "DXB", "LHR", "2026-08-10T06:00:00Z")
        self.assertEqual(flight.origin_icao, "OMDB")
        self.assertEqual(flight.dest_icao, "EGLL")
        self.assertGreaterEqual(len(flight.waypoints), 2)

    def test_opensky_urls(self):
        flight = build_demo_flight()
        planned = plan_opensky(flight, icao24="abc123")
        urls = " ".join(r.url for r in planned)
        self.assertIn("opensky-network.org/api/flights/departure", urls)
        self.assertIn("airport=OMDB", urls)
        self.assertIn("states/all", urls)
        self.assertIn("tracks/all?icao24=abc123", urls)

    def test_paid_track_requires_key(self):
        flight = build_demo_flight()
        with self.assertRaises(AuthRequired):
            plan_flightaware(flight, api_key=None)
        with self.assertRaises(AuthRequired):
            plan_fr24(flight, api_token=None)
        with self.assertRaises(AuthRequired):
            plan_oag(flight, api_key=None)
        fa = plan_flightaware(flight, api_key="test-key")
        self.assertEqual(fa[0].headers["x-apikey"], "test-key")
        self.assertIn("aeroapi.flightaware.com", fa[0].url)
        self.assertTrue(any(r.product == "airport_fids" for r in fa))
        fr = plan_fr24(flight, api_token="tok")
        self.assertEqual(fr[0].headers["Authorization"], "Bearer tok")
        self.assertIn("fr24api.flightradar24.com", fr[0].url)
        oag = plan_oag(flight, api_key="oag-key")
        self.assertEqual(oag[0].headers["Subscription-Key"], "oag-key")
        self.assertIn("DXB", oag[0].url)
        self.assertIn("LHR", oag[0].url)

    def test_html_pages_are_urls_only(self):
        flight = build_demo_flight()
        ff = plan_flightsfrom(flight)
        self.assertTrue(ff[0].meta.get("html"))
        self.assertIn("flightsfrom.com/DXB-LHR", ff[0].url)
        fy = plan_flighty(flight)
        self.assertIn("flightyapp.com", fy[0].url)


class ParserTests(unittest.TestCase):
    def test_opensky_states_and_track(self):
        states = {
            "states": [
                [
                    "abc123",
                    "EK001  ",
                    "UAE",
                    1786320000,
                    1786320000,
                    40.0,
                    30.0,
                    10668.0,
                    False,
                    250.0,
                    280.0,
                ]
            ]
        }
        pts = parse_opensky_states(states, ident="EK001")
        self.assertEqual(len(pts), 1)
        self.assertAlmostEqual(pts[0].position.lat, 30.0)
        self.assertAlmostEqual(pts[0].position.lon, 40.0)
        self.assertGreater(pts[0].fl, 300)
        self.assertGreater(pts[0].gs_kt, 400)
        track = parse_opensky_track(
            {
                "icao24": "abc123",
                "callsign": "EK001",
                "path": [
                    [1786320000, 25.25, 55.36, 10668, 280],
                    [1786323600, 30.0, 40.0, 10668, 290],
                    [1786327200, 51.47, -0.45, 10000, 300],
                ],
            },
            ident="EK001",
        )
        self.assertEqual(len(track), 3)

    def test_aeroapi_fr24_oag(self):
        pts = parse_aeroapi_track(
            {
                "positions": [
                    {
                        "latitude": 25.25,
                        "longitude": 55.36,
                        "altitude": 35000,
                        "groundspeed": 480,
                        "heading": 300,
                        "timestamp": "2026-08-10T06:00:00Z",
                    },
                    {
                        "lat": 40.0,
                        "lon": 20.0,
                        "altitude": 37000,
                        "gs": 490,
                        "timestamp": "2026-08-10T09:00:00Z",
                    },
                ]
            },
            ident="UAE1",
        )
        self.assertEqual(len(pts), 2)
        self.assertEqual(pts[0].fl, 350.0)
        self.assertEqual(pts[0].provider, "flightaware")
        fr = parse_fr24_positions(
            {"data": [{"flight": "EK001", "lat": 25.3, "lon": 55.4, "alt": 36000, "spd": 500}]},
            ident="EK001",
        )
        self.assertEqual(fr[0].provider, "fr24")
        classic = parse_fr24_positions([[25.3, 55.4, 270, 36000, 500]])
        self.assertTrue(classic)
        oag = parse_oag_instances(
            {"data": [{"flightNumber": "EK001", "departureAirport": "DXB", "arrivalAirport": "LHR"}]},
            ident="EK001",
        )
        self.assertEqual(oag[0]["origin"], "DXB")
        fids = parse_aeroapi_fids(
            {
                "departures": [
                    {
                        "ident": "UAE1",
                        "origin": {"code": "OMDB"},
                        "destination": {"code": "EGLL"},
                        "status": "En Route",
                    }
                ]
            }
        )
        self.assertTrue(fids[0]["flighty_equivalent"])

    def test_follow_up_ids(self):
        self.assertEqual(
            icao24_from_departures(
                [{"callsign": "EK001", "icao24": "8963C4"}], ident="EK001"
            ),
            "8963c4",
        )
        self.assertEqual(
            fa_flight_id_from_flights(
                {"flights": [{"ident": "UAE1", "fa_flight_id": "UAE1-123"}]},
                ident="UAE1",
            ),
            "UAE1-123",
        )

    def test_points_to_flight_and_downsample(self):
        flight = build_demo_flight()
        pts = [
            TrackPoint("2026-08-10T06:00:00Z", LatLon(25.0 + i, 55.0 - i), 350.0, gs_kt=480.0)
            for i in range(40)
        ]
        small = downsample(pts, 8)
        self.assertEqual(len(small), 8)
        self.assertEqual(small[0].position.lat, pts[0].position.lat)
        self.assertEqual(small[-1].position.lat, pts[-1].position.lat)
        flown = points_to_flight(flight, pts, include_gs=True)
        self.assertLessEqual(len(flown.waypoints), 24)
        self.assertTrue(any(o.source is Source.ADS_B for o in flown.observations))
        self.assertTrue(any(o.variable is Variable.GROUND_SPEED_KT for o in flown.observations))
        no_gs = points_to_flight(flight, pts[:3], include_gs=False)
        self.assertFalse(any(o.source is Source.ADS_B for o in no_gs.observations))


class MatchTrackTests(unittest.TestCase):
    def test_dry_run_opensky_and_html(self):
        flight = build_demo_flight()
        result = match_flight(
            flight, ["opensky", "flightsfrom", "flighty"], dry_run=True
        )
        hosts = " ".join(r.url for r in result.requests)
        self.assertIn("opensky-network.org", hosts)
        self.assertIn("flightsfrom.com", hosts)
        self.assertIn("flightyapp.com", hosts)
        self.assertEqual(result.observations, [])

    def test_paid_track_skipped_without_key(self):
        flight = build_demo_flight()
        result = match_flight(flight, ["flightaware", "fr24", "oag"], dry_run=True)
        skipped = {s["provider"] for s in result.skipped}
        self.assertEqual(skipped, {"flightaware", "fr24", "oag"})

    def test_html_never_fetched(self):
        flight = build_demo_flight()
        called: list[str] = []

        def fetch(req: PlannedRequest):
            called.append(req.url)
            return {}

        result = match_flight(flight, ["flightsfrom", "flighty"], fetch=fetch)
        self.assertEqual(called, [])
        self.assertTrue(result.requests)

    def test_track_then_weather_on_flown_path(self):
        flight = build_demo_flight()
        flight.observations = []
        seen_lats: list[str] = []

        def fetch(req: PlannedRequest):
            if req.provider == "opensky" and req.product == "departures":
                return [
                    {
                        "callsign": "EK001",
                        "icao24": "abc123",
                        "estDepartureAirport": "OMDB",
                        "estArrivalAirport": "EGLL",
                    }
                ]
            if req.provider == "opensky" and req.product == "track":
                return {
                    "icao24": "abc123",
                    "callsign": "EK001",
                    "path": [
                        [1786320000, 25.25, 55.36, 10668, 280],
                        [1786323600, 33.5, 25.0, 10668, 290],
                        [1786327200, 51.47, -0.45, 10000, 300],
                    ],
                }
            if req.provider == "opensky":
                return {"states": []}
            if req.provider == "gfs":
                seen_lats.append(req.url)
                return {
                    "hourly": {
                        "time": ["2026-08-10T06:00"],
                        "temperature_250hPa": [-48.0],
                        "wind_speed_250hPa": [70.0],
                        "wind_direction_250hPa": [270.0],
                    }
                }
            return {}

        result = match_flight(flight, ["opensky", "gfs"], fetch=fetch)
        self.assertTrue(result.applied_to_flight)
        self.assertEqual(len(result.flight.waypoints), 3)
        self.assertAlmostEqual(result.flight.waypoints[1].position.lat, 33.5)
        self.assertTrue(any("latitude=33.5" in url or "latitude=33.500" in url for url in seen_lats))
        self.assertTrue(any(o.source is Source.ADS_B for o in result.observations))
        self.assertTrue(any(o.source is Source.GFS for o in result.observations))

    def test_cli_track_dry_run(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(
                [
                    "track",
                    "--ident",
                    "EK001",
                    "--origin",
                    "OMDB",
                    "--dest",
                    "EGLL",
                    "--departure",
                    "2026-08-10T06:00:00Z",
                    "--dry-run",
                ]
            )
        self.assertEqual(rc, 0)
        self.assertIn("opensky-network.org", buf.getvalue())

    def test_cli_match_opensky_dry_run(self):
        flight_json = Path(__file__).resolve().parents[1] / "data" / "ek001-omdb-egll.json"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(
                [
                    "match",
                    "--flight",
                    str(flight_json),
                    "--providers",
                    "opensky,flightsfrom",
                    "--dry-run",
                ]
            )
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("opensky-network.org", out)
        self.assertIn("flightsfrom.com", out)


if __name__ == "__main__":
    unittest.main()
