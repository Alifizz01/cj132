# -*- coding: utf-8 -*-
"""Generate the PowerPy Cookbook -- 50 grounded use cases -> self-contained HTML.

Each use case: title, "best for" note, runnable Python (and CLI where it
applies), plus a short note. No practice/questions -- pure examples.
"""
import html
from pathlib import Path

HERE = Path(__file__).resolve().parent

# (number, category, title, best_for, code, cli, note)
# code/cli are plain text; note is short prose.
UC = []


def add(cat, title, best, code, note, cli=None):
    UC.append((cat, title, best, code.strip("\n"), cli, note))


# ============================================================ A. Setup & loading
add("Setup & loading", "Load the whole workbook into one object",
    "The starting point for every script: turn params.xlsx + the cell/substrate JSONs into a typed, validated ReportMetadata.",
    """
import sys; sys.path.insert(0, "src")          # run from source, no pip
from pathlib import Path
from powerpy.loader.report import load_report_data

md = load_report_data(Path("params.xlsx"), Path("src/powerpy/data"))
print(md.document.doc_number, md.cell.name, len(md.array_layout.physical_sections))
""",
    "Everything downstream (analysis, reports) takes this `md`. Loading fails LOUD on a bad sheet, so a clean load means the workbook is internally consistent.")

add("Setup & loading", "Run with zero installation (locked-down laptop)",
    "Best when you cannot pip install: the framework runs straight from src/.",
    """
# run.py at the repo root already does this:
import sys; sys.path.insert(0, "src")
from powerpy.app import main
main()                                          # dispatches the CLI
""",
    "No build step, no site-packages. The only optional native piece is the vendored ngspice; the framework runs fully without it.")

add("Setup & loading", "Inspect the loaded cell / mission / layout data",
    "Sanity-check what the workbook actually contains before you analyse.",
    """
e = md.cell.electrical
print("Isc", e.isc_bol, "Voc", e.voc_bol, "alpha", e.alpha, "area_m2", e.area_m2)
print("sections", md.array_layout.topology.n_wings, "wings x",
      md.array_layout.topology.n_panels_per_wing, "panels")
for s in md.array_layout.physical_sections[:3]:
    print(s.instance_id, s.resistance_ohm, "ohm")
""",
    "The schema is frozen and self-documenting -- field names carry units (e.g. `area_m2`, `resistance_ohm`).")

add("Setup & loading", "Validate a workbook on purpose",
    "Use in CI or before a long run: confirm the workbook loads and the physics invariants hold.",
    """
try:
    md = load_report_data(Path("params.xlsx"), Path("src/powerpy/data"))
    print("OK: workbook valid")
except ValueError as exc:
    print("INVALID:", exc)                      # e.g. 'sections: none included'
""",
    "Guards fire loudly: a sheet that filters to zero rows, a missing required document field, or an impossible cell value (negative area, alpha>1) all raise with the sheet/row named.")

# ============================================================ B. Cell-level IV
add("Cell-level IV", "One cell's I-V / P-V at an operating point",
    "The leaf of the model: how a single SCA behaves at a given temperature, dose and loss.",
    """
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.environment import Environment

cell = CellModel(md.cell)
cell.apply(Environment(temperature_c=51.1, dose_i=246.0, dose_v=511.0,
                       current_loss=0.94, voltage_loss=0.97))
v, i = cell.iv_curve()
print("Voc", v[-1], "Isc", i[0], "Pmax", (v * i).max())
""",
    "`Environment` is one operating point. Dose is in 1e14 e/cm^2; losses are pre-multiplied factors in (0,1].")

add("Cell-level IV", "Build the single-diode curve directly",
    "When you just want the analytic curve from four datasheet points, no schema.",
    """
from powerpy.simulation.cell_level import fit_rseries, single_diode_iv

params = fit_rseries(isc=1.231, imp=1.184, vmp=2.375, voc=2.679)
v, i = single_diode_iv(params, step=0.01)
print(params.rs, params.i0, params.vt)          # series R, sat current, n*kT/q
""",
    "`fit_rseries` is a closed-form fit; `single_diode_iv` solves I(V) with a vectorised Newton step. Pure numpy -- no ngspice.")

add("Cell-level IV", "Operating points (Isc/Imp/Vmp/Voc) at any environment",
    "Best for tabulating how a cell degrades with temperature and radiation.",
    """
cell.apply(Environment())                       # BOL, 28 C
print("BOL", cell.operating_points())
cell.apply(Environment(temperature_c=60, dose_i=1000))
print("hot+irradiated", cell.operating_points())
""",
    "Applies temperature coefficients, the radiation remaining-factors and the loss products to the begin-of-life points.")

