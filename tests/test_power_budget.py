"""Environmental power budget: view factor, budget math, orbit loader."""
import numpy as np
import pytest

from powerpy.model.orbit import view_factor_to_planet


def test_view_factor_geo():
    # GEO 35786 km: F = (R/(R+h))^2 with R = 6378.137 km
    assert view_factor_to_planet(35786.0) == pytest.approx(0.02288, abs=1e-4)


def test_view_factor_leo():
    # 500 km LEO nadir upper bound ~ 0.86
    assert view_factor_to_planet(500.0) == pytest.approx(0.860, abs=1e-3)


def test_view_factor_surface_is_one():
    assert view_factor_to_planet(0.0) == pytest.approx(1.0, abs=1e-9)


def test_view_factor_decreases_with_altitude():
    assert view_factor_to_planet(500.0) > view_factor_to_planet(35786.0)
