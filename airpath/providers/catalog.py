"""Catalog of Phase 1 archives and Phase 2 forecast products."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    title: str
    phase: tuple[str, ...]
    products: tuple[str, ...]
    auth: str
    docs_url: str
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)


PROVIDERS: tuple[ProviderInfo, ...] = (
    ProviderInfo(
        id="iowa",
        title="Iowa State University Mesonet",
        phase=("phase1_actual",),
        products=("metar", "pirep", "raob"),
        auth="none",
        docs_url="https://mesonet.agron.iastate.edu/",
        notes="Free METAR/ASOS, PIREP GeoJSON, RAOB soundings. Best check of what the weather actually was at stations and along-track PIREPs.",
    ),
    ProviderInfo(
        id="awc",
        title="NOAA Aviation Weather Center",
        phase=("phase1_actual", "phase1_forecast"),
        products=("metar", "pirep", "windtemp"),
        auth="none",
        docs_url="https://aviationweather.gov/data/api/",
        notes="Operational METAR/PIREP (≤15 days) plus FD winds/temps (CONUS-centric). No API key. Rate limit ~100 req/min.",
    ),
    ProviderInfo(
        id="ncei",
        title="NOAA NCEI global-hourly (ISD / AIRS-class archive)",
        phase=("phase1_actual",),
        products=("global_hourly",),
        auth="none",
        docs_url="https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation",
        notes="Long historical surface observations (TMP, WND). Tokenless Access Data Service. Optional NCEI_TOKEN for CDO v2.",
    ),
    ProviderInfo(
        id="ecmwf",
        title="ECMWF (Open Data IFS/AIFS + ERA5 CDS)",
        phase=("phase1_actual", "phase1_forecast", "phase2"),
        products=("ifs_open", "aifs_open", "era5_cds", "mars"),
        auth="optional:CDSAPI_KEY",
        docs_url="https://www.ecmwf.int/",
        notes="Official ECMWF portal. Open Data IFS/AIFS 0.25° GRIB2 (CC-BY-4.0, rolling ~12 runs, t/u/v on aviation pressure levels). ERA5 hourly pressure levels via Copernicus CDS. Requests use MARS language (class/stream/type/param/levelist). Live match records URLs + MARS; GRIB decode needs eccodes.",
    ),
    ProviderInfo(
        id="era5",
        title="ECMWF ERA5 reanalysis",
        phase=("phase1_actual", "phase2"),
        products=("pressure_level", "surface"),
        auth="optional:CDSAPI_KEY",
        docs_url="https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5",
        notes="ECMWF ERA5 reanalysis (gold-standard hourly 3D atmosphere, 1940–present). Surface via Open-Meteo archive; pressure-level t/u/v via CDS (see provider `ecmwf`).",
    ),
    ProviderInfo(
        id="ecmwf_ifs",
        title="ECMWF IFS (Open-Meteo historical forecast / analysis hours)",
        phase=("phase1_actual", "phase2"),
        products=("pressure_level",),
        auth="none",
        docs_url="https://www.ecmwf.int/en/forecasts/datasets/open-data",
        notes="ECMWF IFS. JSON path: Open-Meteo historical-forecast analysis hours. Official real-time files: provider `ecmwf` (data.ecmwf.int, stream=oper, Cycle 50r1).",
    ),
    ProviderInfo(
        id="gfs",
        title="NOAA GFS winds aloft",
        phase=("phase1_forecast", "phase2"),
        products=("pressure_level",),
        auth="none",
        docs_url="https://open-meteo.com/en/docs/gfs-api",
        notes="Issued GFS pressure-level wind/temp. Historical Forecast API for past flights; live GFS API for Phase 2.",
    ),
    ProviderInfo(
        id="ibm",
        title="The Weather Company (IBM Aviation API)",
        phase=("phase1_forecast", "phase2"),
        products=("aviation", "turbulence", "icing", "winds_aloft"),
        auth="IBM_WEATHER_API_KEY",
        docs_url="https://www.ibm.com/products/environmental-intelligence-suite",
        notes="Commercial. Turbulence (GTG), icing, high-altitude winds, ceiling/visibility along a path.",
    ),
    ProviderInfo(
        id="meteoblue",
        title="Meteoblue Aviation API",
        phase=("phase1_forecast", "phase2"),
        products=("aviation_fl", "cat", "icing"),
        auth="METEOBLUE_API_KEY",
        docs_url="https://docs.meteoblue.com/",
        notes="Commercial. High-resolution fields on standard flight levels to FL550 for flight-planning software.",
    ),
    ProviderInfo(
        id="opensky",
        title="OpenSky Network ADS-B",
        phase=("track", "phase1_actual"),
        products=("states", "departures", "track"),
        auth="none",
        docs_url="https://opensky-network.org/apidoc/rest.html",
        notes="Public ADS-B REST (no key). Live states in a bounding box, airport departures, optional icao24 track. Historical bulk needs OAuth. Replaces great-circle waypoints with the flown path before weather match.",
    ),
    ProviderInfo(
        id="flightaware",
        title="FlightAware AeroAPI",
        phase=("track", "phase1_actual"),
        products=("flights", "track", "airport_fids"),
        auth="FLIGHTAWARE_API_KEY",
        docs_url="https://www.flightaware.com/commercial/aeroapi/",
        notes="Commercial tracking: ident flight feed, position history, airport FIDS (live arrivals/departures — same class of board Flighty shows consumers). Header x-apikey.",
    ),
    ProviderInfo(
        id="fr24",
        title="Flightradar24 FR24 API",
        phase=("track",),
        products=("live_positions",),
        auth="FR24_API_TOKEN",
        docs_url="https://fr24api.flightradar24.com/docs",
        notes="Live global map, aircraft positions, delays. Bearer FR24_API_TOKEN. ADS-B + MLAT + satellite. Do not call without a token.",
    ),
    ProviderInfo(
        id="oag",
        title="OAG Aviation schedules",
        phase=("schedule",),
        products=("schedules",),
        auth="OAG_API_KEY",
        docs_url="https://www.oag.com/",
        notes="Enterprise forward schedules and historical analytics. Header Subscription-Key. Connectivity/frequency context, not a flown ADS-B track.",
    ),
    ProviderInfo(
        id="flightsfrom",
        title="FlightsFrom.com route network",
        phase=("schedule",),
        products=("route_network",),
        auth="none",
        docs_url="https://www.flightsfrom.com",
        notes="Public city-pair frequency pages. HTML only — dry-run records the URL; never scraped.",
    ),
    ProviderInfo(
        id="flighty",
        title="Flighty airport live boards",
        phase=("fids",),
        products=("consumer_status",),
        auth="none",
        docs_url="https://www.flightyapp.com",
        notes="Consumer app; no public API. Machine live arrivals/departures via FlightAware airport_fids. This id only records the consumer URL (never fetched).",
    ),
)


def get_provider(provider_id: str) -> ProviderInfo:
    for item in PROVIDERS:
        if item.id == provider_id:
            return item
    known = ", ".join(p.id for p in PROVIDERS)
    raise KeyError(f"unknown provider {provider_id!r}; choose from {known}")


def list_providers() -> list[dict]:
    return [p.to_dict() for p in PROVIDERS]