add("Cell-level IV", "Compare a BOL vs EOL cell side by side",
    "Quantify end-of-life power loss for one cell.",
    """
import numpy as np
def mpp(env):
    cell.apply(env); v, i = cell.iv_curve(); return float((v*i).max())

bol = mpp(Environment())
eol = mpp(Environment(temperature_c=51.1, dose_i=246, dose_v=511,
                      current_loss=0.94, voltage_loss=0.97))
print(f"BOL {bol:.2f} W -> EOL {eol:.2f} W  ({100*(1-eol/bol):.0f}% loss)")
""",
    "A one-cell answer scales to the array because series/parallel composition is linear in count.")

add("Cell-level IV", "Switch the I-V engine: analytic vs vendored ngspice",
    "Use ngspice on the office laptop (real SPICE); analytic everywhere else -- same code.",
    """
cell_a = CellModel(md.cell, iv_engine="analytic")   # default, no ngspice
cell_n = CellModel(md.cell, iv_engine="ngspice")    # real SPICE if vendored,
                                                    # else auto-falls back
""",
    "`iv_engine='ngspice'` warns ONCE and falls back to analytic if the ngspice vendor (psp/ + DLLs) is absent -- so it never breaks a portable copy.")

add("Cell-level IV", "Plot a cell I-V / P-V to PNG",
    "Drop a single-cell curve into a slide or a report.",
    """
from powerpy.render.figures import iv_pv_figure
# iv_pv_figure expects an array-like with .iv_curve(); wrap one cell as needed,
# or use it on a section/array (below). For a quick cell plot:
import matplotlib.pyplot as plt
v, i = cell.iv_curve()
plt.plot(v, i); plt.plot(v, v*i); plt.savefig("cell.png", dpi=170)
""",
    "For composed levels (section/array) prefer `iv_pv_figure(level, out)` which marks the MPP and bus voltage.")

# ============================================================ C. Array & electrical
add("Array & electrical", "Assemble the full array from the workbook",
    "Turn the section list into a cell -> string -> section -> panel -> array tree.",
    """
from powerpy.simulation import build_from_report
array = build_from_report(md)
print(array.name, "panels:", len(array.panels))
""",
    "Per-section harness resistance from the sections sheet is wired in automatically (distance from the yoke).")

add("Array & electrical", "Evaluate named mission cases",
    "The standard way to get per-phase power + bus compliance numbers.",
    """
from powerpy.simulation import evaluate, AnalysisCase
from powerpy.schemas import Phase, LaunchConfig

cases = [AnalysisCase("EOL single", Phase.END_OF_LIFE, LaunchConfig.SINGLE, season=0.967),
         AnalysisCase("EOL dual",   Phase.END_OF_LIFE, LaunchConfig.DUAL,   season=0.967)]
results = evaluate(md, cases)
for c in results:
    print(c.case.label, c.results.array.p_mp, "W,  bus", c.bus.power_w if c.bus else None)
""",
    "`evaluate` builds the array once and runs every case; each `CaseResult` carries the per-level summary and the bus-voltage compliance point.")

add("Array & electrical", "Resolve a phase into an Environment",
    "When you want the exact dose/loss/flux the framework uses for a phase.",
    """
from powerpy.simulation.pipeline import environment_for_phase
env = environment_for_phase(md, phase=Phase.END_OF_LIFE,
                            launch_config=LaunchConfig.DUAL, season=0.967)
print(env.temperature_c, env.dose_i, env.current_loss, env.voltage_loss)
""",
    "Pulls temperature from the mission table, dose from radiation_fluxes, and the loss products from the losses sheet -- all for that phase.")

add("Array & electrical", "Per-section results table",
    "Best for spotting which section is weakest (harness, position).",
    """
res = evaluate(md, cases)[0]
for s in res.results.sections:
    print(s.name, "Pmp", round(s.p_mp,1), "Imp", round(s.i_mp,3))
""",
    "Sections far from the yoke (higher resistance) show a slightly lower MPP -- the harness drop made visible.")

add("Array & electrical", "Current / power at the bus voltage",
    "The number the EPS cares about: how much the array delivers at the fixed bus.",
    """
array.apply(env)
i_bus = array.current_at_voltage(101.5)
print("at 101.5 V:", i_bus, "A  ->", 101.5 * i_bus, "W")
""",
    "`current_at_voltage` interpolates the array I-V; multiply by V for power. Compare against the requirement for margin.")

add("Array & electrical", "Whole-array I-V / P-V figure",
    "The headline plot: array curve with MPP, bus point and requirement line.",
    """
from powerpy.render.figures import iv_pv_figure
array.apply(env)
iv_pv_figure(array, "array.png", bus_voltage_v=101.5, requirement_w=7550.0,
             title="Whole-array I-V / P-V")
""",
    "Twin-axis (current + power). Markers show MPP and the operating point at the bus; horizontal line is the requirement.")

