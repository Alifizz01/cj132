"""Smoke test for the thermal report data layer.

Cell optics come from the cell JSON; substrate from the substrate JSON.
Verifies the three computed quantities are physically sane.
"""
from pathlib import Path

import numpy as np
import pytest

from powerpy.loader.report import load_report_data
from powerpy.analysis.thermal_data import run_thermal_report, ThermalCase
from powerpy.schemas._common import Phase
from powerpy.schemas.fluxes import LaunchConfig

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "src" / "powerpy" / "param" / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"

pytestmark = pytest.mark.skipif(
    not PARAMS.exists(), reason="params.xlsx not present")


def _md():
    return load_report_data(PARAMS, DATA)


def test_thermal_report_quantities_sane():
    md = _md()
    cases = [
        ThermalCase("BOL", Phase.BOL_BC, LaunchConfig.SINGLE, season=1.034),
        ThermalCase("EOL", Phase.END_OF_LIFE, LaunchConfig.SINGLE, season=0.967),
    ]
    d = run_thermal_report(md, cases)

    # one equilibrium point per case, in a plausible GEO range
    assert len(d.points) == 2
    for p in d.points:
        assert -50.0 < p.t_front_c < 120.0
        assert p.p_elec_w > 0.0

    # inputs echo the cell JSON optics
    assert d.inputs["cell_alpha"] == pytest.approx(md.cell.electrical.alpha)
    assert d.inputs["cell_epsilon"] == pytest.approx(md.cell.electrical.epsilon)

    # the hot spot is hotter than a healthy cell, with a real gradient
    assert d.hotspot.failed_c > d.hotspot.nominal_c
    assert d.hotspot.delta_c > 0.0
    assert d.panel_grid_c.max() == pytest.approx(d.hotspot.failed_c, abs=0.5)
    assert d.panel_grid_c.min() < d.panel_grid_c.max()
