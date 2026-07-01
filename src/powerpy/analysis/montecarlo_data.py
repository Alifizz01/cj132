"""Monte-Carlo failure study packaged for a report.

Wraps :mod:`powerpy.analysis.study` (auto-stopping random sampling + greedy
worst-case search) around a panel built from the cell JSON optics and the
substrate JSON, and returns everything a report needs:

  * the study setup (panel size, failure probability, limits, auto-stop target),
  * the converged summary (runs, mean/max peak T, standard error, P(over-limit)),
  * the per-run peak temperatures (for a histogram),
  * the worst-case failure cluster and its growth trajectory.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from powerpy.analysis import study
from powerpy.analysis.thermal_data import (
    AM0,
    cell_optics,
    cell_palette,
    p_elec_per_cell,
    load_layout_grid,
    panel_from_grid,
)
from powerpy.config.layout import from_dict as _layout_from_dict
from powerpy.config.substrate import Substrate, load_substrate
from powerpy.schemas import ReportMetadata
from powerpy.schemas._common import Phase
from powerpy.schemas.fluxes import LaunchConfig
from powerpy.simulation.pipeline import environment_for_phase
from powerpy.analysis.power_budget import DEFAULT_ORBIT, compute_power_budget


@dataclass
class MCReportData:
    inputs: dict
    summary: dict          # auto_monte_carlo summary (records stripped out)
    p_over_limit: float    # fraction of runs with >=1 cell over the limit
    peaks: list            # peak_t_c per run (histogram input)
    worst: dict            # worst_case_search result
    t_limit_c: float
    worst_grid: object = None   # (rows, cols) temperatures of the worst case
    power_budget: object = None


def _build_panel(md, sub, n_rows, n_cols):
    _, _, area = cell_optics(md)
    pitch_mm = float(np.sqrt(area) * 1000.0)
    layout = _layout_from_dict({
        "name": "mc_panel",
        "pitch_mm": pitch_mm,
        "palette": cell_palette(md, sub),
        "layout": [" ".join(["C"] * n_cols) for _ in range(n_rows)],
    })
    return layout, area


def run_mc_study(md: ReportMetadata, *,
                 phase: Phase = Phase.END_OF_LIFE,
                 launch_config: LaunchConfig = LaunchConfig.DUAL,
                 season: float = 0.967,
                 substrate: Substrate | str = "FSP-SFLA",
                 layout=None,
                 layout_file: str | None = None,
                 panel_layout_file: str | None = None,
                 n_rows: int = 7, n_cols: int = 10,
                 t_limit_c: float = 150.0,
                 dissipation_multiple: float = 4.0,
                 p_fail: float = 0.05, target_se: float = 1.5,
                 max_runs: int = 300, max_failures: int = 5,
                 g_lat: float = 0.02, seed: int = 0,
                 workers: int = 4,
                 efficiency: float = 0.30) -> MCReportData:
    """Run the auto-stopping MC + worst-case search and package the results."""
    sub = (substrate if isinstance(substrate, Substrate)
           else load_substrate(substrate))
    if panel_layout_file is not None:           # full-palette layout (load_layout)
        from powerpy.config.layout import load_layout
        layout = load_layout(panel_layout_file)
    if layout is not None:                      # prebuilt PanelLayout
        _, _, area = cell_optics(md)
        n_rows, n_cols = layout.n_rows, layout.n_cols
    elif layout_file is not None:               # 'C'/'.' grid
        layout, area = panel_from_grid(md, sub, load_layout_grid(layout_file))
        n_rows, n_cols = layout.n_rows, layout.n_cols
    else:
        layout, area = _build_panel(md, sub, n_rows, n_cols)

    env = environment_for_phase(md, phase=phase, launch_config=launch_config,
                                season=season)
    p_cell = p_elec_per_cell(md, env)
    healthy_w = p_cell
    reverse_w = -dissipation_multiple * p_cell

    orbit = md.mission_orbit if md.mission_orbit is not None else DEFAULT_ORBIT
    budget = compute_power_budget(orbit, season=season, efficiency=efficiency)
    solve_kwargs = dict(p_sun=AM0 * season,
                        p_albedo=budget.albedo_w_m2, p_ir=budget.ir_w_m2,
                        c_cond=sub.c_cond, g_lat=g_lat, area=area)

    summary = study.auto_monte_carlo(
        layout, t_limit_c=t_limit_c, solve_kwargs=solve_kwargs,
        p_fail=p_fail, target_se=target_se, max_runs=max_runs,
        healthy_w=healthy_w, reverse_w=reverse_w, seed=seed, workers=workers)

    worst = study.worst_case_search(
        layout, max_failures=max_failures, t_limit_c=t_limit_c,
        solve_kwargs=solve_kwargs, healthy_w=healthy_w, reverse_w=reverse_w,
        workers=workers)

    # re-solve the worst-case failure set to get a temperature map for the report
    from powerpy.solve.thermal import solve_panel
    pe = study.make_pe(layout, worst["failed"], healthy_w, reverse_w)
    worst_grid = np.asarray(solve_panel(layout, p_elec=pe, **solve_kwargs).t_front_c)

    records = summary.pop("records")
    peaks = [r["peak_t_c"] for r in records]
    n_over = sum(1 for r in records if r["n_over_limit"] > 0)
    p_over = (n_over / len(records)) if records else 0.0

    inputs = {
        "panel_rows": n_rows, "panel_cols": n_cols,
        "n_cells": len(study.cell_indices(layout)),
        "phase": phase, "launch_config": launch_config,
        "p_fail": p_fail, "healthy_w": round(healthy_w, 3),
        "reverse_w": round(reverse_w, 3), "t_limit_c": t_limit_c,
        "target_se": target_se, "max_runs": max_runs,
        "dissipation_multiple": dissipation_multiple,
    }
    return MCReportData(inputs=inputs, summary=summary, p_over_limit=p_over,
                        peaks=peaks, worst=worst, t_limit_c=t_limit_c,
                        worst_grid=worst_grid, power_budget=budget)
