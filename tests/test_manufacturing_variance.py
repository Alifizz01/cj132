import pytest

from powerpy.simulation.cell_condition import (
    CellCondition, sample_manufacturing_variance, resolve_cell_env,
)
from powerpy.simulation.environment import Environment


def test_default_sigma_is_strict_noop():
    conds = [CellCondition() for _ in range(5)]
    out = sample_manufacturing_variance(conds, seed=0)   # sigmas default to 0
    assert out == conds
    assert all(c.imp_factor == 1.0 and c.pmax_factor == 1.0 for c in out)


def test_sampler_is_deterministic_per_seed():
    conds = [CellCondition() for _ in range(8)]
    a = sample_manufacturing_variance(conds, seed=42, imp_sigma=0.02, pmax_sigma=0.03)
    b = sample_manufacturing_variance(conds, seed=42, imp_sigma=0.02, pmax_sigma=0.03)
    assert [c.imp_factor for c in a] == [c.imp_factor for c in b]
    assert [c.pmax_factor for c in a] == [c.pmax_factor for c in b]


def test_sampler_varies_with_sigma_and_stays_positive():
    conds = [CellCondition() for _ in range(50)]
    out = sample_manufacturing_variance(conds, seed=1, imp_sigma=0.05, pmax_sigma=0.05)
    imps = [c.imp_factor for c in out]
    assert len(set(imps)) > 1
    assert all(c.imp_factor > 0 and c.pmax_factor > 0 for c in out)


def test_sampled_factor_actually_moves_the_env():
    conds = [CellCondition() for _ in range(20)]
    out = sample_manufacturing_variance(conds, seed=7, imp_sigma=0.1)
    base = Environment(season=1.0, current_loss=1.0, voltage_loss=1.0)
    moved = next(c for c in out if c.imp_factor != 1.0)
    env = resolve_cell_env(moved, base)
    assert env.current_loss == pytest.approx(moved.imp_factor)
