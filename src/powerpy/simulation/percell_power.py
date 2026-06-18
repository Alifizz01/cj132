"""Per-cell FORWARD power back-propagation solver (approach B, Phase 2).

Given a built :class:`~powerpy.simulation.array_level.ArrayModel` (from
:func:`~powerpy.simulation.spec_build.build_array_from_spec`) at its operating
point, recover the FORWARD electrical power each tile carries, keyed by the flat
tile index ``k`` from the originating :class:`~powerpy.schemas.panel_circuit.ArraySpec`.

This is a real recursive back-propagation, NOT a reader: ``combine_series`` /
``combine_parallel`` discard per-cell correspondence, so we re-derive each
child's operating point by inverting its own cached curve at the shared node
voltage (parallel: split V down) or shared node current (series: share I up).

Scope (LOCKED for Phase 2):
  * FORWARD power only.  ``single_diode_iv`` spans ``[0, Voc]`` and clips
    ``I >= 0``; a cell driven into reverse bias has no curve data there, so its
    forward power simply reads ~0 at the operating point.  Reverse-bias
    dissipation stays out of scope (the ``make_pe`` heuristic remains the
    default fast path for hotspot studies).
  * The chosen operating point is the ARRAY maximum-power point (V*).

The per-cell powers are gated to sum to the array power at V* (energy balance);
:func:`solve_percell_power` itself does not assert, but the value is exposed so
callers/tests can verify the gate.
"""
from __future__ import annotations

import numpy as np

from powerpy.schemas.panel_circuit import ArraySpec
from powerpy.simulation.array_level import ArrayModel


def _current_at_voltage(curve, v: float) -> float:
    """Current a child curve sources at terminal voltage ``v``."""
    vv, ii = curve
    return float(np.interp(v, vv, ii))


def _voltage_at_current(curve, i: float) -> float:
    """Voltage a series child develops at shared current ``i``.

    The curve's current is descending (Isc -> 0 at Voc), so reverse both for an
    ascending x-axis before interpolating.  Outside ``[0, Isc]`` ``np.interp``
    clamps to the endpoints (a cell forced beyond its own Isc reads ~0 V).
    """
    vv, ii = curve
    return float(np.interp(i, ii[::-1], vv[::-1]))


def solve_percell_power(array: ArrayModel, spec: ArraySpec,
                        *, v_star: float | None = None) -> dict[int, float]:
    """Per-cell FORWARD power keyed by tile index ``k``.

    ``array`` MUST already have had ``apply(env)`` called (so every cached
    ``iv_curve`` reflects the operating environment).  ``spec`` provides the
    tile-index members in the SAME tree order ``build_array_from_spec`` used.

    ``v_star`` is the array terminal (bus) voltage to back-propagate from;
    defaults to the array maximum-power-point voltage.
    """
    if v_star is None:
        v_star, _i_mp, _p_mp = array.calc_mp()

    power: dict[int, float] = {}

    # Array -> panels (parallel): every panel sees the bus voltage V*.
    for panel, pan_spec in zip(array.panels, spec.panels):
        _solve_panel(panel, pan_spec, v_star, power)
    return power


def _solve_panel(panel, pan_spec, v_terminal: float, power: dict) -> None:
    # Panel -> sections (parallel): every section sees the panel voltage.
    for section, sec_spec in zip(panel.sections, pan_spec.sections):
        _solve_section(section, sec_spec, v_terminal, power)


def _solve_section(section, sec_spec, v_terminal: float, power: dict) -> None:
    # The section applies v_out = v_node - I_sec * R_sec.  At section terminal
    # voltage v_terminal the internal string-parallel node sits at
    #   v_node = v_terminal + I_sec * R_sec.
    i_sec = section.current_at_voltage(v_terminal)
    v_node = v_terminal + i_sec * section.section_resistance_ohm
    # Strings in parallel share v_node.
    for string, st_spec in zip(section.strings, sec_spec.strings):
        _solve_string(string, st_spec, v_node, power)


def _solve_string(string, st_spec, v_node: float, power: dict) -> None:
    # The string terminal curve is the raw series stack shifted down by the
    # block-diode drop and the I*Rseries drop.  At string terminal voltage
    # v_node the string sources current I_s; the internal series stack carries
    # the SAME I_s (series), so we read each cell's voltage at I_s directly.
    i_s = string.current_at_voltage(v_node)
    for cell, k in zip(string.cells, st_spec.members):
        v_cell = _voltage_at_current(cell.iv_curve(), i_s)
        power[int(k)] = v_cell * i_s
