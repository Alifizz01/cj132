"""Use case B's electrical operating-point breakdown.

Solve the array MPP under per-cell conditions, then walk back down the tree to
report every string's and every cell's operating point -- the numbers behind
``results.xlsx`` (summary / strings / cells). Moved verbatim from
scripts/write_results.py (P4); the numbers are pinned by the analyse byte gate.
"""
from __future__ import annotations

import numpy as np

from powerpy.simulation.cell_condition import CellCondition
from powerpy.simulation.spec_adapt import adapt_grid
from powerpy.simulation.spec_build import build_array_from_spec


def _voltage_at_current(curve, i):
    vv, ii = curve
    return float(np.interp(i, ii[::-1], vv[::-1]))


def analyse_operating_point(cell, layout, conditions, env):
    """Return ``(summary, strings, cells)`` for one conditioned run.

    ``summary`` -- array MPP / Isc / Voc plus the loss vs an unconditioned
    nominal build; ``strings`` -- (id, I, node V, P) per string; ``cells`` --
    (k, string, state, shade, life, V, I, P) per cell at the array MPP.
    """
    spec = adapt_grid(layout)
    arr = build_array_from_spec(cell, spec, conditions=conditions)
    arr.apply(env)
    v_star, i_mp, p_mp = arr.calc_mp()
    va, ia = arr.iv_curve()
    isc = float(np.interp(0.0, va, ia))
    voc = float(np.interp(0.0, ia[::-1], va[::-1]))

    nom = build_array_from_spec(cell, spec)
    nom.apply(env)
    _, _, p_nom = nom.calc_mp()

    strings, cells = [], []
    for panel, pan_spec in zip(arr.panels, spec.panels):
        for section, sec_spec in zip(panel.sections, pan_spec.sections):
            i_sec = section.current_at_voltage(v_star)
            v_node = v_star + i_sec * section.section_resistance_ohm
            for string, st_spec in zip(section.strings, sec_spec.strings):
                i_s = string.current_at_voltage(v_node)
                p_string = 0.0
                for c, k in zip(string.cells, st_spec.members):
                    v_cell = _voltage_at_current(c.iv_curve(), i_s)
                    p_cell = v_cell * i_s
                    p_string += p_cell
                    cd = conditions.get(k, CellCondition())
                    cells.append((int(k), st_spec.id, cd.state, cd.shade, cd.life,
                                  round(v_cell, 4), round(i_s, 4), round(p_cell, 4)))
                strings.append((st_spec.id, round(i_s, 4), round(v_node, 4),
                                round(p_string, 4)))
    summary = dict(Pmpp_W=round(p_mp, 3), Vmpp_V=round(v_star, 3), Impp_A=round(i_mp, 4),
                   Isc_A=round(isc, 4), Voc_V=round(voc, 3), Pnom_W=round(p_nom, 3),
                   loss_W=round(p_mp - p_nom, 3),
                   loss_pct=round(100 * (p_mp - p_nom) / p_nom, 2) if p_nom else 0.0)
    return summary, strings, cells
