"""setup_sim.py -- Phase 3 config tooling for per-cell simulation.

Responsibilities
----------------
1. **Workbook**: generate a blank ``sim_conditions.xlsx`` when it is missing;
   normalise (add missing sheets) without clobbering existing user values.
2. **Snapshot**: read the master grid + condition layers, assemble an
   ``ArraySpec``, validate the bijection, and emit a resolved, deterministically
   ordered JSON snapshot into ``runs/<run_id>/snapshot.json``.

Usage (from project root)
--------------------------
    python scripts/setup_sim.py \\
        --layout  path/to/layout.json \\
        --wb      sim_conditions.xlsx \\
        --runs    runs/ \\
        --run-id  my_run

Everything can also be called programmatically via ``run_setup_sim()``.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "src"))

from powerpy.config.layout import PanelLayout, load_layout
from powerpy.loader.sim_config import read_topology, resolve_layout
from powerpy.loader.workbooks import find_workbooks
from powerpy.loader.condition_layers import (
    generate_condition_workbook,
    load_condition_layers,
    normalize_condition_workbook,
)
from powerpy.schemas.panel_circuit import ArraySpec, SectionSpec, StringSpec, PanelSpec, validate_bijection
from powerpy.simulation.cell_condition import CellCondition, sample_manufacturing_variance
from powerpy.simulation.spec_adapt import adapt_grid


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_setup_sim(
    layout: PanelLayout,
    *,
    wb_path: Path,
    runs_dir: Path,
    run_id: str = "run",
    imp_sigma: float = 0.0,
    pmax_sigma: float = 0.0,
    variance_seed: int = 0,
) -> Path:
    """Generate/normalise the workbook and emit a run snapshot.

    Parameters
    ----------
    layout:
        The master :class:`~powerpy.config.layout.PanelLayout`.
    wb_path:
        Path to the ``sim_conditions.xlsx`` workbook.  Created when missing;
        normalised in place (no clobber) when present.
    runs_dir:
        Parent folder for run snapshots (``runs/<run_id>/snapshot.json``).
    run_id:
        Identifier for this run's snapshot folder (default ``"run"``).
    imp_sigma, pmax_sigma:
        Manufacturing variance relative sigmas (default 0 = no-op).
    variance_seed:
        RNG seed for manufacturing variance sampling.

    Returns
    -------
    Path to the written ``snapshot.json`` file.
    """
    wb_path = Path(wb_path)
    runs_dir = Path(runs_dir)
    n_rows, n_cols = layout.n_rows, layout.n_cols

    # --- workbook: generate or normalise (never clobber) --------------------
    if not wb_path.exists():
        generate_condition_workbook(wb_path, n_rows=n_rows, n_cols=n_cols)
    else:
        normalize_condition_workbook(wb_path, n_rows=n_rows, n_cols=n_cols)

    # --- load condition layers ----------------------------------------------
    import openpyxl
    wb = openpyxl.load_workbook(str(wb_path), data_only=True)
    base_conditions: dict[int, CellCondition] = load_condition_layers(
        wb, n_rows=n_rows, n_cols=n_cols)

    # Apply manufacturing variance (no-op when both sigmas are 0).
    n_tiles = n_rows * n_cols
    ordered_keys = list(range(n_tiles))
    cond_list = [base_conditions.get(k, CellCondition()) for k in ordered_keys]
    if imp_sigma != 0.0 or pmax_sigma != 0.0:
        cond_list = sample_manufacturing_variance(
            cond_list, seed=variance_seed,
            imp_sigma=imp_sigma, pmax_sigma=pmax_sigma)
    conditions: dict[int, CellCondition] = dict(zip(ordered_keys, cond_list))

    # --- build ArraySpec from master grid -----------------------------------
    spec: ArraySpec = adapt_grid(layout)

    # --- validate bijection -------------------------------------------------
    validate_bijection(spec, n_tiles)

    # --- emit snapshot ------------------------------------------------------
    snap_dir = runs_dir / run_id
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / "snapshot.json"

    snapshot = _build_snapshot(spec, conditions)
    snap_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True),
                         encoding="utf-8")
    return snap_path


# ---------------------------------------------------------------------------
# Snapshot serialisation (deterministic)
# ---------------------------------------------------------------------------

def _spec_to_dict(spec: ArraySpec) -> dict:
    """Serialise ArraySpec to a plain dict (deterministic ordering)."""
    panels = []
    for pan in sorted(spec.panels, key=lambda p: p.id):
        sections = []
        for sec in sorted(pan.sections, key=lambda s: s.id):
            strings = []
            for st in sorted(sec.strings, key=lambda s: s.id):
                strings.append({
                    "id": st.id,
                    "members": list(st.members),
                    "series_resistance_ohm": st.series_resistance_ohm,
                    "block_diode_v_drop": st.block_diode_v_drop,
                    "n_block_diodes": st.n_block_diodes,
                    "string_shunt_diode": st.string_shunt_diode,
                })
            sections.append({
                "id": sec.id,
                "panel": sec.panel,
                "resistance_ohm": sec.resistance_ohm,
                "strings": strings,
            })
        panels.append({"id": pan.id, "sections": sections})
    return {"name": spec.name, "panels": panels}


def _condition_to_dict(cond: CellCondition) -> dict:
    return {
        "state": cond.state,
        "shade": cond.shade,
        "life": cond.life,
        "incidence": cond.incidence,
        "imp_factor": cond.imp_factor,
        "pmax_factor": cond.pmax_factor,
    }


def _build_snapshot(spec: ArraySpec, conditions: dict[int, CellCondition]) -> dict:
    """Build the full snapshot dict (deterministic: sorted keys)."""
    conds_dict = {
        str(k): _condition_to_dict(v)
        for k, v in sorted(conditions.items())
    }
    return {
        "spec": _spec_to_dict(spec),
        "conditions": conds_dict,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--layout", default=None,
                   help="Path to a grid JSON (PanelLayout). If omitted, the panel "
                        "topology is read from the 'panel' sheet of --wb (params.xlsx).")
    p.add_argument("--substrate", default=None,
                   help="Substrate name or JSON path (optional).")
    p.add_argument("--wb", default=str(_ROOT / "src" / "powerpy" / "param" / "params.xlsx"),
                   help="LEGACY single workbook holding BOTH cell config and the "
                        "condition layers (default: params.xlsx). Ignored when "
                        "--design/--scenario are given.")
    p.add_argument("--design", default=None,
                   help="design workbook ('topology'/'panel' sheet).")
    p.add_argument("--scenario", default=None,
                   help="scenario workbook (layer_* condition sheets live here).")
    p.add_argument("--runs", default="runs",
                   help="Parent directory for run snapshots (default: runs/).")
    p.add_argument("--run-id", default="run",
                   help="Run identifier (default: run).")
    p.add_argument("--imp-sigma", type=float, default=0.0,
                   help="Manufacturing Imp relative sigma (default 0 = no-op).")
    p.add_argument("--pmax-sigma", type=float, default=0.0,
                   help="Manufacturing Pmax relative sigma (default 0 = no-op).")
    p.add_argument("--variance-seed", type=int, default=0,
                   help="RNG seed for manufacturing variance (default 0).")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if args.design or args.scenario:
        wbs = find_workbooks(design=args.design, scenario=args.scenario)
    else:
        wbs = find_workbooks(legacy_params=args.wb)
    if args.layout:
        layout = load_layout(args.layout, substrate=args.substrate)
        imp_sigma, pmax_sigma, seed = args.imp_sigma, args.pmax_sigma, args.variance_seed
    else:
        cfg = read_topology(wbs.design)        # 'topology' sheet ('panel' fallback)
        layout = resolve_layout(cfg, base_dir=wbs.design.parent)
        imp_sigma = args.imp_sigma or cfg["imp_sigma"]
        pmax_sigma = args.pmax_sigma or cfg["pmax_sigma"]
        seed = cfg["variance_seed"]
    snap = run_setup_sim(
        layout=layout,
        wb_path=Path(wbs.scenario),   # condition layers live in the scenario file
        runs_dir=Path(args.runs),
        run_id=args.run_id,
        imp_sigma=imp_sigma,
        pmax_sigma=pmax_sigma,
        variance_seed=seed,
    )
    print("layout : %s  (%d x %d)" % (layout.name, layout.n_rows, layout.n_cols))
    print("snapshot -> %s" % snap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
