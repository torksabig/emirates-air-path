from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path

from airpath.cli import main
from airpath.demo import build_demo_flight
from airpath.models import Source, Variable
from airpath.providers import AuthRequired, list_providers, match_flight
from airpath.providers.awc import parse_metar, parse_pirep
from airpath.providers.commercial import plan_ibm, plan_meteoblue
from airpath.providers.iowa import parse_metar_json, parse_pirep_geojson
from airpath.providers.ncei import parse_global_hourly, parse_isd_tmp, parse_isd_wnd
from airpath.providers.openmeteo import era5_cds_request, parse_openmeteo_hourly
from airpath.stats import phase1_ready, score_verifications
from airpath.verify import collect_pairs, verify_flight


class CatalogTests(unittest.TestCase):
    def test_all_requested_providers_listed(self):
        ids = {p["id"] for p in list_providers()}
        self.assertTrue(
            {
                "iowa",
                "awc",
                "ncei",
                "era5",
                "gfs",
                "ibm",
                "meteoblue",
                "ecmwf_ifs",
                "ecmwf",
                "opensky",
                "flightaware",
                "fr24",
                "oag",
                "flightsfrom",
                "flighty",
            }
            <= ids
        )

    def test_cli_sources(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main(["sources"]), 0)
        self.assertIn("iowa", buf.getvalue())
        self.assertIn("ecmwf", buf.getvalue())
        self.assertIn("opensky", buf.getvalue())
        self.assertIn("https://www.ecmwf.int/", buf.getvalue())


class ParserTests(unittest.TestCase):
    def test_isd_tmp_and_wnd(self):
        self.assertAlmostEqual(parse_isd_tmp("+0380,1"), 38.0)
        kt, wdir = parse_isd_wnd("310,1,N,0062,1")
        self.assertAlmostEqual(wdir, 310)
        self.assertTrue(11.5 < kt < 13.0)

    def test_ncei_global_hourly(self):
        flight = build_demo_flight()
        wp = flight.waypoints[0]
        payload = [
            {
                "STATION": "41194099999",
                "DATE": "2026-08-10T06:00:00",
                "TMP": "+0380,1",
                "WND": "310,1,N,0062,1",
            }
        ]
        rows = parse_global_hourly(payload, wp, "OMDB")
        variables = {r.variable for r in rows}
        self.assertIn(Variable.TEMP_C, variables)
        self.assertTrue(all(r.source is Source.NCEI and not r.is_forecast for r in rows))

    def test_iowa_metar_and_pirep(self):
        flight = build_demo_flight()
        wp = flight.waypoints[0]
        metar = parse_metar_json(
            {"data": [{"valid": "2026-08-10T06:00:00Z", "tmpc": 37.0, "sknt": 12, "drct": 300}]},
            wp,
            "OMDB",
        )
        self.assertEqual(metar[0].source, Source.METAR)
        pireps = parse_pirep_geojson(
            {
                "features": [
                    {
                        "geometry": {"coordinates": [55.37, 25.25]},
                        "properties": {
                            "valid": "2026-08-10T06:10:00Z",
                            "temp": -49.0,
                            "sknt": 88,
                            "drct": 270,
                            "fl": 350,
                        },
                    }
                ]
            },
            flight,
        )
        self.assertTrue(any(o.source is Source.PIREP for o in pireps))

    def test_awc_metar_pirep(self):
        flight = build_demo_flight()
        metars = parse_metar(
            [{"icaoId": "OMDB", "obsTime": 1786320000, "temp": 36.0, "wspd": 10, "wdir": 290}],
            flight,
        )
        self.assertTrue(metars)
        pireps = parse_pirep(
            [
                {
                    "lat": 25.25,
                    "lon": 55.36,
                    "fltLvl": "350",
                    "temp": -47,
                    "wspd": 90,
                    "wdir": 265,
                    "obsTime": 1786320000,
                }
            ],
            flight,
        )
        self.assertTrue(any(o.variable is Variable.WIND_KT for o in pireps))

    def test_openmeteo_hourly_nearest(self):
        flight = build_demo_flight()
        wp = flight.waypoints[0]
        payload = {
            "hourly": {
                "time": ["2026-08-10T05:00", "2026-08-10T06:00", "2026-08-10T07:00"],
                "temperature_250hPa": [-50.0, -48.0, -47.0],
                "wind_speed_250hPa": [60.0, 72.0, 80.0],
                "wind_direction_250hPa": [260.0, 270.0, 275.0],
            }
        }
        rows = parse_openmeteo_hourly(
            payload, wp, Source.GFS, is_forecast=True, provider="gfs"
        )
        wind = next(r for r in rows if r.variable is Variable.WIND_KT)
        self.assertEqual(wind.value, 72.0)
        self.assertTrue(wind.is_forecast)

    def test_era5_cds_request_shape(self):
        wp = build_demo_flight().waypoints[0]
        body = era5_cds_request(wp)
        self.assertEqual(body["dataset"], "reanalysis-era5-pressure-levels")
        self.assertIn("u_component_of_wind", body["variable"])


