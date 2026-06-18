from pathlib import Path

import numpy as np
import pytest

from powerpy.loader.report import load_report_data
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.cell_condition import CellCondition
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def _params():
    return load_report_data(PARAMS, DATA).cell


def test_default_condition_is_unchanged_operating_points():
    p = _params()
    env = Environment(temperature_c=28.0)
    a = CellModel(p)
    b = CellModel(p, condition=CellCondition())
    a.apply(env); b.apply(env)
    assert a.operating_points() == b.operating_points()


def test_shaded_cell_lowers_isc():
    p = _params()
    env = Environment(temperature_c=28.0)
    healthy = CellModel(p)
    shaded = CellModel(p, condition=CellCondition(shade=0.5))
    healthy.apply(env); shaded.apply(env)
    isc_h = healthy.operating_points()[0]
    isc_s = shaded.operating_points()[0]
    assert isc_s == pytest.approx(0.5 * isc_h, rel=1e-9)


def test_imp_factor_lowers_isc():
    p = _params()
    env = Environment(temperature_c=28.0)
    healthy = CellModel(p)
    variant = CellModel(p, condition=CellCondition(imp_factor=0.9))
    healthy.apply(env); variant.apply(env)
    isc_h = healthy.operating_points()[0]
    isc_v = variant.operating_points()[0]
    assert isc_v == pytest.approx(0.9 * isc_h, rel=1e-9)


def test_pmax_factor_lowers_peak_power():
    p = _params()
    env = Environment(temperature_c=28.0)
    healthy = CellModel(p)
    variant = CellModel(p, condition=CellCondition(pmax_factor=0.8))
    healthy.apply(env); variant.apply(env)
    isc_h, imp_h, vmp_h, voc_h = healthy.operating_points()
    isc_v, imp_v, vmp_v, voc_v = variant.operating_points()
    assert (imp_v * vmp_v) == pytest.approx(0.8 * imp_h * vmp_h, rel=1e-9)


def test_apply_is_idempotent():
    p = _params()
    env = Environment(temperature_c=28.0)
    c = CellModel(p, condition=CellCondition(shade=0.5, life=0.8))
    c.apply(env)
    op_once = c.operating_points()
    c.apply(env); c.apply(env)
    op_thrice = c.operating_points()
    assert op_once == op_thrice
    v1, i1 = c.iv_curve()
    c.apply(env)
    v2, i2 = c.iv_curve()
    assert np.allclose(v1, v2, rtol=0, atol=1e-12)
    assert np.allclose(i1, i2, rtol=0, atol=1e-12)
