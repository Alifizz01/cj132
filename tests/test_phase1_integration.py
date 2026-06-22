from pathlib import Path

import numpy as np
import pytest

from powerpy.loader.report import load_report_data
from powerpy.schemas.panel_circuit import StringSpec, SectionSpec, PanelSpec, ArraySpec
from powerpy.simulation.spec_build import build_array_from_spec
from powerpy.simulation.cell_condition import CellCondition
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "src" / "powerpy" / "param" / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")

# Measured against the live params.xlsx cell (MEASURE step): one failed_open
# cell in a 2-string section -> ratio 0.50 (the sibling string keeps producing).
FAILED_RATIO_LO = 0.40
FAILED_RATIO_HI = 0.60


def _cell():
    return load_report_data(PARAMS, DATA).cell


def _two_string_spec():
    s1 = StringSpec(id="s1", members=(0, 1, 2))
    s2 = StringSpec(id="s2", members=(3, 4, 5))
    sec = SectionSpec(id="sec_a", strings=(s1, s2))
    return ArraySpec(name="spec", panels=(PanelSpec(id="panel_1", sections=(sec,)),))


def _single_string_spec():
    s1 = StringSpec(id="s1", members=(0, 1, 2))
    sec = SectionSpec(id="sec_a", strings=(s1,))
    return ArraySpec(name="one", panels=(PanelSpec(id="panel_1", sections=(sec,)),))


def _pmax(arr, env):
    arr.apply(env)
    v, i = arr.iv_curve()
    return float((v * i).max())


def test_shaded_cell_lowers_array_pmax():
    cell, spec, env = _cell(), _two_string_spec(), Environment(temperature_c=28.0)
    nominal = _pmax(build_array_from_spec(cell, spec), env)
    shaded = _pmax(build_array_from_spec(
        cell, spec, conditions={1: CellCondition(shade=0.4)}), env)
    assert shaded < nominal


def test_chipped_cell_lowers_string_current():
    cell, spec, env = _cell(), _two_string_spec(), Environment(temperature_c=28.0)
    nominal = _pmax(build_array_from_spec(cell, spec), env)
    chipped = _pmax(build_array_from_spec(
        cell, spec, conditions={4: CellCondition(life=0.6)}), env)
    assert chipped < nominal


def test_failed_open_isolates_string_without_collapsing_section():
    cell, env = _cell(), Environment(temperature_c=28.0)
    spec = _two_string_spec()
    nominal = _pmax(build_array_from_spec(cell, spec), env)

    failed = build_array_from_spec(
        cell, spec, conditions={0: CellCondition(state="failed_open")})
    p_failed = _pmax(failed, env)

    ratio = p_failed / nominal
    assert FAILED_RATIO_LO < ratio < FAILED_RATIO_HI

    # robust structural check: survivor ~ Pmax of a single healthy string alone
    one_string = _pmax(build_array_from_spec(cell, _single_string_spec()), env)
    assert p_failed == pytest.approx(one_string, rel=0.05)

    failed.apply(env)
    v, i = failed.iv_curve()
    assert np.all(np.isfinite(v)) and np.all(np.isfinite(i))


def test_array_apply_is_idempotent():
    cell, spec, env = _cell(), _two_string_spec(), Environment(temperature_c=28.0)
    arr = build_array_from_spec(cell, spec, conditions={1: CellCondition(shade=0.5)})
    arr.apply(env)
    v1, i1 = arr.iv_curve()
    arr.apply(env); arr.apply(env)
    v2, i2 = arr.iv_curve()
    assert np.allclose(v1, v2, rtol=0, atol=1e-12)
    assert np.allclose(i1, i2, rtol=0, atol=1e-12)
