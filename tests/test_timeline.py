"""Unit tests for along-track timeline (offline, no network)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from airpath.cli import main
from airpath.geo import LatLon
from airpath.models import Flight, Observation, Source, Variable, Waypoint
from airpath.timeline import (
    DEFAULT_CHANGE_THRESHOLDS,
    build_timeline,
    circular_delta_deg,
    delta_for,
    time_lag_seconds,
)


def _flight_with_wx() -> Flight:
    wps = [
        Waypoint(0, LatLon(25.25, 55.36), 350.0, "2026-08-10T06:00:00Z"),
        Waypoint(1, LatLon(30.00, 50.20), 350.0, "2026-08-10T07:00:00Z"),
        Waypoint(2, LatLon(35.00, 45.00), 350.0, "2026-08-10T08:00:00Z"),
        Waypoint(3, LatLon(40.00, 40.00), 350.0, "2026-08-10T09:00:00Z"),
    ]
    obs = [
        Observation(0, Source.GFS, Variable.WIND_KT, 50.0, "2026-08-10T06:00:00Z", True, {"valid_time": "2026-08-10T06:00:00Z"}),
        Observation(0, Source.GFS, Variable.TEMP_C, -50.0, "2026-08-10T06:00:00Z", True, {"valid_time": "2026-08-10T06:00:00Z"}),
        Observation(0, Source.ERA5, Variable.WIND_KT, 48.0, "2026-08-10T06:00:00Z", False, {}),
        # Small wind bump at seq 1 — below default 5 kt threshold
        Observation(1, Source.GFS, Variable.WIND_KT, 53.0, "2026-08-10T07:00:00Z", True, {"valid_time": "2026-08-10T07:00:00Z"}),
        Observation(1, Source.GFS, Variable.TEMP_C, -49.0, "2026-08-10T07:00:00Z", True, {}),
        Observation(1, Source.ERA5, Variable.WIND_KT, 49.0, "2026-08-10T07:00:00Z", False, {}),
        # Significant wind jump at seq 2 (+12 kt vs seq 1)
        Observation(2, Source.GFS, Variable.WIND_KT, 65.0, "2026-08-10T08:00:00Z", True, {"valid_time": "2026-08-10T08:00:00Z"}),
        Observation(2, Source.GFS, Variable.TEMP_C, -45.0, "2026-08-10T08:00:00Z", True, {}),  # +4 C significant
        Observation(2, Source.ERA5, Variable.WIND_KT, 62.0, "2026-08-10T08:00:00Z", False, {}),
        Observation(3, Source.GFS, Variable.WIND_KT, 66.0, "2026-08-10T09:00:00Z", True, {}),
        Observation(3, Source.GFS, Variable.TEMP_C, -44.5, "2026-08-10T09:00:00Z", True, {}),
        Observation(3, Source.ERA5, Variable.WIND_KT, 63.0, "2026-08-10T09:00:00Z", False, {}),
        # Wind direction wrap across 0 deg
        Observation(0, Source.GFS, Variable.WIND_FROM_DEG, 350.0, "2026-08-10T06:00:00Z", True, {}),
        Observation(1, Source.GFS, Variable.WIND_FROM_DEG, 10.0, "2026-08-10T07:00:00Z", True, {}),
    ]
    return Flight(
        flight_id="EK001",
        origin_icao="OMDB",
        dest_icao="EGLL",
        origin=wps[0].position,
        dest=wps[-1].position,
        aircraft_type="A388",
        departure_utc="2026-08-10T06:00:00Z",
        waypoints=wps,
        observations=obs,
    )


class DeltaHelpersTests(unittest.TestCase):
    def test_circular_delta_wraps(self):
        self.assertAlmostEqual(circular_delta_deg(10.0, 350.0), 20.0)
        self.assertAlmostEqual(circular_delta_deg(350.0, 10.0), -20.0)

    def test_delta_for_wind_from(self):
        self.assertAlmostEqual(delta_for("wind_from_deg", 10.0, 350.0), 20.0)
        self.assertAlmostEqual(delta_for("wind_kt", 65.0, 53.0), 12.0)

    def test_time_lag(self):
        lag = time_lag_seconds("2026-08-10T06:30:00Z", "2026-08-10T06:00:00Z")
        self.assertAlmostEqual(lag, -1800.0)


class BuildTimelineTests(unittest.TestCase):
    def test_points_carry_route_and_weather(self):
        payload = build_timeline(_flight_with_wx())
        self.assertEqual(payload["kind"], "airpath_along_track")
        self.assertEqual(payload["flight_id"], "EK001")
        self.assertEqual(payload["n_waypoints"], 4)
        self.assertGreater(payload["n_observations"], 0)
        p0 = payload["points"][0]
        self.assertEqual(p0["seq"], 0)
        self.assertEqual(p0["time_utc"], "2026-08-10T06:00:00Z")
        self.assertAlmostEqual(p0["lat"], 25.25)
        sources = {w["source"] for w in p0["weather"]}
        self.assertIn("gfs", sources)
        self.assertIn("era5", sources)
        gfs_wind = next(
            w for w in p0["weather"] if w["source"] == "gfs" and w["variable"] == "wind_kt"
        )
        self.assertEqual(gfs_wind["issued_at_utc"], "2026-08-10T06:00:00Z")
        self.assertEqual(gfs_wind["valid_time_utc"], "2026-08-10T06:00:00Z")
        self.assertTrue(gfs_wind["is_forecast"])

    def test_changes_flag_significant_jumps(self):
        payload = build_timeline(_flight_with_wx())
        self.assertGreaterEqual(payload["n_changes"], 2)
        wind_changes = [
            c
            for c in payload["changes"]
            if c["source"] == "gfs" and c["variable"] == "wind_kt"
        ]
        self.assertTrue(any(c["seq"] == 2 and abs(c["delta"] - 12.0) < 0.01 for c in wind_changes))
        temp_changes = [
            c
            for c in payload["changes"]
            if c["source"] == "gfs" and c["variable"] == "temp_c"
        ]
        self.assertTrue(any(c["seq"] == 2 for c in temp_changes))
        # seq 1 wind +3 kt should not be significant under default 5 kt
        self.assertFalse(
            any(c["seq"] == 1 and c["variable"] == "wind_kt" and c["source"] == "gfs" for c in payload["changes"])
        )

    def test_source_and_variable_filters(self):
        payload = build_timeline(
            _flight_with_wx(), sources=["era5"], variables=["wind_kt"]
        )
        for pt in payload["points"]:
            for w in pt["weather"]:
                self.assertEqual(w["source"], "era5")
                self.assertEqual(w["variable"], "wind_kt")

    def test_custom_thresholds(self):
        payload = build_timeline(
            _flight_with_wx(),
            sources=["gfs"],
            variables=["wind_kt"],
            change_thresholds={"wind_kt": 2.0},
        )
        # +3 kt at seq 1 now significant
        self.assertTrue(
            any(c["seq"] == 1 and c["variable"] == "wind_kt" for c in payload["changes"])
        )

    def test_default_thresholds_match_phase1_moderate(self):
        self.assertEqual(DEFAULT_CHANGE_THRESHOLDS["wind_kt"], 5.0)
        self.assertEqual(DEFAULT_CHANGE_THRESHOLDS["temp_c"], 2.0)


class AlongTrackCliTests(unittest.TestCase):
    def test_cli_writes_json(self):
        from airpath.ingest import save_flight

        flight = _flight_with_wx()
        with tempfile.TemporaryDirectory() as tmp:
            flight_path = Path(tmp) / "flight.json"
            out_path = Path(tmp) / "timeline.json"
            save_flight(flight_path, flight)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(
                    [
                        "along-track",
                        "--flight",
                        str(flight_path),
                        "--json",
                        str(out_path),
                        "--sources",
                        "gfs",
                        "--variables",
                        "wind_kt,temp_c",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue(out_path.is_file())
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["kind"], "airpath_along_track")
            self.assertGreater(payload["n_changes"], 0)
            text = buf.getvalue()
            self.assertIn("changes=", text)

    def test_cli_changes_only(self):
        from airpath.ingest import save_flight

        flight = _flight_with_wx()
        with tempfile.TemporaryDirectory() as tmp:
            flight_path = Path(tmp) / "flight.json"
            save_flight(flight_path, flight)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(
                    [
                        "along-track",
                        "--flight",
                        str(flight_path),
                        "--changes-only",
                        "--sources",
                        "gfs",
                    ]
                )
            self.assertEqual(code, 0)
            text = buf.getvalue()
            self.assertIn("->", text)
            self.assertIn("gfs/", text)


if __name__ == "__main__":
    unittest.main()
