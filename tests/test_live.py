"""Unit tests for live free-source automation (mocked fetch, no network)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from airpath.automation import (
    LIVE_FREE_PROVIDERS,
    resolve_flight,
    run_live,
    run_live_once,
    snapshot_basename,
)
from airpath.cli import main
from airpath.providers.http import PlannedRequest


FIXED_NOW = datetime(2026, 8, 24, 9, 30, 0, tzinfo=timezone.utc)


class ResolveFlightTests(unittest.TestCase):
    def test_skeleton_from_ident(self):
        flight = resolve_flight(
            ident="EK001",
            origin="DXB",
            dest="LHR",
            departure="2026-08-24T06:00:00Z",
        )
        self.assertEqual(flight.flight_id, "EK001")
        self.assertEqual(flight.origin_icao, "OMDB")
        self.assertEqual(flight.dest_icao, "EGLL")
        self.assertGreaterEqual(len(flight.waypoints), 2)

    def test_default_departure_uses_now(self):
        flight = resolve_flight(
            ident="EK001",
            origin="OMDB",
            dest="EGLL",
            now=lambda: FIXED_NOW,
        )
        self.assertEqual(flight.departure_utc, "2026-08-24T09:30:00Z")

    def test_requires_args(self):
        with self.assertRaises(ValueError):
            resolve_flight(ident="EK001")


class LiveDryRunTests(unittest.TestCase):
    def test_dry_run_writes_planned_urls_no_fetch(self):
        fetch = mock.Mock(side_effect=AssertionError("network should not be called"))
        with tempfile.TemporaryDirectory() as tmp:
            result = run_live_once(
                ident="EK001",
                origin="OMDB",
                dest="EGLL",
                departure="2026-08-24T06:00:00Z",
                out_dir=tmp,
                dry_run=True,
                fetch=fetch,
                now=lambda: FIXED_NOW,
            )
            fetch.assert_not_called()
            self.assertTrue(result.dry_run)
            self.assertIsNotNone(result.out_path)
            self.assertTrue(result.out_path.is_file())
            payload = json.loads(result.out_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["kind"], "airpath_live")
            self.assertTrue(payload["dry_run"])
            self.assertGreater(payload["match"]["n_requests"], 0)
            urls = [r["url"] for r in payload["match"]["requests"]]
            self.assertTrue(any("opensky-network.org" in u for u in urls))
            # Free weather planners should appear
            providers = {r["provider"] for r in payload["match"]["requests"]}
            self.assertIn("opensky", providers)
            self.assertTrue({"iowa", "awc", "gfs"} & providers)

    def test_default_providers_are_free_only(self):
        paid = {"flightaware", "fr24", "oag", "ibm", "meteoblue"}
        self.assertFalse(paid & set(LIVE_FREE_PROVIDERS))
        self.assertIn("opensky", LIVE_FREE_PROVIDERS)
        self.assertIn("ecmwf", LIVE_FREE_PROVIDERS)


class LiveFetchTests(unittest.TestCase):
    def test_mocked_fetch_loop(self):
        def fake_fetch(req: PlannedRequest):
            # Minimal empty payloads — parsers tolerate empty / unknown shapes.
            if req.provider == "opensky":
                return []
            if req.provider in {"iowa", "awc", "ncei"}:
                return [] if req.product != "pirep" else {"features": []}
            if req.provider in {"gfs", "era5", "ecmwf_ifs"}:
                return {"hourly": {"time": []}}
            if req.provider == "ecmwf":
                return {"status": "planned_only"}
            return {}

        sleeps: list[float] = []
        with tempfile.TemporaryDirectory() as tmp:
            results = run_live(
                ident="EK001",
                origin="OMDB",
                dest="EGLL",
                departure="2026-08-24T06:00:00Z",
                out_dir=tmp,
                dry_run=False,
                loop=True,
                every=1.5,
                max_runs=2,
                fetch=fake_fetch,
                sleep=sleeps.append,
                now=lambda: FIXED_NOW,
            )
            self.assertEqual(len(results), 2)
            self.assertEqual(sleeps, [1.5])
            for run in results:
                self.assertTrue(run.out_path.is_file())
                data = json.loads(run.out_path.read_text(encoding="utf-8"))
                self.assertEqual(data["flight_id"], "EK001")
                self.assertFalse(data["dry_run"])

    def test_snapshot_basename(self):
        self.assertEqual(
            snapshot_basename("EK001", "20260824T093000Z"),
            "EK001_20260824T093000Z",
        )


class LiveCliTests(unittest.TestCase):
    def test_cli_live_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(
                    [
                        "live",
                        "--ident",
                        "EK001",
                        "--origin",
                        "OMDB",
                        "--dest",
                        "EGLL",
                        "--departure",
                        "2026-08-24T06:00:00Z",
                        "--out-dir",
                        tmp,
                        "--dry-run",
                    ]
                )
            self.assertEqual(code, 0)
            out = buf.getvalue()
            self.assertIn("opensky", out)
            files = list(Path(tmp).glob("*.json"))
            self.assertEqual(len(files), 1)

    def test_cli_live_from_flight_json(self):
        sample = Path(__file__).resolve().parents[1] / "data" / "ek001-omdb-egll.json"
        with tempfile.TemporaryDirectory() as tmp:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(
                    [
                        "live",
                        "--flight",
                        str(sample),
                        "--out-dir",
                        tmp,
                        "--dry-run",
                        "--providers",
                        "opensky,iowa,gfs",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn("planned=", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