add("Array & electrical", "Per-section I-V grid figure",
    "One small I-V per section on a grid -- a quick visual audit of the array.",
    """
from powerpy.render.figures import sections_grid_figure
array.apply(env)
sections_grid_figure(array, "sections.png", bus_voltage_v=101.5)
""",
    "Best for catching an outlier section (wrong parallel count, huge resistance) at a glance.")

add("Array & electrical", "Generate the full electrical PDF report",
    "The deliverable: AIRBUS-style PDF straight from the workbook + cases.",
    """
from powerpy.render import Report
pdf = (Report.from_results(md, results, build_array=True, requirement_w=7550.0)
             .render("build_report", audience="engineer")
             .compile_pdf("reports/Solar_Array_Report.pdf"))
""",
    "Section order, visibility and content come from the `structure` sheet -- edit the workbook, not the template.")

# ============================================================ D. Layout / placement
add("Layout & placement", "Build a panel from an electrical topology",
    "Fastest way to get a layout: blocks in series, parallel strings, cells in series.",
    """
from powerpy.config.layout import panel_from_topology
layout = panel_from_topology(n_blocks=3, n_parallel=2, n_series=10)
print(layout.n_rows, "x", layout.n_cols, "=", layout.n_tiles, "cells")
""",
    "Every tile is auto-tagged `block='B1'`, `string='B1S1'`, so the same object carries the circuit AND the physical grid.")

add("Layout & placement", "Author a fully-tagged layout JSON",
    "Best when placement and wiring must live in one versioned file.",
    """
# data/layouts/simple_3block.json
# {"palette": {"B1S1": {"is_cell": true, "block": "B1", "string": "B1S1",
#                        "alpha_front": 0.91, "epsilon_front": 0.83}, ...},
#  "layout": ["B1S1 B1S1 ... B2S1 ...", "B1S2 ..."]}
from powerpy.config.layout import load_layout
layout = load_layout("src/powerpy/data/layouts/simple_3block.json")
print(layout.tile_at(0, 0).block, layout.tile_at(0, 0).string)
""",
    "A tile knows both its seat (row, col) and its team (block/string) -- placement for thermal, wiring for electrical.")

add("Layout & placement", "Layout with bare / no-SCA regions",
    "Model cut-outs, keep-outs, or missing cells -- they run at substrate optics.",
    """
from powerpy.config.layout import from_dict
layout = from_dict({"name": "with cut-out", "pitch_mm": 84,
    "palette": {"C": {"is_cell": True, "alpha_front": 0.91},
                ".": {"is_cell": False, "alpha_front": 0.3}},
    "layout": ["C C C C", "C . . C", "C C C C"]})
""",
    "Bare tiles generate no power (`generates_power == False`) -- they never 'fail' in a Monte-Carlo and take substrate optics in thermal.")

add("Layout & placement", "Draw the layout map (cells vs bare vs diode)",
    "A picture of where cells sit, coloured by block, with the harness bus-bars.",
    """
from powerpy.render.layout_figures import layout_map_figure
layout_map_figure(layout, "layout.png", label_tiles=True,
                  title="Panel layout")
""",
    "Hatched tiles = bare/no-SCA; red lines = inter-block harness/node. Best for a layout-review figure.")

add("Layout & placement", "Schematic of a panel's sections",
    "A legible block diagram when the real grid is too wide to draw cell-by-cell.",
    """
from powerpy.render.layout_figures import panel_schematic_figure
panel_schematic_figure(md.array_layout.section_types, "schematic.png")
""",
    "Each section becomes a block sized by its parallel-string count; a shorter section shows a hatched no-SCA gap.")

add("Layout & placement", "Get the thermal adjacency a layout implies",
    "Best when you wire your own solver -- the grid gives 4-neighbour pairs.",
    """
pairs = layout.neighbours()                     # [(i, j), ...] flat indices
props = layout.prop_arrays()                    # alpha/epsilon/is_cell per tile
print(len(pairs), "edges,", props["is_cell"].sum(), "cells")
""",
    "`neighbours()` is exactly what the lateral-conduction solver consumes for heat spreading.")

add("Layout & placement", "Save a layout you built in code",
    "Round-trip a programmatic layout back to JSON for reuse.",
    """
import json, dataclasses
def layout_to_dict(la):
    return {"name": la.name, "pitch_mm": la.pitch_mm,
            "palette": {k: dataclasses.asdict(t) for k, t in la.palette.items()},
            "layout": [" ".join(r) for r in la.grid]}
json.dump(layout_to_dict(layout), open("my_layout.json", "w"), indent=2)
""",
    "Keeps a generated topology (e.g. from `panel_from_topology`) as an editable input file.")

