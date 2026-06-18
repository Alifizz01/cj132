from pathlib import Path

import numpy as np
import pytest

from powerpy.loader.report import load_report_data
from powerpy.schemas.panel_circuit import StringSpec, SectionSpec, PanelSpec, ArraySpec
from powerpy.simulation.spec_build import build_array_from_spec
from powerpy.simulation.cell_condition import CellCondition
from powerpy.simulation.environment import Environment
from powerpy.simulation.percell_power import solve_percell_power

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def _cell():
    return load_report_data(PARAMS, DATA).cell


def _two_string_spec():
    s1 = StringSpec(id="s1", members=(0, 1, 2))
    s2 = StringSpec(id="s2", members=(3, 4, 5))
    sec = SectionSpec(id="sec_a", strings=(s1, s2))
    return ArraySpec(name="spec", panels=(PanelSpec(id="panel_1", sections=(sec,)),))


def _lossless_two_string_spec():
    # no block diode + no series resistance -> the per-cell power sum equals the
    # array terminal power at V* exactly (no diode/IR losses to account for).
    s1 = StringSpec(id="s1", members=(0, 1, 2), block_diode_v_drop=0.0)
    s2 = StringSpec(id="s2", members=(3, 4, 5), block_diode_v_drop=0.0)
    sec = SectionSpec(id="sec_a", strings=(s1, s2))
    return ArraySpec(name="spec", panels=(PanelSpec(id="panel_1", sections=(sec,)),))


def test_percell_power_keys_are_all_members():
    cell, spec, env = _cell(), _two_string_spec(), Environment(temperature_c=28.0)
    arr = build_array_from_spec(cell, spec)
    arr.apply(env)
    p = solve_percell_power(arr, spec)
    assert set(p.keys()) == set(spec.all_members())
    assert all(np.isfinite(v) for v in p.values())


def test_percell_power_energy_balance_at_mpp():
    """The per-cell powers must sum to the array power at the chosen V* (MPP).

    Uses a lossless spec (no block diode, no series R) so the energy-balance
    gate is exact: forward cell power has nowhere to go but the terminal.
    """
    cell, spec, env = _cell(), _lossless_two_string_spec(), Environment(temperature_c=28.0)
    arr = build_array_from_spec(cell, spec)
    arr.apply(env)
    p = solve_percell_power(arr, spec)

    v_mp, i_mp, p_mp = arr.calc_mp()
    total = sum(p.values())
    # within tolerance of the array MPP power (resampling/interp tolerance)
    assert total == pytest.approx(p_mp, rel=0.02)


def test_percell_power_accounts_for_block_diode_losses():
    """With block diodes the cell-power sum exceeds the array terminal power by
    exactly the block-diode dissipation (0.6 V * string current, per string)."""
    cell, spec, env = _cell(), _two_string_spec(), Environment(temperature_c=28.0)
    arr = build_array_from_spec(cell, spec)
    arr.apply(env)
    p = solve_percell_power(arr, spec)

    v_mp, i_mp, p_mp = arr.calc_mp()
    section = list(arr.iter_sections())[0]
    # diode loss = sum over strings of (n_block * v_drop * I_string at V*)
    v_node = v_mp + section.current_at_voltage(v_mp) * section.section_resistance_ohm
    diode_loss = sum(
        st.n_block_diodes * st.block_diode_v_drop * st.current_at_voltage(v_node)
        for st in section.strings)
    assert sum(p.values()) == pytest.approx(p_mp + diode_loss, rel=0.02)


def test_percell_power_healthy_cells_roughly_equal():
    cell, spec, env = _cell(), _two_string_spec(), Environment(temperature_c=28.0)
    arr = build_array_from_spec(cell, spec)
    arr.apply(env)
    p = solve_percell_power(arr, spec)
    vals = list(p.values())
    # all healthy + identical -> each cell carries about the same forward power
    assert max(vals) == pytest.approx(min(vals), rel=0.05)
    assert min(vals) > 0.0


def test_percell_power_shaded_cell_carries_less():
    cell, spec, env = _cell(), _two_string_spec(), Environment(temperature_c=28.0)
    arr = build_array_from_spec(cell, spec, conditions={1: CellCondition(shade=0.4)})
    arr.apply(env)
    p = solve_percell_power(arr, spec)
    # the shaded cell (tile 1) limits its own string's current -> lower power
    # than a healthy cell in the unshaded sibling string (tile 3)
    assert p[1] < p[3]
