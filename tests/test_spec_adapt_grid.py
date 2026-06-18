from pathlib import Path

import numpy as np
import pytest

from powerpy.config.layout import panel_from_topology
from powerpy.loader.report import load_report_data
from powerpy.schemas.panel_circuit import validate_bijection
from powerpy.simulation.spec_adapt import adapt_grid
from powerpy.simulation.spec_build import build_array_from_spec
from powerpy.simulation.string_level import StringModel
from powerpy.simulation.section_level import SectionModel
from powerpy.simulation.panel_level import PanelModel
from powerpy.simulation.array_level import ArrayModel
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def _cell():
    return load_report_data(PARAMS, DATA).cell


def test_adapt_grid_is_a_bijection():
    lay = panel_from_topology(n_blocks=1, n_parallel=2, n_series=3)
    spec = adapt_grid(lay)
    validate_bijection(spec, lay.n_tiles)   # no raise


def test_adapt_grid_matches_hand_built_tree_structurally():
    cell = _cell()
    lay = panel_from_topology(n_blocks=1, n_parallel=2, n_series=3)
    env = Environment(temperature_c=28.0)

    spec = adapt_grid(lay)
    arr_spec = build_array_from_spec(cell, spec, iv_engine="analytic")
    arr_spec.apply(env)
    v_spec, i_spec = arr_spec.iv_curve()

    strings = []
    for s in range(2):
        cells = [CellModel(cell, iv_engine="analytic") for _ in range(3)]
        strings.append(StringModel.from_cells(cells, name="ref.s%d" % s))
    sec = SectionModel.from_strings(strings, name="sec_grid")
    pan = PanelModel.from_sections([sec], name="panel_1")
    arr_ref = ArrayModel.from_panels([pan], name="grid")
    arr_ref.apply(env)
    v_ref, i_ref = arr_ref.iv_curve()

    assert np.allclose(v_spec, v_ref, rtol=0, atol=1e-9)
    assert np.allclose(i_spec, i_ref, rtol=0, atol=1e-9)


def test_adapt_grid_raises_on_untagged_tile():
    lay = panel_from_topology(n_blocks=1, n_parallel=2, n_series=3)
    key = lay.flat_keys()[0]
    import dataclasses
    bad_tile = dataclasses.replace(lay.palette[key], string=None)
    bad_palette = dict(lay.palette)
    bad_palette[key] = bad_tile
    bad_lay = dataclasses.replace(lay, palette=bad_palette)
    with pytest.raises(ValueError):
        adapt_grid(bad_lay)
