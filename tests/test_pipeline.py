from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from airpath.cli import main
from airpath.demo import build_demo_flight
from airpath.ingest import flight_from_dict, flight_to_dict, load_flight, save_flight
from airpath.models import Observation, Source, Variable


class PipelineTests(unittest.TestCase):
    def test_roundtrip_json(self):
        flight = build_demo_flight()
        payload = flight_to_dict(flight)
        loaded = flight_from_dict(payload)
        self.assertEqual(loaded.flight_id, "EK001")
        self.assertEqual(len(loaded.waypoints), len(flight.waypoints))
        self.assertEqual(len(loaded.observations), len(flight.observations))
        self.assertIsInstance(loaded.observations[0], Observation)
        self.assertIsInstance(loaded.observations[0].source, Source)
        self.assertIsInstance(loaded.observations[0].variable, Variable)

    def test_cli_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.json"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["demo", "--json", str(out)])
            self.assertEqual(rc, 0)
            data = json.loads(out.read_text())
            self.assertTrue(data["phase1_ready"])
            self.assertGreater(data["n_verifications"], 0)

    def test_cli_phase1_on_saved_flight(self):
        flight = build_demo_flight()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flight.json"
            save_flight(path, flight)
            again = load_flight(path)
            self.assertEqual(again.flight_id, "EK001")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["phase1", "--flight", str(path)])
                rc2 = main(["phase2", "--flight", str(path)])
            self.assertEqual(rc, 0)
            self.assertEqual(rc2, 0)