# ============================================================ E. Thermal
add("Thermal", "Equilibrium temperature of one cell (2-node)",
    "The core thermal answer: absorbed sun minus extracted power, radiated away.",
    """
from powerpy.solve.thermal import solve_thermal
r = solve_thermal(area=0.007075, alpha_front=0.91, alpha_rear=0.48,
                  epsilon_front=0.83, epsilon_rear=0.76, c_cond=800.0,
                  p_sun=1322.0, p_albedo=0.0, p_ir=0.0, p_elec=2.2)
print("T_front", r.t_front_c[0], "C")
""",
    "Radiative balance with sigma*T^4; `p_elec` is the cooling term (power leaving as electricity).")

add("Thermal", "Solve a whole panel (grid) thermally",
    "Per-cell temperatures across a panel, optionally with heat spreading.",
    """
from powerpy.solve.thermal import solve_panel
import numpy as np
res = solve_panel(layout, p_sun=1322.0, p_elec=np.full(layout.n_tiles, 2.2),
                  c_cond=800.0, g_lat=0.02, area=0.007075)
print("hottest cell", res.t_front_c.max(), "C")
""",
    "`g_lat > 0` turns on lateral conduction (sparse Newton); `g_lat = 0` is the fast independent-cell path.")

add("Thermal", "Solve from a Substrate object",
    "Convenience: take optics + conduction straight from a substrate JSON.",
    """
from powerpy.config.substrate import load_substrate
from powerpy.solve.thermal import solve_thermal_for_substrate
sub = load_substrate("FSP-SFLA")
r = solve_thermal_for_substrate(sub, area=0.007075, p_sun=1322.0,
                                p_albedo=0.0, p_ir=0.0, p_elec=2.2)
""",
    "`sub.c_cond = conductivity / thickness`. Swap substrates by name to compare thermal designs.")

add("Thermal", "See the effect of lateral conduction",
    "Best for justifying (or not) a conductive facesheet.",
    """
from powerpy.solve.thermal import lateral_conductance, solve_panel
import numpy as np
g = lateral_conductance(k_facesheet=150.0, thickness_m=3e-4,
                        edge_width_m=0.055, pitch_m=0.055)
pe = np.full(layout.n_tiles, 2.2); pe[layout.n_tiles//2] = -9.0   # one hot cell
cold = solve_panel(layout, p_sun=1322, p_elec=pe, c_cond=800, g_lat=0.0,  area=7e-3)
warm = solve_panel(layout, p_sun=1322, p_elec=pe, c_cond=800, g_lat=g,    area=7e-3)
print("hot-spot peak:", cold.t_front_c.max(), "->", warm.t_front_c.max())
""",
    "Conduction lowers a hot-spot peak by sharing heat with neighbours -- but also lets a cluster reinforce itself.")

add("Thermal", "Panel temperature heat-map figure",
    "Turn a solved grid into a coloured map for a report.",
    """
from powerpy.render.thermal_figures import panel_heatmap_figure
panel_heatmap_figure(res.t_front_c, "heatmap.png",
                     title="Panel temperature map")
""",
    "Auto-annotates each cell when the grid is small; guards against a degenerate (uniform) colour range.")

add("Thermal", "Full thermal PDF report",
    "AIRBUS-style thermal report: inputs, layout, equilibrium temps, hot-spot.",
    """
from powerpy.render.thermal_report import ThermalReport
from powerpy.analysis.thermal_report import ThermalCase
cases = [ThermalCase("EOL dual", Phase.END_OF_LIFE, LaunchConfig.DUAL, season=0.967)]
ThermalReport.from_metadata(md, cases,
        layout_file="src/powerpy/data/layouts/g2g_panel.json"
    ).render("build_thermal").compile_pdf("reports/Thermal_Report.pdf")
""",
    "Cell optics come from the cell JSON; substrate from the substrate JSON; the panel comes from the layout file (cells vs bare).")

add("Thermal", "Equilibrium temperature per mission phase",
    "Tabulate the array's operating temperature across the mission.",
    """
from powerpy.analysis.thermal_report import run_thermal_report, ThermalCase
data = run_thermal_report(md, [
    ThermalCase("BOL", Phase.BOL_BC, LaunchConfig.SINGLE, season=1.034),
    ThermalCase("EOL", Phase.END_OF_LIFE, LaunchConfig.DUAL, season=0.967)])
for p in data.points:
    print(p.case.label, round(p.t_front_c, 1), "C")
""",
    "Compare against the mission table's expected pva_temperature as a cross-check.")

