"""Widebody cruise fuel model (A380 / 777-class order of magnitude).

Not a certified performance manual — used to rank routes from weather
and ISA deviation. Ground speed comes from TAS + along-track wind.
"""

from __future__ import annotations

import math

from .isa import density_ratio, isa_temperature_k

# Nominal cruise for a heavy widebody at M0.84 / FL350 / ISA.
NOMINAL_FF_KG_H = 6800.0
NOMINAL_MACH = 0.84
NOMINAL_FL = 350.0
KT_PER_MPS = 1.943844


def tas_kt(mach: float, oat_c: float) -> float:
    """True airspeed from Mach and static air temperature."""
    t_k = oat_c + 273.15
    a_mps = math.sqrt(1.4 * 287.05287 * t_k)
    return mach * a_mps * KT_PER_MPS


def cruise_fuel_flow_kg_h(
    fl: float,
    oat_c: float,
    *,
    mach: float = NOMINAL_MACH,
) -> float:
    """Fuel flow rises in denser / hotter-than-ISA air, falls in thin/cold air."""
    alt_ft = fl * 100.0
    sigma = density_ratio(alt_ft, oat_c)
    sigma_nom = density_ratio(NOMINAL_FL * 100.0, isa_temperature_k(NOMINAL_FL * 100.0) - 273.15)
    # Density falls with altitude (and with hot air at constant FL). ISA-hot
    # still burns more: engines need higher N1 for the same Mach.
    isa_dev = (oat_c + 273.15) - isa_temperature_k(alt_ft)
    density_term = (sigma / sigma_nom) ** 0.55
    isa_term = 1.0 + 0.004 * isa_dev
    mach_term = (mach / NOMINAL_MACH) ** 1.6
    return NOMINAL_FF_KG_H * density_term * isa_term * mach_term


def ground_speed_kt(tas: float, along_track_wind_kt: float) -> float:
    gs = tas + along_track_wind_kt
    return max(80.0, gs)


def segment_fuel_kg(
    distance_nm: float,
    gs_kt: float,
    fuel_flow_kg_h: float,
) -> float:
    if gs_kt <= 0:
        raise ValueError("ground speed must be positive")
    hours = distance_nm / gs_kt
    return fuel_flow_kg_h * hours


def segment_time_h(distance_nm: float, gs_kt: float) -> float:
    return distance_nm / max(gs_kt, 80.0)