class MatchTests(unittest.TestCase):
    def test_dry_run_urls(self):
        flight = build_demo_flight()
        result = match_flight(flight, ["iowa", "awc", "ncei", "gfs", "era5", "ecmwf_ifs"], dry_run=True)
        hosts = " ".join(r.url for r in result.requests)
        self.assertIn("mesonet.agron.iastate.edu", hosts)
        self.assertIn("aviationweather.gov", hosts)
        self.assertIn("ncei.noaa.gov", hosts)
        self.assertIn("open-meteo.com", hosts)
        self.assertEqual(result.observations, [])

    def test_commercial_requires_key(self):
        wps = build_demo_flight().waypoints[:1]
        with self.assertRaises(AuthRequired):
            plan_ibm(wps, api_key=None)
        planned = plan_meteoblue(wps, api_key="test-key")
        self.assertIn("apikey=test-key", planned[0].url)

    def test_injected_gfs_vs_ifs_crosswalk(self):
        flight = build_demo_flight()
        flight.observations = []

        def fetch(req):
            hour = {
                "time": ["2026-08-10T06:00"],
                "temperature_250hPa": [-40.0 if req.provider == "gfs" else -48.0],
                "wind_speed_250hPa": [90.0 if req.provider == "gfs" else 70.0],
                "wind_direction_250hPa": [280.0 if req.provider == "gfs" else 270.0],
            }
            if req.provider == "era5":
                hour = {
                    "time": ["2026-08-10T06:00"],
                    "temperature_2m": [38.0],
                    "wind_speed_10m": [12.0],
                    "wind_direction_10m": [310.0],
                }
            return {"hourly": hour}

        result = match_flight(flight, ["gfs", "ecmwf_ifs", "era5"], fetch=fetch)
        flight.observations.extend(result.observations)
        pairs = collect_pairs(flight.observations, mode="crosswalk")
        self.assertTrue(pairs)
        rows = verify_flight(flight, pairing="crosswalk")
        self.assertTrue(all(r.equation.form for r in rows))
        gfs_vs_ifs = [
            r
            for r in rows
            if r.source is Source.GFS and r.truth_source is Source.ECMWF_IFS
        ]
        self.assertTrue(gfs_vs_ifs)
        scores = score_verifications(rows)
        self.assertTrue(phase1_ready(scores) or any(s.source is Source.GFS for s in scores))

    def test_cli_match_dry_run(self):
        flight_json = Path(__file__).resolve().parents[1] / "data" / "ek001-omdb-egll.json"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(
                ["match", "--flight", str(flight_json), "--providers", "gfs,iowa", "--dry-run"]
            )
        self.assertEqual(rc, 0)
        self.assertIn("open-meteo.com", buf.getvalue())


