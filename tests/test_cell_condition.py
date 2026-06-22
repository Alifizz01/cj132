import dataclasses
import math

import pytest

from powerpy.simulation.cell_condition import CellCondition, resolve_cell_env
from powerpy.simulation.environment import Environment


def test_condition_defaults_are_a_noop():
    cond = CellCondition()
    base = Environment(temperature_c=28.0, season=1.0, current_loss=1.0)
    out = resolve_cell_env(cond, base)
    assert out.season == 1.0
    assert out.current_loss == 1.0
    assert out.voltage_loss == base.voltage_loss
    assert out.temperature_c == 28.0


def test_condition_validation():
    with pytest.raises(ValueError):
        CellCondition(state="failed_short")
    with pytest.raises(ValueError):
        CellCondition(shade=1.5)
    with pytest.raises(ValueError):
        CellCondition(imp_factor=0.0)
    with pytest.raises(ValueError):
        CellCondition(pmax_factor=0.0)


def test_shade_life_incidence_lower_current_loss():
    cond = CellCondition(shade=0.5, life=0.8, incidence=0.9)
    base = Environment(season=1.0, current_loss=1.0)
    out = resolve_cell_env(cond, base)
    # life rides current_loss; shade/incidence ride season (each current-axis
    # knob applied once, since operating_points multiplies current_loss*season).
    assert out.current_loss == pytest.approx(1.0 * 0.8)
    assert out.season == pytest.approx(1.0 * 0.5 * 0.9)
    # net current-axis factor is the full shade*life*incidence product
    assert out.current_loss * out.season == pytest.approx(1.0 * 0.8 * 0.5 * 0.9)


def test_imp_factor_scales_current_axis_only():
    cond = CellCondition(imp_factor=0.95)
    base = Environment(season=1.0, current_loss=1.0, voltage_loss=1.0)
    out = resolve_cell_env(cond, base)
    assert out.current_loss == pytest.approx(0.95)
    assert out.voltage_loss == pytest.approx(1.0)


def test_pmax_factor_splits_across_both_axes():
    cond = CellCondition(pmax_factor=0.81)
    base = Environment(season=1.0, current_loss=1.0, voltage_loss=1.0)
    out = resolve_cell_env(cond, base)
    assert out.current_loss == pytest.approx(math.sqrt(0.81))
    assert out.voltage_loss == pytest.approx(math.sqrt(0.81))


def test_failed_open_uses_tiny_current_loss_and_season_not_zero():
    cond = CellCondition(state="failed_open")
    base = Environment(season=1.0, current_loss=1.0)
    out = resolve_cell_env(cond, base)
    # epsilon rides season (a single current-axis knob); current_loss is left
    # untouched.  Net current-axis factor (current_loss*season) is tiny but >0.
    assert 0.0 < out.season <= cond.failed_open_epsilon
    assert out.current_loss == pytest.approx(base.current_loss)
    assert 0.0 < out.current_loss * out.season <= cond.failed_open_epsilon


def test_resolve_is_pure_and_idempotent():
    cond = CellCondition(shade=0.5, life=0.7)
    base = Environment(season=1.0, current_loss=1.0)
    base_snapshot = dataclasses.asdict(base)
    cond_snapshot = dataclasses.asdict(cond)
    out1 = resolve_cell_env(cond, base)
    out2 = resolve_cell_env(cond, base)
    assert out1 == out2
    assert dataclasses.asdict(base) == base_snapshot
    assert dataclasses.asdict(cond) == cond_snapshot