add("Thermal", "Customize the substrate (what-if)",
    "Try a different facesheet/substrate without touching a file.",
    """
from powerpy.config.substrate import from_dict
sub = from_dict({"name": "CFRP test", "alpha_front": 0.3, "alpha_rear": 0.4,
                 "epsilon_front": 0.8, "epsilon_rear": 0.8,
                 "conductivity": 5.0, "thickness": 0.0005})
print("c_cond", sub.c_cond, "W/m2K")
""",
    "Higher conductivity / thinner substrate -> larger `c_cond` -> front and rear couple more tightly.")

# ============================================================ F. Failure & Monte-Carlo
add("Failure & Monte-Carlo", "Inject specific cell failures",
    "Best for a known-failure what-if (e.g. a cracked corner).",
    """
from powerpy.analysis.study import make_pe
from powerpy.solve.thermal import solve_panel
pe = make_pe(layout, failed=[0, 1, 10], healthy_w=2.2, reverse_w=-8.8)
res = solve_panel(layout, p_elec=pe, p_sun=1322, c_cond=800, g_lat=0.02, area=7e-3)
print("peak with 3 failed:", res.t_front_c.max(), "C")
""",
    "A failed cell flips from extracting `healthy_w` to dissipating `reverse_w` (negative) -- the reverse-bias hot spot.")

add("Failure & Monte-Carlo", "Sweep many failure patterns",
    "Rank a set of candidate failure scenarios by peak temperature.",
    """
from powerpy.analysis.study import failure_sweep, rank
patterns = [[0], [0, 1], [5, 6, 7]]
recs = failure_sweep(layout, patterns, t_limit_c=150.0,
                     solve_kwargs=dict(p_sun=1322, c_cond=800, g_lat=0.02, area=7e-3),
                     workers=4)
for r in rank(recs)[:3]:
    print(r["failed"], "->", r["peak_t_c"], "C,", r["n_over_limit"], "over limit")
""",
    "Patterns run in parallel on a thread pool (numpy releases the GIL during the solve).")

add("Failure & Monte-Carlo", "Greedy worst-case failure cluster",
    "Find the single most damaging way K cells could fail -- the design driver.",
    """
from powerpy.analysis.study import worst_case_search
w = worst_case_search(layout, max_failures=4, t_limit_c=150.0,
        solve_kwargs=dict(p_sun=1322, c_cond=800, g_lat=0.02, area=7e-3), workers=4)
print("worst:", w["failed"], "->", w["peak_t_c"], "C")
""",
    "Lateral conduction lets adjacent failures reinforce one another, so the worst case is usually a CLUSTER, not scattered cells.")

add("Failure & Monte-Carlo", "Auto-stopping Monte-Carlo",
    "Random failures, sampled until the mean peak temperature is statistically tight.",
    """
from powerpy.analysis.study import auto_monte_carlo
a = auto_monte_carlo(layout, t_limit_c=150.0,
        solve_kwargs=dict(p_sun=1322, c_cond=800, g_lat=0.02, area=7e-3),
        p_fail=0.05, target_se=1.5, max_runs=300, workers=4)
print(a["stopped"], a["n_runs"], "runs, mean peak", a["mean_peak_c"], "C")
""",
    "Standard error shrinks like 1/sqrt(N); it stops at `target_se` instead of a fixed N. Reproducible for a fixed seed.")

add("Failure & Monte-Carlo", "Full Monte-Carlo failure PDF report",
    "The deliverable: setup, distribution histogram, worst-case cluster + heat-map.",
    """
from powerpy.render.montecarlo_report import MonteCarloReport
MonteCarloReport.from_metadata(md,
        panel_layout_file="src/powerpy/data/layouts/simple_3block.json",
        phase=Phase.END_OF_LIFE, launch_config=LaunchConfig.DUAL, season=0.967,
        t_limit_c=150.0, p_fail=0.08, max_failures=4
    ).render("build_mc").compile_pdf("reports/MonteCarlo_Report.pdf")
""",
    "Takes a tagged layout (`panel_layout_file`) or a simple C/. grid (`layout_file`). Bare tiles are excluded from failures automatically.")

add("Failure & Monte-Carlo", "CLI: run / worst / sweep",
    "Best for quick checks from a terminal -- no Python script.",
    """
# solve one layout (+ optional injected failures) and write an HTML heat-map
powerpy run  layout.json --g-lat 0.02 --fail 0 1 2 --report out.html

# greedy worst-case cluster
powerpy worst layout.json --max-failures 4 --report worst.html

# auto-stopping Monte-Carlo
powerpy sweep layout.json --p-fail 0.05 --target-se 1.5 --max-runs 300
""",
    "Also `python -m powerpy <cmd>`. Flags: `--p-sun`, `--albedo`, `--ir`, `--t-limit`, `--healthy-w`, `--reverse-w`, `--workers`, `--substrate`.",
    cli=True)

