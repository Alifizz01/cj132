from pathlib import Path

import numpy as np
import pytest

from powerpy.loader.report import load_report_data
from powerpy.schemas.panel_circuit import StringSpec, SectionSpec, PanelSpec, ArraySpec
from powerpy.simulation.spec_build import build_array_from_spec
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def _cell():
    return load_report_data(PARAMS, DATA).cell


def _spec():
    # two parallel strings of 3 cells each -> tiles 0..5
    s1 = StringSpec(id="s1", members=(0, 1, 2))
    s2 = StringSpec(id="s2", members=(3, 4, 5))
    sec = SectionSpec(id="sec_a", strings=(s1, s2))
    return ArraySpec(name="spec", panels=(PanelSpec(id="panel_1", sections=(sec,)),))


def test_spec_build_makes_distinct_cells_per_member():
    arr = build_array_from_spec(_cell(), _spec(), iv_engine="analytic")
    assert len(arr.panels) == 1
    secs = list(arr.iter_sections())
    assert len(secs) == 1
    s1, s2 = secs[0].strings
    assert len(s1.cells) == 3 and len(s2.cells) == 3
    objs = [id(c) for c in s1.cells] + [id(c) for c in s2.cells]
    assert len(set(objs)) == 6


def test_spec_build_curve_is_finite_with_positive_peak():
    arr = build_array_from_spec(_cell(), _spec(), iv_engine="analytic")
    arr.apply(Environment(temperature_c=28.0))
    v, i = arr.iv_curve()
    p = v * i
    assert np.all(np.isfinite(v)) and np.all(np.isfinite(i))
    assert float(p.max()) > 0.0
