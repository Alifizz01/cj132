"""Environmental power budget (per m^2) for the reports.

Pure calculation: given the mission orbit/environment, it returns the four
power-density terms a report shows -- incident solar, electrical extracted at
the cell efficiency, albedo, and planetary IR -- plus the worked-calculation
lines (formula + substituted numbers + result) used to print the derivation.

Albedo/IR use the geometric view factor from altitude, so GEO automatically
sees a much smaller planetary load than LEO.  No I/O, no rendering.
"""
from __future__ import annotations

from dataclasses import dataclass

from powerpy.model.environment import SIGMA, albedo_flux, planetary_ir_flux
from powerpy.model.orbit import view_factor_to_planet
from powerpy.schemas.mission import MissionOrbit

# A GEO fallback used only when ReportMetadata carries no mission_orbit
# (e.g. hand-built metadata in a test); the loader always supplies a real one.
DEFAULT_ORBIT = MissionOrbit(params={
    "altitude_km": 35786.0, "sun_intensity_eol_min": 1322.0,
})


@dataclass(frozen=True)
class CalcLine:
    """One worked line of the budget derivation."""
    label: str          # "Albedo load"
    formula: str        # LaTeX math, e.g. r"P_{\mathrm{alb}} = a \cdot S \cdot F"
    substitution: str   # LaTeX math, e.g. r"0.30 \times 1322 \times 0.0229"
    value_w_m2: float


@dataclass(frozen=True)
class PowerBudget:
    incident_solar_w_m2: float
    electrical_w_m2: float
    albedo_w_m2: float
    ir_w_m2: float
    efficiency: float
    view_factor: float
    tilt: float
    altitude_km: float
    lines: tuple


def compute_power_budget(orbit: MissionOrbit, *, season: float = 1.0,
                         tilt: float = 1.0,
                         efficiency: float = 0.30) -> PowerBudget:
    """Per-m^2 environmental power budget for one operating point.

    ``efficiency`` is the space-grade cell conversion efficiency (~0.30) used
    for the *displayed* electrical term; the thermal solve still uses the
    model's computed MPP power.
    """
    s = orbit.sun_intensity_eol_min * season       # incident solar [W/m^2]
    f = view_factor_to_planet(orbit.altitude_km)    # geometric view factor
    a = orbit.bond_albedo
    tp = orbit.planet_temp_k
    eps = orbit.ir_emissivity

    electrical = efficiency * s * tilt
    albedo = albedo_flux(a, s, f)
    ir = planetary_ir_flux(tp, eps, f)

    lines = (
        CalcLine(
            "Incident solar", r"S = S_{\mathrm{EOL}} \cdot \mathrm{season}",
            r"%.0f \times %.3f" % (orbit.sun_intensity_eol_min, season), s),
        CalcLine(
            "Electrical extracted",
            r"P_{\mathrm{elec}} = \eta \cdot S \cdot \cos\theta",
            r"%.2f \times %.0f \times %.3f" % (efficiency, s, tilt), electrical),
        CalcLine(
            "Albedo load", r"P_{\mathrm{alb}} = a \cdot S \cdot F",
            r"%.2f \times %.0f \times %.4f" % (a, s, f), albedo),
        CalcLine(
            "Planetary IR load",
            r"P_{\mathrm{IR}} = \varepsilon\,\sigma\,T_p^4\,F",
            r"%.2f \times %.3g \times %.0f^4 \times %.4f" % (eps, SIGMA, tp, f),
            ir),
    )
    return PowerBudget(
        incident_solar_w_m2=s, electrical_w_m2=electrical,
        albedo_w_m2=albedo, ir_w_m2=ir, efficiency=efficiency,
        view_factor=f, tilt=tilt, altitude_km=orbit.altitude_km, lines=lines)