add("Failure & Monte-Carlo", "Single failed-cell hot spot",
    "The simplest failure case: one open bypass diode, how hot and what margin.",
    """
import numpy as np
from powerpy.solve.thermal import solve_panel
pe = np.full(layout.n_tiles, 2.2); pe[layout.n_tiles // 2] = -8.8
res = solve_panel(layout, p_sun=1322, p_elec=pe, c_cond=800, g_lat=0.02, area=7e-3)
peak = res.t_front_c.max()
print("hot-spot", round(peak,1), "C, margin to 150 C:", round(150-peak,1))
""",
    "Margin = limit - peak. Below zero means a cell could exceed its temperature limit.")

add("Failure & Monte-Carlo", "Tune the reverse-bias dissipation",
    "Make the failure model match your real bypass-diode behaviour.",
    """
# reverse_w is how much a failed cell dissipates (negative = heat in).
# Default in run_mc_study is 4x the cell's healthy power. Override it:
from powerpy.analysis.montecarlo_report import run_mc_study
data = run_mc_study(md, panel_layout_file="src/powerpy/data/layouts/simple_3block.json",
                    dissipation_multiple=6.0, t_limit_c=150.0, max_failures=4)
print("worst peak:", data.worst["peak_t_c"], "C")
""",
    "If you have the real reverse I-V / clamp voltage, set `reverse_w` from I*V_reverse instead of a multiple.")

# ============================================================ G. Diode & voltage
add("Bypass diode & voltage", "Reverse voltage on a failed cell",
    "Best for sizing how many cells one bypass diode should protect.",
    """
from powerpy.model.diode import (unprotected_reverse_voltage,
                                 clamped_reverse_voltage, BypassDiode)
v_un = unprotected_reverse_voltage(n_series=54, v_cell=2.4)       # whole string
v_cl = clamped_reverse_voltage(18, v_cell=2.4, diode=BypassDiode(0.6))
print("unprotected", v_un, "V  vs clamped", v_cl, "V")
""",
    "A bypass diode clamps the reverse voltage a shaded cell sees -- fewer cells per diode means a gentler reverse stress.")

add("Bypass diode & voltage", "Power a failed cell dissipates",
    "Convert the failure into the `p_elec` the thermal solver needs.",
    """
from powerpy.model.diode import BypassDiode, failed_cell_p_elec
diode = BypassDiode(v_forward=0.6)
p = failed_cell_p_elec(i=1.2, n_series=54, v_cell=2.4, diode=diode,
                       cells_per_diode=18)
print("dissipated", p, "W")
""",
    "Links the electrical failure (string current x reverse voltage) to the thermal hot spot in one call.")

add("Bypass diode & voltage", "Scan bypass-diode spacing",
    "Find how 'cells per diode' trades against reverse stress / dissipation.",
    """
from powerpy.model.diode import spacing_scan, BypassDiode
rows = spacing_scan(1.2, 2.4, 54, BypassDiode(0.6),
                    cells_per_diode_options=[9, 18, 27, 54])
for r in rows:
    print(r)                                    # {cells_per_diode, v_reverse, p_reverse_w}
""",
    "Best for a diode-placement trade study: more diodes = safer but heavier/costlier.")

add("Bypass diode & voltage", "Zero-voltage (reverse-bias cancellation) analysis",
    "The special case where forward and reverse voltages cancel and the panel reads 0 V.",
    """
from powerpy.analysis.voltage import find_zero_voltage_diode, compare_models
z = find_zero_voltage_diode(n_blocks=3, n_series=54, v_fwd=2.3, v_diode=0.7)
print("zero-voltage when", z)
print(compare_models(n_blocks=3, n_series=54))   # raw vs diode-protected
""",
    "Explains a confusing 0 V reading: enough reverse-biased blocks exactly offset the forward ones. `compare_models` shows raw vs bypass-protected.")

# ============================================================ H. Orbit & transient
add("Orbit & transient", "Orbit period, beta angle, eclipse in one call",
    "Best first step for any orbit-driven thermal/power case.",
    """
from powerpy.model.orbit import summarize_orbit
s = summarize_orbit(altitude_km=500, inclination_deg=51.6, raan_deg=0, day_of_year=172)
print(f"period {s.period_min:.1f} min, beta {s.beta_deg:.1f} deg, "
      f"eclipse {100*s.eclipse_fraction:.0f}% ({s.eclipse_min:.1f} min)")
""",
    "Pure numpy -- no astropy/numba/hapsira. GEO at solstice -> ~0% eclipse; low LEO -> ~36%.")

