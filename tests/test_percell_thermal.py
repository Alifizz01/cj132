from pathlib import Path

import numpy as np
import pytest

from powerpy.config.layout import panel_from_topology
from powerpy.loader.report import load_report_data
from powerpy.simulation.spec_adapt import adapt_grid
from powerpy.simulation.spec_build import build_array_from_spec
from powerpy.simulation.cell_condition import CellCondition
from powerpy.simulation.environment import Environment
from powerpy.simulation.percell_power import (
    solve_percell_power, percell_power_array, solve_panel_percell,
)

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "src" / "powerpy" / "param" / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def _cell():
    return load_report_data(PARAMS, DATA).cell


def _grid():
    # 2 parallel strings x 3 series cells -> 6 tiles, fully tagged
    return panel_from_topology(n_blocks=1, n_parallel=2, n_series=3)


def test_percell_power_array_is_indexed_by_k():
    cell, lay = _cell(), _grid()
    spec = adapt_grid(lay)
    arr = build_array_from_spec(cell, spec)
    arr.apply(Environment(temperature_c=28.0))
    p_map = solve_percell_power(arr, spec)
    pe = percell_power_array(p_map, lay.n_tiles)
    assert pe.shape == (lay.n_tiles,)
    for k, val in p_map.items():
        assert pe[k] == pytest.approx(val)


def test_solve_panel_percell_runs_glat0_and_returns_grid():
    cell, lay = _cell(), _grid()
    spec = adapt_grid(lay)
    res, pe = solve_panel_percell(
        cell, spec, lay, p_sun=1367.0,
        env=Environment(temperature_c=28.0))
    assert res.t_front_c.shape == (lay.n_rows, lay.n_cols)
    assert res.g_lat == 0.0
    assert np.all(np.isfinite(res.t_front_c))


def test_shaded_cell_runs_cooler_than_healthy_neighbours():
    """A shaded cell loses front solar (and electrical term) -> cooler tile."""
    cell, lay = _cell(), _grid()
    spec = adapt_grid(lay)
    # shade tile 1 (middle of first string)
    res, pe = solve_panel_percell(
        cell, spec, lay, p_sun=1367.0,
        env=Environment(temperature_c=28.0),
        conditions={1: CellCondition(shade=0.3)})
    t = res.t_front_c.flatten()
    # tile 1 is shaded -> cooler than a healthy tile in the other string (tile 3)
    assert t[1] < t[3]


def test_failed_open_sibling_cells_unaffected_glat0():
    """With g_lat=0 a failed_open cell's grid neighbours keep their temperature
    (independent per-cell solve)."""
    cell, lay = _cell(), _grid()
    spec = adapt_grid(lay)
    # baseline: all healthy
    _res0, _pe0 = solve_panel_percell(
        cell, spec, lay, p_sun=1367.0, env=Environment(temperature_c=28.0))
    res_h = _res0.t_front_c.flatten()

    # fail tile 0; tile 3 is in the other (independent) string
    res, pe = solve_panel_percell(
        cell, spec, lay, p_sun=1367.0, env=Environment(temperature_c=28.0),
        conditions={0: CellCondition(state="failed_open")})
    t = res.t_front_c.flatten()
    # sibling/neighbour tiles unchanged to high precision (no lateral coupling
    # and the same front solar) -- only tile 0's electrical term shifts
    assert t[3] == pytest.approx(res_h[3], abs=1e-6)
