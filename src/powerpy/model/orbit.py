"""Vendored orbital mechanics -- pure numpy, no astropy / numba / hapsira.

A small, self-contained replacement for the bits of hapsira this project would
use for power/thermal analysis.  Everything here is closed-form for a Keplerian
(circular by default) orbit, so it has zero compiled or pip dependencies and
runs from source on a locked-down machine.

Covers:
  * orbital period from altitude (Kepler's third law),
  * ECI position propagation over one orbit,
  * Sun direction (ECI) for a day of year,
  * beta angle (Sun elevation above the orbit plane),
  * eclipse fraction / duration (cylindrical-shadow geometry), and a per-step
    geometric in-shadow test,
  * a flux-vs-time timeline (solar/albedo/IR per step) that drops straight into
    the transient thermal solver.

Frames: a simple Earth-centred inertial (ECI) frame with the Sun placed via the
ecliptic obliquity.  Good to ~1 deg for power/thermal sizing; it is NOT an
ephemeris-grade propagator (that is what hapsira/astropy are for, and what you
do not need here).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from powerpy.model.environment import (
    AM0,
    FluxPoint,
    albedo_flux,
    planetary_ir_flux,
)

# --- constants ------------------------------------------------------------
MU_EARTH = 3.986004418e14     # Earth gravitational parameter GM [m^3/s^2]
R_EARTH_M = 6378137.0         # Earth equatorial radius [m]
OBLIQUITY_DEG = 23.4393       # ecliptic obliquity
DAYS_PER_YEAR = 365.25
VERNAL_EQUINOX_DOY = 80       # ~20 March: solar ecliptic longitude = 0


# --- rotations ------------------------------------------------------------
def _rx(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rz(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


# --- core ----------------------------------------------------------------
def orbital_period(altitude_km: float, *, body_radius_km: float = R_EARTH_M / 1e3,
                   mu: float = MU_EARTH) -> float:
    """Orbital period [s] of a circular orbit (Kepler's third law)."""
    a = (body_radius_km + altitude_km) * 1e3
    if a <= 0:
        raise ValueError("semi-major axis must be > 0")
    return float(2.0 * np.pi * np.sqrt(a ** 3 / mu))


def view_factor_to_planet(altitude_km: float,
                          body_radius_km: float = R_EARTH_M / 1e3) -> float:
    """Geometric nadir view factor of a flat plate to the planet sphere.

    ``F = (R / (R + h))**2`` -- the fraction of a downward-facing plate's
    hemisphere filled by the planet disc.  This is the upper bound (face
    looking straight at the planet); it falls with altitude, so GEO sees a
    much smaller albedo/IR load than LEO.
    """
    if altitude_km < 0:
        raise ValueError("altitude_km must be >= 0")
    return float((body_radius_km / (body_radius_km + altitude_km)) ** 2)


def sun_direction_eci(day_of_year: float) -> np.ndarray:
    """Unit vector from Earth to Sun in ECI for a given day of year (approx)."""
    lam = np.radians((day_of_year - VERNAL_EQUINOX_DOY) * 360.0 / DAYS_PER_YEAR)
    eps = np.radians(OBLIQUITY_DEG)
    s = np.array([np.cos(lam), np.sin(lam) * np.cos(eps), np.sin(lam) * np.sin(eps)])
    return s / np.linalg.norm(s)


def orbit_normal(inclination_deg: float, raan_deg: float) -> np.ndarray:
    """Unit angular-momentum (orbit-plane normal) vector in ECI."""
    n = _rz(np.radians(raan_deg)) @ _rx(np.radians(inclination_deg)) @ np.array([0.0, 0.0, 1.0])
    return n / np.linalg.norm(n)


def orbit_positions(altitude_km: float, inclination_deg: float, raan_deg: float,
                    n_steps: int) -> tuple[np.ndarray, np.ndarray]:
    """(times[s], positions[N,3] in ECI metres) over exactly one circular orbit."""
    if n_steps <= 0:
        raise ValueError("n_steps must be > 0")
    r = (R_EARTH_M / 1e3 + altitude_km) * 1e3
    period = orbital_period(altitude_km)
    t = np.linspace(0.0, period, n_steps, endpoint=False)
    theta = 2.0 * np.pi * t / period
    rot = _rz(np.radians(raan_deg)) @ _rx(np.radians(inclination_deg))
    plane = np.stack([r * np.cos(theta), r * np.sin(theta), np.zeros_like(theta)], axis=1)
    pos = plane @ rot.T
    return t, pos


def beta_angle(inclination_deg: float, raan_deg: float, day_of_year: float) -> float:
    """Beta angle [deg]: Sun elevation above the orbit plane.

    0 deg = Sun in the orbit plane (longest eclipse); +-90 deg = Sun normal to
    the plane (often full sun, no eclipse).
    """
    sun = sun_direction_eci(day_of_year)
    n = orbit_normal(inclination_deg, raan_deg)
    return float(np.degrees(np.arcsin(np.clip(np.dot(sun, n), -1.0, 1.0))))


def eclipse_fraction(altitude_km: float, beta_deg: float, *,
                     body_radius_km: float = R_EARTH_M / 1e3) -> float:
    """Fraction of the orbit spent in Earth's shadow (cylindrical-shadow model).

    Returns 0 when the beta angle is high enough that the orbit clears the
    shadow entirely.
    """
    R = body_radius_km
    a = body_radius_km + altitude_km
    ratio = np.sqrt(1.0 - (R / a) ** 2)             # = sqrt(h^2+2Rh)/(R+h)
    cb = np.cos(np.radians(beta_deg))
    if cb <= 1e-12 or ratio / cb >= 1.0:
        return 0.0
    return float(np.degrees(np.arccos(ratio / cb)) / 180.0)


def eclipse_duration(altitude_km: float, beta_deg: float) -> float:
    """Eclipse duration [s] = period * eclipse fraction."""
    return orbital_period(altitude_km) * eclipse_fraction(altitude_km, beta_deg)


def in_shadow(position_m: np.ndarray, sun_unit: np.ndarray, *,
              body_radius_m: float = R_EARTH_M) -> bool:
    """True if an ECI position sits in Earth's cylindrical umbra."""
    along = float(np.dot(position_m, sun_unit))          # +ve = sun side
    perp = position_m - along * sun_unit
    return along < 0.0 and float(np.linalg.norm(perp)) < body_radius_m


# --- flux timeline -------------------------------------------------------
def orbit_flux_timeline(altitude_km: float, inclination_deg: float,
                        raan_deg: float, day_of_year: float, n_steps: int, *,
                        bond_albedo: float = 0.3, planet_temp_k: float = 255.0,
                        ir_emissivity: float = 1.0, view_factor: float = 0.3,
                        distance_au: float = 1.0) -> list[FluxPoint]:
    """Geometric flux timeline over one orbit (drop-in for the transient solver).

    Propagates the orbit, flags eclipse from the actual shadow geometry (not a
    fixed fraction), and returns one :class:`FluxPoint` per step: full Sun on
    the sunlit arc, zero during eclipse; albedo tracks the Sun; planetary IR is
    always present.
    """
    t, pos = orbit_positions(altitude_km, inclination_deg, raan_deg, n_steps)
    sun = sun_direction_eci(day_of_year)
    p_sun0 = AM0 / distance_au ** 2
    p_ir = planetary_ir_flux(planet_temp_k, ir_emissivity, view_factor)
    out: list[FluxPoint] = []
    for ti, ri in zip(t, pos):
        ecl = in_shadow(ri, sun)
        p_sun = 0.0 if ecl else p_sun0
        p_alb = 0.0 if ecl else albedo_flux(bond_albedo, p_sun0, view_factor)
        out.append(FluxPoint(time_s=float(ti), p_sun=p_sun, p_albedo=p_alb,
                             p_ir=p_ir, tilt=1.0, eclipsed=ecl))
    return out


@dataclass(frozen=True)
class OrbitSummary:
    """Headline orbit numbers for a report/printout."""
    altitude_km: float
    period_s: float
    period_min: float
    beta_deg: float
    eclipse_fraction: float
    eclipse_min: float


def summarize_orbit(altitude_km: float, inclination_deg: float, raan_deg: float,
                    day_of_year: float) -> OrbitSummary:
    """Period, beta angle, eclipse fraction & duration in one call."""
    period = orbital_period(altitude_km)
    beta = beta_angle(inclination_deg, raan_deg, day_of_year)
    ef = eclipse_fraction(altitude_km, beta)
    return OrbitSummary(altitude_km=altitude_km, period_s=period,
                        period_min=period / 60.0, beta_deg=beta,
                        eclipse_fraction=ef, eclipse_min=period * ef / 60.0)