add("Orbit & transient", "Flux-vs-time over one orbit",
    "The driver for a transient thermal run: sun on the sunlit arc, zero in eclipse.",
    """
from powerpy.model.orbit import orbit_flux_timeline
flux = orbit_flux_timeline(altitude_km=500, inclination_deg=51.6, raan_deg=0,
                           day_of_year=172, n_steps=240)
ecl = sum(f.eclipsed for f in flux)
print(ecl, "of", len(flux), "steps in eclipse; p_sun max", max(f.p_sun for f in flux))
""",
    "Eclipse is flagged from the actual cylindrical-shadow geometry, not a fixed fraction.")

add("Orbit & transient", "Transient temperature around an orbit",
    "How the array heats in sun and cools in eclipse -- the time-domain answer.",
    """
from powerpy.solve.transient import solve_transient, areal_heat_capacity
# include the backing's thermal mass (a bare cell alone is too light to be stable)
C = areal_heat_capacity(area=0.007075, rho=2700, cp=900, thickness=0.002)
flux = orbit_flux_timeline(500, 51.6, 0, 172, 240)
tr = solve_transient(area=0.007075, alpha_front=0.91, alpha_rear=0.48,
                     epsilon_front=0.83, epsilon_rear=0.76, c_cond=800.0,
                     heat_capacity=C, flux_series=flux, p_elec_series=2.2)
print("Tmax", tr.t_front_c.max(), "Tmin", tr.t_front_c.min())
""",
    "Backward-Euler integration of C dT/dt = (heat in - heat out). `p_elec_series` can be a scalar, per-cell, or a (steps x cells) failure injected mid-orbit.")

add("Orbit & transient", "Coupled electrical <-> thermal solve",
    "Best when power and temperature chase each other: a hotter cell makes less power, which changes its heat.",
    """
from powerpy.solve.coupling import couple
import numpy as np
# power_fn: per-cell temperature [C] -> per-cell extracted power [W]
def power_fn(t_c):
    return np.maximum(0.0, 2.6 - 0.01 * (t_c - 28.0))   # toy temp-derated power
r = couple(power_fn, area=0.007075, alpha_front=0.91, alpha_rear=0.48,
           epsilon_front=0.83, epsilon_rear=0.76, c_cond=800.0,
           p_sun=1322.0, omega=0.5)
print("self-consistent T", r.t_front_c[0], "C, converged", r.converged)
""",
    "Fixed-point iteration with under-relaxation (`omega`) until temperature and power stop changing -- the physically self-consistent operating point.")

add("Orbit & transient", "Time for a hot spot to reach its limit",
    "Best for a thermal-runaway / survival question after a failure.",
    """
from powerpy.solve.transient import time_to_threshold
t = time_to_threshold(tr, limit_c=150.0, cell=0)
print("reaches 150 C after", t, "s" if t is not None else "(never)")
""",
    "Returns when cell 0 first crosses the limit -- or None if it stays safe across the whole timeline.")

# emit -------------------------------------------------------------------------
CATS = []
for cat, *_ in UC:
    if cat not in CATS:
        CATS.append(cat)


def esc(s):
    return html.escape(s)


def code_html(code, cli=False):
    label = "CLI" if cli else "Python"
    return (f'<div class="codewrap"><span class="codelabel">{label}</span>'
            f'<pre class="code">{esc(code)}</pre></div>')


blocks = []
n = 0
for cat in CATS:
    blocks.append(f'<h2 class="cathead" id="cat-{esc(cat).replace(" ","-")}">{esc(cat)}</h2>')
    for c, title, best, code, cli, note in [u for u in UC if u[0] == cat]:
        n += 1
        is_cli = cli is True
        cli_extra = cli if isinstance(cli, str) else None
        body = code_html(code, cli=is_cli)
        if cli_extra:
            body += f'<p class="note"><strong>Also:</strong> {esc(cli_extra)}</p>'
        blocks.append(f"""
<div class="example">
  <div class="exhead"><span class="num">{n:02d}</span><h3>{esc(title)}</h3></div>
  <div class="callout best"><span class="bestlabel">Best for</span> {esc(best)}</div>
  {body}
  <p class="note">{esc(note)}</p>
</div>""")

# contents
toc_rows = []
n = 0
for cat in CATS:
    toc_rows.append(f'<li class="toccat">{esc(cat)}</li>')
    for c, title, *_ in [u for u in UC if u[0] == cat]:
        n += 1
        toc_rows.append(f'<li><span class="tocn">{n:02d}</span> {esc(title)}</li>')

