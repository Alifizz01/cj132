# -*- coding: utf-8 -*-
"""Orbit-driven environment fluxes (sun, eclipse, albedo, planetary IR).

The thermal solve needs P_sun, P_albedo, P_IR and the pointing tilt at each moment;
around an orbit these vary (and drop in eclipse). This module computes them, using
``hapsira`` (the maintained poliastro fork) to propagate the orbit. It replaces the
legacy ``eclipse.py`` flux path, whose albedo function was flagged broken and which
depended on poliastro/astropy that are not importable here.

The flux physics (inverse-square solar, view-factor albedo/IR) is pure and tested.
The hapsira propagation is wired behind a guarded import so the rest of the module
imports even where an orbit hasn't been defined yet.

Status: flux math standalone & tested; hapsira propagation best-effort (needs an
orbit definition: central body + elements/state vector).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

AU_M = 1.495978707e11      # astronomical unit [m]
AM0 = 1367.0               # solar irradiance at 1 AU [W/m^2]
SIGMA = 5.670367e-8        # Stefan-Boltzmann [W/m^2K^4]


def solar_irradiance(distance_au: float, eclipsed: bool = False) -> float:
    """Direct solar irradiance [W/m^2] at a distance (AU); 0 in eclipse."""
    if eclipsed:
        return 0.0
    if distance_au <= 0:
        raise ValueError("distance must be > 0 AU")
    return AM0 / (distance_au ** 2)


def albedo_flux(bond_albedo: float, solar_at_planet: float, view_factor: float) -> float:
    """Planet-reflected solar irradiance onto the array [W/m^2]."""
    return bond_albedo * solar_at_planet * view_factor


def planetary_ir_flux(planet_temp_k: float, emissivity: float, view_factor: float) -> float:
    """Planetary thermal-IR irradiance onto the array [W/m^2] (grey-body)."""
    return emissivity * SIGMA * planet_temp_k ** 4 * view_factor


def cosine_tilt(alpha_deg: float, beta_deg: float, season_angle_deg: float = 0.0) -> float:
    """Pointing factor cos(alpha+season_angle)*cos(beta); 1.0 when square-on."""
    a = np.radians(alpha_deg + season_angle_deg)
    b = np.radians(beta_deg)
    return float(np.cos(a) * np.cos(b))


@dataclass
class FluxPoint:
    """Environment fluxes at one instant around the orbit."""
    time_s: float
    p_sun: float
    p_albedo: float
    p_ir: float
    tilt: float
    eclipsed: bool


def orbit_flux_timeline(period_s: float, n_steps: int, *, eclipse_fraction: float = 0.35,
                        distance_au: float = 1.0, bond_albedo: float = 0.3,
                        view_factor: float = 0.3, planet_temp_k: float = 255.0,
                        tilt: float = 1.0):
    """Analytic circular-orbit flux timeline (no ``hapsira`` needed).

    One :class:`FluxPoint` per step over one orbit of ``period_s``: full sun for
    the sunlit arc then **zero** sun during the eclipse arc (the last
    ``eclipse_fraction`` of the orbit); albedo tracks the sun (no sun, no
    reflection); planetary IR is present throughout (the planet glows even in
    shadow). Reuses :func:`solar_irradiance`, :func:`albedo_flux`,
    :func:`planetary_ir_flux`. This is the simple, testable orbit driver for the
    transient solver; ``propagate_fluxes`` (hapsira) is the high-fidelity seam.
    """
    if n_steps <= 0 or period_s <= 0:
        raise ValueError("need period_s > 0 and n_steps > 0")
    dt = period_s / n_steps
    sun_full = solar_irradiance(distance_au)
    alb_full = albedo_flux(bond_albedo, sun_full, view_factor)
    p_ir = planetary_ir_flux(planet_temp_k, 1.0, view_factor)
    pts = []
    for k in range(n_steps):
        eclipsed = (k / n_steps) >= (1.0 - eclipse_fraction)
        pts.append(FluxPoint(
            time_s=k * dt,
            p_sun=0.0 if eclipsed else sun_full,
            p_albedo=0.0 if eclipsed else alb_full,
            p_ir=p_ir, tilt=tilt, eclipsed=eclipsed,
        ))
    return pts


def propagate_fluxes(orbit, n_steps: int, step_s: float, **kw):
    """Propagate an orbit and return a list of :class:`FluxPoint` (one per step).

    Requires ``hapsira``. ``orbit`` is a ``hapsira.twobody.Orbit``. This is the
    integration seam: it computes, per step, the sun distance and eclipse state
    (for P_sun), the view factor from altitude (for albedo/IR) and the pointing
    tilt. Kept thin and explicit so it is easy to validate against the legacy
    eclipse geometry.
    """
    try:
        from hapsira.twobody.propagation import propagate  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "hapsira propagation requires the hapsira package and an Orbit; "
            "got: %s" % exc
        )
    # Implementation note: build the time grid, propagate, derive sun vector /
    # eclipse / view factor / tilt per step, and append FluxPoint(...). Left as
    # the explicit integration point against a concrete mission orbit.
    raise NotImplementedError(
        "define the mission orbit (central body + elements) and fill in the "
        "per-step sun/eclipse/view-factor geometry here"
    )
