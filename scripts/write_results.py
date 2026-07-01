"""Electrical analysis -> results.xlsx (no PDF).  CLI, reads params.xlsx.

Build the array from a topology (blocks / parallel / series) OR a layout JSON,
take the cell config + per-cell condition layers from params.xlsx, solve the
ELECTRICAL operating point, and write a results workbook (array / strings /
cells).  No temperature, no PDF.

Run (from project root):
    python scripts/write_results.py --blocks 1 --parallel 4 --series 10 --no-report
    python scripts/write_results.py --layout src/powerpy/data/layouts/simple_3block.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import numpy as np
from powerpy.config.layout import load_layout, panel_from_topology
from powerpy.loader.cell import load_cell_parameters
from powerpy.loader.condition_layers import load_condition_layers
from powerpy.loader.sim_config import read_topology, resolve_layout
from powerpy.loader.workbooks import find_workbooks
from powerpy.output.excel import write_results_xlsx
from powerpy.simulation.spec_adapt import adapt_grid
from powerpy.simulation.spec_build import build_array_from_spec
from powerpy.simulation.environment import Environment
from powerpy.simulation.cell_condition import CellCondition, sample_manufacturing_variance


def _voltage_at_current(curve, i):
    vv, ii = curve
    return float(np.interp(i, ii[::-1], vv[::-1]))


def analyse(cell, layout, conditions, env):
    spec = adapt_grid(layout)
    arr = build_array_from_spec(cell, spec, conditions=conditions)
    arr.apply(env)
    v_star, i_mp, p_mp = arr.calc_mp()
    va, ia = arr.iv_curve()
    isc = float(np.interp(0.0, va, ia))
    voc = float(np.interp(0.0, ia[::-1], va[::-1]))

    nom = build_array_from_spec(cell, spec); nom.apply(env)
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


# the writer lives in the output package now; kept name for callers/tests
write_xlsx = write_results_xlsx


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--layout", default=None, help="layout JSON (overrides the 'panel' sheet).")
    p.add_argument("--parallel", type=int, default=None,
                   help="strings in parallel (with --series/--blocks); overrides the 'panel' sheet.")
    p.add_argument("--series", type=int, default=None, help="cells in series per string.")
    p.add_argument("--blocks", type=int, default=1, help="number of blocks (default 1).")
    p.add_argument("--irradiance", type=float, default=None,
                   help="global sun level (1.0 = full); overrides the 'panel' sheet.")
    p.add_argument("--params", default=str(_ROOT / "src" / "powerpy" / "param" / "params.xlsx"),
                   help="LEGACY single workbook: cell config + 'panel' sheet + "
                        "condition layers (default src/powerpy/param/params.xlsx). "
                        "Ignored when --design/--scenario are given.")
    p.add_argument("--design", default=None,
                   help="design workbook (cell_params + topology/panel sheet).")
    p.add_argument("--scenario", default=None,
                   help="scenario workbook (layer_* condition sheets).")
    p.add_argument("--out", default="results.xlsx", help="output workbook (default results.xlsx).")
    p.add_argument("--no-report", action="store_true",
                   help="skip the PDF report; write only the Excel results.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = _parse_args(argv)
    if a.design or a.scenario:
        wbs = find_workbooks(design=a.design, scenario=a.scenario)
    else:
        wbs = find_workbooks(legacy_params=a.params)
    imp_sigma = pmax_sigma = 0.0
    seed = 0
    if a.layout:
        layout = load_layout(a.layout)
        irradiance = a.irradiance if a.irradiance is not None else 1.0
    elif a.parallel is not None:
        if a.series is None:
            raise SystemExit("--parallel requires --series (and optional --blocks)")
        layout = panel_from_topology(n_blocks=a.blocks, n_parallel=a.parallel, n_series=a.series)
        irradiance = a.irradiance if a.irradiance is not None else 1.0
    else:
        cfg = read_topology(wbs.design)        # 'topology' sheet ('panel' fallback)
        layout = resolve_layout(cfg, base_dir=wbs.design.parent)
        irradiance = a.irradiance if a.irradiance is not None else cfg["irradiance"]
        imp_sigma, pmax_sigma, seed = cfg["imp_sigma"], cfg["pmax_sigma"], cfg["variance_seed"]

    NR, NC = layout.n_rows, layout.n_cols
    # cell config straight from the design workbook -- no report metadata needed
    cell = load_cell_parameters(wbs.design, _ROOT / "src" / "powerpy" / "data")

    # per-cell conditions from the scenario workbook's layer sheets (if they fit)
    try:
        conditions = load_condition_layers(wbs.scenario, n_rows=NR, n_cols=NC)
        n_cond = sum(1 for v in conditions.values()
                     if v.state != "healthy" or v.shade != 1.0 or v.life != 1.0)
        cond_msg = "%d non-default cell(s)" % n_cond
    except ValueError:
        conditions = {}
        cond_msg = ("layers don't match this %dx%d grid -> all-healthy "
                    "(run setup_sim.py to add matching layers)" % (NR, NC))

    # manufacturing variance (default sigma 0 = no-op)
    if imp_sigma or pmax_sigma:
        keys = list(range(NR * NC))
        clist = sample_manufacturing_variance(
            [conditions.get(k, CellCondition()) for k in keys],
            seed=seed, imp_sigma=imp_sigma, pmax_sigma=pmax_sigma)
        conditions = dict(zip(keys, clist))

    # global irradiance rides the current axis (analytic operating_points reads current_loss)
    env = Environment(temperature_c=28.0, season=irradiance, current_loss=irradiance)

    summary, strings, cells = analyse(cell, layout, conditions, env)
    write_xlsx(Path(a.out), layout.name, summary, strings, cells)

    print("layout     : %s  (%d x %d = %d cells)" % (layout.name, NR, NC, NR * NC))
    print("irradiance : %.3f (global)   conditions: %s" % (irradiance, cond_msg))
    if imp_sigma or pmax_sigma:
        print("variance   : imp_sigma=%.4g  pmax_sigma=%.4g  seed=%d" % (imp_sigma, pmax_sigma, seed))
    print("ARRAY  Pmpp=%(Pmpp_W)s W  Vmpp=%(Vmpp_V)s V  Impp=%(Impp_A)s A  "
          "Isc=%(Isc_A)s A  Voc=%(Voc_V)s V" % summary)
    print("LOSS   %(loss_W)s W  (%(loss_pct)s%% vs nominal %(Pnom_W)s W)" % summary)
    if a.no_report:
        print("report : PDF skipped (--no-report); Excel only")
    print("wrote  : %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