HTML = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>PowerPy Cookbook -- 50 Use Cases</title>
<link rel="stylesheet" href="print-base.css">
<style>
:root {{ --accent:#1F5048; --accent2:#9a4715; --ink:#1a1a1a; --sub:#5b6b66; }}
html,body {{ font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; color:var(--ink); line-height:1.5; }}
h1,h2,h3 {{ font-family: Georgia, "Times New Roman", serif; }}
.chapter-opener {{ border:1px solid #d9dde2; border-radius:8px; padding:20mm 16mm; margin-bottom:8mm; }}
.chapter-opener .kicker {{ color:var(--accent); font-size:.8rem; letter-spacing:.18em; text-transform:uppercase; font-family:"Segoe UI",sans-serif; }}
.chapter-opener h1 {{ font-size:2.5rem; margin:.3em 0 .2em; color:var(--accent); }}
.chapter-opener p {{ color:var(--sub); max-width:60ch; }}
.toc {{ columns:2; column-gap:12mm; font-size:.86rem; list-style:none; padding:0; }}
.toc li {{ margin:.12em 0; break-inside:avoid; }}
.toc .toccat {{ font-weight:700; color:var(--accent); margin-top:.7em; font-family:"Segoe UI",sans-serif; }}
.toc .tocn {{ color:var(--accent2); font-weight:600; font-variant-numeric:tabular-nums; }}
.cathead {{ color:var(--accent); border-bottom:2px solid var(--accent); padding-bottom:.2em; margin:9mm 0 5mm; font-size:1.5rem; break-after:avoid; }}
.example {{ border:1px solid #e2e6ea; border-left:4px solid var(--accent); border-radius:6px; padding:5mm 6mm; margin:0 0 6mm; }}
.exhead {{ display:flex; align-items:baseline; gap:.6em; }}
.exhead .num {{ background:var(--accent); color:#fff !important; font-family:"Segoe UI",sans-serif; font-weight:700; font-size:.8rem; padding:.15em .5em; border-radius:4px; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
.exhead h3 {{ margin:0; font-size:1.12rem; }}
.callout.best {{ background:#eef3f1; border:1px solid #cfe0da; border-radius:5px; padding:.5em .8em; margin:.6em 0; font-size:.9rem; }}
.bestlabel {{ display:inline-block; background:var(--accent); color:#fff !important; font-size:.62rem; letter-spacing:.1em; text-transform:uppercase; padding:.12em .5em; border-radius:3px; margin-right:.5em; font-family:"Segoe UI",sans-serif; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
.codewrap {{ position:relative; margin:.6em 0; }}
.codelabel {{ position:absolute; top:0; right:0; font-size:.6rem; letter-spacing:.1em; color:#8a97a0; padding:.2em .5em; font-family:"Segoe UI",sans-serif; }}
pre.code {{ font-family:"Consolas","SF Mono",Menlo,monospace; font-size:.78rem; line-height:1.45; padding:.8em 1em; border-radius:5px; overflow:hidden; white-space:pre-wrap; }}
.note {{ font-size:.86rem; color:#33403b; margin:.5em 0 0; }}
.note strong {{ color:var(--accent2); }}
.legend {{ font-size:.84rem; color:var(--sub); }}
</style></head>
<body>

<div class="chapter-opener">
  <div class="kicker">PowerPy &middot; Solar-Array Analysis Framework</div>
  <h1>Cookbook: 50 Use Cases</h1>
  <p>Fifty worked examples of how to drive and customise the framework &mdash; from loading the
  workbook to electrical I-V, layout, thermal, failure Monte-Carlo, bypass diodes and orbit.
  Each entry says what it is <em>best for</em>, shows the exact Python (and CLI where it applies),
  and adds a short note. Pure examples &mdash; copy, adapt, run.</p>
  <p class="legend"><strong>Setup:</strong> run from the repo root with <code>sys.path.insert(0, "src")</code>
  (or <code>python run.py</code>); no installation required. Snippets assume <code>md = load_report_data(...)</code>
  and, where a layout is used, a <code>layout</code> from one of the layout examples.</p>
</div>

<h2 class="cathead">Contents</h2>
<ul class="toc">
{''.join(toc_rows)}
</ul>

{''.join(blocks)}

<div class="example" style="border-left-color:var(--accent2);">
  <div class="exhead"><h3>Where each analysis fits</h3></div>
  <p class="note"><strong>Electrical (Report):</strong> power margin vs requirement, per-section sizing, harness effect. &nbsp;
  <strong>Thermal (ThermalReport):</strong> operating temperature per phase, hot-spot margin. &nbsp;
  <strong>Monte-Carlo (MonteCarloReport):</strong> failure risk &mdash; distribution of peak temperature and the worst credible cluster. &nbsp;
  <strong>Orbit + transient:</strong> time-domain heating/cooling and eclipse survival. &nbsp;
  Pick the lightest tool that answers the question; escalate to Monte-Carlo only for failure/worst-case work.</p>
</div>

</body></html>"""

out = HERE / "PowerPy_Cookbook_50_UseCases.html"
out.write_text(HTML, encoding="utf-8")
print("wrote", out, "with", n, "use cases")
