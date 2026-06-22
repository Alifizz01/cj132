"""Absolute-sanity guard for the per-cell thermal path.

Relative checks ("shaded < healthy") pass even when the absolute temperatures
diverge; this asserts the healthy-panel temperatures are physically plausible,
which catches the cell-area/energy-balance bug.
"""
from pathlib import Path

import numpy as np
import pytest

from powerpy.config.layout import load_layout
from powerpy.loader.report import load_report_data
from powerpy.simulation.spec_adapt import adapt_grid
from powerpy.simulation.percell_power import solve_panel_percell
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "src" / "powerpy" / "param" / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
LAYOUT = DATA / "layouts" / "simple_3block.json"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def test_healthy_panel_temperatures_are_physical():
    cell = load_report_data(PARAMS, DATA).cell
    lay = load_layout(str(LAYOUT))
    spec = adapt_grid(lay)
    res, pe = solve_panel_percell(
        cell, spec, lay, p_sun=1367.0, env=Environment(temperature_c=28.0))
    T = np.asarray(res.t_front_c).ravel()
    # every healthy cell must land in a sane sun-facing range, not diverge
    assert np.all(T > -120.0) and np.all(T < 200.0), f"diverged: {T.min()}..{T.max()}"
