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


def test_view_factor_negative_altitude_raises():
    with pytest.raises(ValueError):
        view_factor_to_planet(-1.0)


from powerpy.schemas.mission import MissionOrbit


def _orbit():
    return MissionOrbit(params={
        "altitude_km": 35786.0,
        "sun_intensity_eol_min": 1322.0,
        "sun_intensity_bol": 1367.0,
        "bond_albedo": 0.30,
        "planet_temp_k": 255.0,
        "ir_emissivity": 1.0,
    })


def test_mission_orbit_typed_accessors():
    o = _orbit()
    assert o.altitude_km == 35786.0
    assert o.sun_intensity_eol_min == 1322.0
    assert o.sun_intensity_bol == 1367.0
    assert o.bond_albedo == 0.30
    assert o.planet_temp_k == 255.0
    assert o.ir_emissivity == 1.0


def test_mission_orbit_defaults_when_missing():
    o = MissionOrbit(params={"altitude_km": 500.0})
    assert o.bond_albedo == 0.30        # default
    assert o.planet_temp_k == 255.0     # default
    assert o.ir_emissivity == 1.0       # default
    assert o.sun_intensity_eol_min == 1367.0  # default AM0
    assert o.sun_intensity_bol == 1367.0  # default


def test_mission_orbit_altitude_required():
    with pytest.raises(KeyError):
        _ = MissionOrbit(params={}).altitude_km


from pathlib import Path
from powerpy.loader.report import load_report_data

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "src" / "powerpy" / "param" / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"

needs_params = pytest.mark.skipif(
    not PARAMS.exists(), reason="params.xlsx not present")


@needs_params
def test_report_loads_mission_orbit():
    md = load_report_data(PARAMS, DATA)
    assert md.mission_orbit is not None
    assert md.mission_orbit.altitude_km == 35786.0          # GEO
    assert md.mission_orbit.sun_intensity_eol_min == 1322.0
    assert len(md.mission_orbit.params) > 0


from powerpy.analysis.power_budget import compute_power_budget, PowerBudget


def test_power_budget_values_geo():
    b = compute_power_budget(_orbit(), season=1.0, tilt=1.0, efficiency=0.30)
    assert isinstance(b, PowerBudget)
    assert b.view_factor == pytest.approx(0.02288, abs=1e-4)
    assert b.incident_solar_w_m2 == pytest.approx(1322.0, abs=0.1)
    assert b.electrical_w_m2 == pytest.approx(396.6, abs=0.2)   # 0.30 * 1322
    assert b.albedo_w_m2 == pytest.approx(9.08, abs=0.05)        # 0.30*1322*F
    assert b.ir_w_m2 == pytest.approx(5.49, abs=0.05)            # sigma*255^4*F


def test_power_budget_lines_show_calculation():
    b = compute_power_budget(_orbit(), season=1.0, tilt=1.0, efficiency=0.30)
    labels = [ln.label for ln in b.lines]
    assert "Electrical extracted" in labels
    assert "Albedo load" in labels
    assert "Planetary IR load" in labels
    elec = next(ln for ln in b.lines if ln.label == "Electrical extracted")
    assert "0.30" in elec.substitution and "1322" in elec.substitution


from powerpy.analysis.thermal_data import run_thermal_report, ThermalCase
from powerpy.schemas._common import Phase
from powerpy.schemas.fluxes import LaunchConfig


@needs_params
def test_thermal_report_has_power_budget():
    md = load_report_data(PARAMS, DATA)
    cases = [ThermalCase("EOL", Phase.END_OF_LIFE, LaunchConfig.SINGLE,
                          season=0.967)]
    d = run_thermal_report(md, cases)
    assert d.power_budget is not None
    assert d.power_budget.electrical_w_m2 > 0
    assert 0 < d.power_budget.albedo_w_m2 < 50
    assert 0 < d.power_budget.ir_w_m2 < 50