class EcmwfTests(unittest.TestCase):
    def test_uv_meteorological_wind(self):
        from airpath.providers.ecmwf import uv_to_wind

        kt, from_deg = uv_to_wind(0.0, 10.0)  # wind toward north → from south
        self.assertGreater(kt, 19.0)
        self.assertAlmostEqual(from_deg, 180.0, places=4)
        kt, from_deg = uv_to_wind(10.0, 0.0)  # toward east → from west
        self.assertAlmostEqual(from_deg, 270.0, places=4)

    def test_open_data_url_and_mars(self):
        from airpath.providers.ecmwf import mars_request, open_data_grib_url, plan_open_data

        flight = build_demo_flight()
        planned = plan_open_data(flight, model="ifs")
        self.assertTrue(planned)
        url = planned[0].url
        self.assertIn("data.ecmwf.int/forecasts", url)
        self.assertIn("/ifs/0p25/oper/", url)
        self.assertTrue(url.endswith("-oper-fc.grib2"))
        mars = planned[0].meta["mars"]
        self.assertEqual(mars["class"], "od")
        self.assertEqual(mars["stream"], "oper")
        self.assertEqual(mars["param"], "t/u/v")
        self.assertEqual(mars["levtype"], "pl")
        self.assertIn(mars["levelist"], {"200", "250", "300"})
        # URL helper stays aligned with Cycle 50r1 layout
        from datetime import datetime, timezone

        cycle = datetime(2026, 8, 16, 0, tzinfo=timezone.utc)
        self.assertEqual(
            open_data_grib_url(cycle, 24, model="ifs"),
            "https://data.ecmwf.int/forecasts/20260816/00z/ifs/0p25/oper/20260816000000-24h-oper-fc.grib2",
        )
        req = mars_request(flight.waypoints[0], cycle=cycle, step=6)
        self.assertEqual(req["type"], "fc")

    def test_decoded_ifs_point_and_era5(self):
        from airpath.providers.ecmwf import parse_decoded_point

        wp = build_demo_flight().waypoints[0]
        ifs = parse_decoded_point(
            {
                "t_k": 220.15,
                "u_ms": 40.0,
                "v_ms": -10.0,
                "valid_time": "2026-08-10T06:00:00Z",
                "level_hpa": 250,
            },
            wp,
            model="ifs",
        )
        self.assertTrue(any(o.source is Source.ECMWF_IFS and o.is_forecast for o in ifs))
        era5 = parse_decoded_point(
            {
                "product_type": "reanalysis",
                "t_c": -53.0,
                "u_ms": 30.0,
                "v_ms": 5.0,
                "valid_time": "2026-08-10T06:00:00Z",
            },
            wp,
            model="ifs",
        )
        self.assertTrue(all(o.source is Source.ERA5 and not o.is_forecast for o in era5))

    def test_match_injects_ecmwf_forecast(self):
        flight = build_demo_flight()
        flight.observations = []

        def fetch(req):
            if req.provider != "ecmwf":
                return {}
            return {
                "t_k": 218.0,
                "u_ms": 25.0,
                "v_ms": 8.0,
                "valid_time": "2026-08-10T06:00:00Z",
                "level_hpa": 250,
                "product_type": "reanalysis" if req.product == "era5_cds" else "fc",
            }

        result = match_flight(flight, ["ecmwf"], fetch=fetch)
        self.assertTrue(result.observations)
        self.assertTrue(any(o.source is Source.ECMWF_IFS for o in result.observations))
        self.assertTrue(any(o.source is Source.ERA5 for o in result.observations))

    def test_cli_ecmwf_dry_run(self):
        flight_json = Path(__file__).resolve().parents[1] / "data" / "ek001-omdb-egll.json"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(
                ["match", "--flight", str(flight_json), "--providers", "ecmwf", "--dry-run"]
            )
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("data.ecmwf.int", out)
        self.assertIn("cds.climate.copernicus.eu", out)


if __name__ == "__main__":
    unittest.main()
