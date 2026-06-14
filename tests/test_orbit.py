"""Vendored orbit toolkit: physical sanity checks (pure numpy, no hapsira)."""
import numpy as np
import pytest

from powerpy.model.orbit import (
    beta_angle,
    eclipse_fraction,
    in_shadow,
    orbit_flux_timeline,
    orbit_positions,
    orbital_period,
    summarize_orbit,
)


def test_leo_period():
    # 500 km LEO ~ 94.6 min
    assert orbital_period(500.0) / 60.0 == pytest.approx(94.6, abs=1.0)


def test_geo_period():
    # GEO ~ sidereal day (~1436 min)
    assert orbital_period(35786.0) / 60.0 == pytest.approx(1436.0, abs=5.0)


def test_orbit_positions_on_sphere():
    t, pos = orbit_positions(500.0, 51.6, 0.0, 64)
    r = (6378.137 + 500.0) * 1e3
    radii = np.linalg.norm(pos, axis=1)
    assert np.allclose(radii, r, rtol=1e-6)
    assert len(t) == 64


def test_high_beta_no_eclipse():
    # near-polar orbit edge-on to the sun -> high |beta| -> no eclipse
    assert eclipse_fraction(700.0, 80.0) == 0.0


def test_low_beta_has_eclipse():
    f = eclipse_fraction(500.0, 0.0)
    assert 0.30 < f < 0.40            # ~36% for low LEO


def test_eclipse_fraction_decreases_with_beta():
    assert eclipse_fraction(500.0, 0.0) > eclipse_fraction(500.0, 50.0)


def test_in_shadow_geometry():
    sun = np.array([1.0, 0.0, 0.0])
    behind = np.array([-7.0e6, 0.0, 0.0])     # directly behind Earth
    sunny = np.array([7.0e6, 0.0, 0.0])       # sun side
    assert in_shadow(behind, sun) is True
    assert in_shadow(sunny, sun) is False


def test_flux_timeline_matches_eclipse_fraction():
    fl = orbit_flux_timeline(500.0, 0.0, 0.0, 80, 200)
    frac = sum(1 for f in fl if f.eclipsed) / len(fl)
    s = summarize_orbit(500.0, 0.0, 0.0, 80)
    assert frac == pytest.approx(s.eclipse_fraction, abs=0.05)
    # sun flux is 0 in eclipse, AM0 in sun
    assert max(f.p_sun for f in fl) == pytest.approx(1367.0, abs=1.0)
    assert min(f.p_sun for f in fl) == 0.0
