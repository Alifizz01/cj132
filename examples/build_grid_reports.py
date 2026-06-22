# -*- coding: utf-8 -*-
"""Generate the ELECTRICAL and THERMAL reports for a grid-as-single-source panel.

The panel: 3 blocks, each with 2 parallel strings, each string 12 cells in series
(= 72 cells). ONE grid is the single source: each cell tile carries its electrical
identity (``string`` = series string, ``block`` = parallel section) AND its optics
(front absorptivity from the cell, rear/IR from the substrate). The same grid
drives both reports:

  * ELECTRICAL -- the array is derived from the grid (build_array_from_grid) and
    the nominal report is rendered for each analysis-scope config.
  * THERMAL    -- the same PanelLayout is solved (lateral conduction + a failed
    bypass-diode hot spot) and the LaTeX thermal report is rendered.

The cell is taken from ``cell_reference_file`` + ``cell_shunt_diode_reference_file``
and the substrate from the new ``substrate_reference_file`` column of cell_params.

Zero-install (mirrors run.py). Usage:
    python examples/build_grid_reports.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from powerpy.app import build_electrical_report                 # noqa: E402
from powerpy.config.layout import load_layout                   # noqa: E402
from powerpy.config.substrate import from_dict as substrate_from_dict  # noqa: E402
from powerpy.loader.report import load_report_data              # noqa: E402
from powerpy.loader.analysis import load_analysis_scope         # noqa: E402
from powerpy.analysis.thermal_report import ThermalCase         # noqa: E402
from powerpy.render.thermal_report import ThermalReport         # noqa: E402

DATA_DIR = _ROOT / "src" / "powerpy" / "data"
PARAMS = _ROOT / "params.xlsx"
GRID_JSON = DATA_DIR / "layouts" / "grid_3x2x12.json"
ELEC_PDF = _ROOT / "reports" / "grid_3x2x12_electrical.pdf"
THERM_PDF = _ROOT / "reports" / "grid_3x2x12_thermal.pdf"

N_BLOCKS, N_PARALLEL, N_SERIES = 3, 2, 12


def build_grid_dict(cell_alpha: float, sub) -> dict:
    """3 blocks x 2 parallel x 12 series = 72 cells, side-by-side.

    Rows = the parallel strings (2); columns = block*series (3*12 = 36). Each tile
    is tagged ``string="B{b}S{s}"`` (its series string) and ``block="B{b}"`` (its
    parallel section); cell tiles carry the cell's front absorptivity and the
    substrate's rear/IR optics so the same grid is thermally correct.
    """
    palette: dict = {}
    rows = []
    for s in range(1, N_PARALLEL + 1):                 # parallel string index -> a row
        row_keys = []
        for c in range(N_BLOCKS * N_SERIES):           # 36 columns
            b = c // N_SERIES + 1                       # block 1..3
            key = "B%dS%d" % (b, s)
            if key not in palette:
                palette[key] = {
                    "is_cell": True,
                    "string": key,                      # series string id
                    "block": "B%d" % b,                 # parallel section id
                    "cell_type": "3G30LARS_GEO",
                    "alpha_front": float(cell_alpha),   # cell faces the sun
                    "alpha_rear": float(sub.alpha_rear),
                    "epsilon_front": float(sub.epsilon_front),
                    "epsilon_rear": float(sub.epsilon_rear),
                }
            row_keys.append(key)
        rows.append(" ".join(row_keys))

    circuit = {}
    for b in range(1, N_BLOCKS + 1):
        circuit["B%d" % b] = {"resistance_ohm": 0.0}
        for s in range(1, N_PARALLEL + 1):
            circuit["B%dS%d" % (b, s)] = {"string_shunt_diode": True}

    return {
        "name": "grid_3x2x12 (%d blocks x %d parallel x %d series = %d cells)"
                % (N_BLOCKS, N_PARALLEL, N_SERIES, N_BLOCKS * N_PARALLEL * N_SERIES),
        "pitch_mm": 40.0,
        "palette": palette,
        "layout": rows,
        "circuit": circuit,
    }


def _thermal_cases(report):
    """One ThermalCase per analysis-scope row (else a single End_of_Life case)."""
    scope = load_analysis_scope(PARAMS)
    if scope:
        return [ThermalCase(label=c.label, phase=c.phase,
                            launch_config=c.launch, season=c.season)
                for c in scope]
    return [ThermalCase(label="End_of_Life", phase="End_of_Life",
                        launch_config="single", season=1.0)]


def main() -> int:
    warnings.filterwarnings("ignore")
    report = load_report_data(PARAMS, DATA_DIR)

    # substrate from the new substrate_reference_file column (fallback msro_case2)
    sub_ref = report.cell.substrate_reference_file or (DATA_DIR / "substrates" / "msro_case2.json")
    with open(sub_ref, "r", encoding="utf-8") as fh:
        sub = substrate_from_dict(json.load(fh))

    # write the single grid (electrical tags + thermal optics)
    GRID_JSON.parent.mkdir(parents=True, exist_ok=True)
    GRID_JSON.write_text(json.dumps(build_grid_dict(report.cell.electrical.alpha, sub),
                                    indent=2), encoding="utf-8")
    print("[grid] wrote %s (%d cells)" % (GRID_JSON, N_BLOCKS * N_PARALLEL * N_SERIES))
    print("[grid] substrate: %s (c_cond=%.0f W/m^2K)" % (sub.name, sub.c_cond))

    # --- ELECTRICAL report (array derived from the grid) ---
    epdf, labels, _ = build_electrical_report(
        PARAMS, ELEC_PDF, data_dir=DATA_DIR, engine="analytic", grid_file=GRID_JSON)
    print("[elec] cases: %s" % ", ".join(labels))
    print("[elec] %s" % (epdf or "pdflatex missing -- .tex only"))

    # --- THERMAL report (same grid, lateral conduction + hot spot) ---
    grid_layout = load_layout(GRID_JSON)
    tpdf = (ThermalReport
            .from_metadata(report, _thermal_cases(report), substrate=sub,
                           layout=grid_layout, t_limit_c=150.0)
            .render(_ROOT / "reports" / "_build_grid_thermal")
            .compile_pdf(THERM_PDF))
    print("[therm] %s" % (tpdf or "pdflatex missing -- .tex only"))

    return 0 if (epdf and tpdf) else 1


if __name__ == "__main__":
    raise SystemExit(main())
