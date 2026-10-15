"""International Standard Atmosphere (ISA) helpers.

Fuel planning and forecast verification both need ISA deviation:
actual OAT minus the ISA temperature at the same pressure altitude.
"""

from __future__ import annotations

T0_K = 288.15
P0_HPA = 1013.25
L_K_PER_M = 0.0065
G0 = 9.80665
R = 287.05287
FT_TO_M = 0.3048
TROPAUSE_M = 11000.0
TROPAUSE_T_K = 216.65


def fl_to_feet(flight_level: float) -> float:
    return flight_level * 100.0


def feet_to_meters(alt_ft: float) -> float:
    return alt_ft * FT_TO_M


def isa_temperature_k(alt_ft: float) -> float:
    """ISA static temperature (K) in the troposphere / lower stratosphere."""
    h = feet_to_meters(alt_ft)
    if h <= TROPAUSE_M:
        return T0_K - L_K_PER_M * h
    return TROPAUSE_T_K


def isa_temperature_c(alt_ft: float) -> float:
    return isa_temperature_k(alt_ft) - 273.15


def isa_pressure_hpa(alt_ft: float) -> float:
    """ISA pressure (hPa) below the tropopause, stratosphere-constant T above."""
    h = feet_to_meters(alt_ft)
    exponent = G0 / (R * L_K_PER_M)
    if h <= TROPAUSE_M:
        return P0_HPA * (1.0 - (L_K_PER_M * h) / T0_K) ** exponent
    p_trop = P0_HPA * (1.0 - (L_K_PER_M * TROPAUSE_M) / T0_K) ** exponent
    return p_trop * pow(2.718281828459045, -G0 * (h - TROPAUSE_M) / (R * TROPAUSE_T_K))


def nearest_pressure_level_hpa(alt_ft: float) -> int:
    """Map altitude to the Open-Meteo pressure-level grid (hPa)."""
    p = isa_pressure_hpa(alt_ft)
    grid = (1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100)
    return min(grid, key=lambda level: abs(level - p))


def isa_deviation_k(oat_c: float, alt_ft: float) -> float:
    return (oat_c + 273.15) - isa_temperature_k(alt_ft)


def density_ratio(alt_ft: float, oat_c: float) -> float:
    """rho / rho_sl using ISA pressure and actual temperature."""
    p = isa_pressure_hpa(alt_ft)
    t = oat_c + 273.15
    rho = (p * 100.0) / (R * t)
    rho_sl = (P0_HPA * 100.0) / (R * T0_K)
    return rho / rho_sl
