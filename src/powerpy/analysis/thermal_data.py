"""Thermal-analysis data layer for the thermal report.

Given a loaded :class:`ReportMetadata` and a :class:`Substrate`, this computes
the three things the thermal report shows:

  * per-phase **equilibrium cell temperature** (2-node radiative balance),
  * a **panel temperature heat-map** (the lateral-conduction panel solver),
  * a **failed-bypass-diode hot-spot** case with margin to a temperature limit.

Cell optical/geometry parameters come from the cell JSON via
``ReportMetadata.cell.electrical`` (``alpha`` front absorptance, ``epsilon``
front emittance, ``area_m2``).  Rear-face optics and through-thickness
conduction come from the substrate JSON.  No new workbook columns are needed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from powerpy.config.layout import from_dict as _layout_from_dict
from powerpy.config.substrate import Substrate, load_substrate
from powerpy.schemas import ReportMetadata
from powerpy.schemas.fluxes import LaunchConfig
from powerpy.schemas._common import Phase
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.environment import Environment
from powerpy.simulation.pipeline import environment_for_phase
from powerpy.solve.thermal import solve_panel, solve_thermal
from powerpy.analysis.power_budget import (
    DEFAULT_ORBIT, PowerBudget, compute_power_budget,
)
from powerpy.schemas.mission import MissionOrbit

AM0 = 1367.0  # solar irradiance at 1 AU [W/m^2]


# ---------------------------------------------------------------- cases
@dataclass(frozen=True)
class ThermalCase:
    label: str
    phase: Phase
    launch_config: LaunchConfig
    season: float = 1.0


@dataclass(frozen=True)
class ThermalPoint:
    """Equilibrium result for one case (single representative cell)."""
    case: ThermalCase
    p_sun: float        # incident solar [W/m^2]
    p_elec_w: float     # extracted electrical power per cell [W]
    t_front_c: float    # equilibrium front-face temperature [°C]
    t_rear_c: float


@dataclass
class HotSpot:
    nominal_c: float     # healthy cell temperature [°C]
    failed_c: float      # failed (open-bypass) cell temperature [°C]
    delta_c: float       # failed - nominal
    p_dissipated_w: float
    t_limit_c: float
    margin_c: float      # t_limit - failed  (>0 = safe)


@dataclass
class ThermalReportData:
    substrate: Substrate
    inputs: dict
    points: list                  # list[ThermalPoint]
    panel_case_label: str
    panel_grid_c: np.ndarray      # (nrows, ncols) front temperatures [°C]
    hotspot: HotSpot
    layout: object = None         # the PanelLayout used (for the layout figure)
    power_budget: PowerBudget | None = None


# ---------------------------------------------------------------- helpers
def cell_optics(md: ReportMetadata):
    """(alpha_front, epsilon_front, area_m2) taken from the cell JSON."""
    e = md.cell.electrical
    return float(e.alpha), float(e.epsilon), float(e.area_m2)


def p_elec_per_cell(md: ReportMetadata, env: Environment) -> float:
    """Extracted MPP electrical power of one cell at this environment [W].

    This is the power leaving the cell as electricity (a cooling term in the
    heat balance).
    """
    cell = CellModel(md.cell)
    cell.apply(env)
    isc, imp, vmp, voc = cell.operating_points()
    return float(imp * vmp)


def equilibrium_point(md: ReportMetadata, sub: Substrate,
                      case: ThermalCase, *,
                      orbit: MissionOrbit = DEFAULT_ORBIT,
                      efficiency: float = 0.30) -> ThermalPoint:
    """Steady-state temperature of one representative cell for ``case``."""
    env = environment_for_phase(
        md, phase=case.phase, launch_config=case.launch_config,
        season=case.season)
    alpha_f, eps_f, area = cell_optics(md)
    p_sun = AM0 * case.season
    p_elec = p_elec_per_cell(md, env)
    budget = compute_power_budget(orbit, season=case.season,
                                  efficiency=efficiency)

    res = solve_thermal(
        area=area,
        alpha_front=alpha_f, alpha_rear=sub.alpha_rear,
        epsilon_front=eps_f, epsilon_rear=sub.epsilon_rear,
        c_cond=sub.c_cond,
        p_sun=p_sun, p_albedo=budget.albedo_w_m2, p_ir=budget.ir_w_m2,
        p_elec=p_elec,
    )
    return ThermalPoint(
        case=case, p_sun=p_sun, p_elec_w=p_elec,
        t_front_c=float(np.ravel(res.t_front_c)[0]),
        t_rear_c=float(np.ravel(res.t_rear_c)[0]),
    )


def cell_palette(md: ReportMetadata, sub: Substrate) -> dict:
    """Palette with a cell key ``C`` and a bare/no-SCA key ``.``.

    Cell tiles take the cell-JSON optics; bare tiles take the substrate optics
    and generate no power (so they run hotter -- and warm their neighbours).
    """
    alpha_f, eps_f, _ = cell_optics(md)
    return {
        "C": {"is_cell": True,
              "alpha_front": alpha_f, "alpha_rear": sub.alpha_rear,
              "epsilon_front": eps_f, "epsilon_rear": sub.epsilon_rear},
        ".": {"is_cell": False, "name": "bare",
              "alpha_front": sub.alpha_front, "alpha_rear": sub.alpha_rear,
              "epsilon_front": sub.epsilon_front, "epsilon_rear": sub.epsilon_rear},
    }


def load_layout_grid(path) -> list:
    """Read the ``layout`` rows (list of 'C'/'.' strings) from a layout JSON."""
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["layout"]


def panel_from_grid(md: ReportMetadata, sub: Substrate, rows):
    """Build a PanelLayout from a grid of 'C' (cell) / '.' (bare) rows."""
    _, _, area = cell_optics(md)
    pitch_mm = float(np.sqrt(area) * 1000.0)
    layout = _layout_from_dict({
        "name": "panel", "pitch_mm": pitch_mm,
        "palette": cell_palette(md, sub), "layout": rows})
    return layout, area


def _uniform_panel(md: ReportMetadata, sub: Substrate, n_rows: int, n_cols: int):
    return panel_from_grid(md, sub, [" ".join(["C"] * n_cols)
                                     for _ in range(n_rows)])


def hotspot_case(md: ReportMetadata, sub: Substrate, case: ThermalCase,
                 *, layout=None, area=None, n_rows: int = 9, n_cols: int = 9,
                 dissipation_multiple: float = 4.0,
                 t_limit_c: float = 150.0,
                 g_lat: float = 0.02,
                 orbit: MissionOrbit = DEFAULT_ORBIT,
                 efficiency: float = 0.30) -> tuple[HotSpot, np.ndarray]:
    """Failed open-bypass-diode hot spot, returned with the panel grid.

    A failed bypass diode leaves one cell reverse-biased: it stops generating
    and instead dissipates the string current the healthy cells push through it
    (the reverse-bias the user sketched).  We model that dissipation as
    ``dissipation_multiple`` times the cell's healthy power, solve the whole
    panel with lateral conduction, and return the :class:`HotSpot` summary and
    the temperature grid.  ``layout`` (with bare/no-SCA tiles) may be supplied;
    otherwise a uniform ``n_rows x n_cols`` cell panel is used.
    """
    if layout is None:
        layout, area = _uniform_panel(md, sub, n_rows, n_cols)
    env = environment_for_phase(
        md, phase=case.phase, launch_config=case.launch_config,
        season=case.season)
    p_cell = p_elec_per_cell(md, env)

    cells = np.nonzero(layout.prop_arrays()["generates_power"])[0]
    centre = int(cells[len(cells) // 2])   # a representative central cell
    p_elec = np.full(layout.n_tiles, p_cell)   # bare tiles auto-zeroed by solver
    p_dissip = dissipation_multiple * p_cell
    p_elec[centre] = -p_dissip   # negative = a dissipating (reverse-biased) cell

    budget = compute_power_budget(orbit, season=case.season,
                                  efficiency=efficiency)
    res = solve_panel(
        layout, p_sun=AM0 * case.season,
        p_albedo=budget.albedo_w_m2, p_ir=budget.ir_w_m2,
        p_elec=p_elec, c_cond=sub.c_cond, g_lat=g_lat, area=area,
    )
    grid = np.asarray(res.t_front_c)
    failed_c = float(grid.flat[centre])
    nominal_c = float(grid.flat[int(cells[0])])   # a healthy cell
    hot = HotSpot(
        nominal_c=nominal_c, failed_c=failed_c,
        delta_c=failed_c - nominal_c, p_dissipated_w=p_dissip,
        t_limit_c=t_limit_c, margin_c=t_limit_c - failed_c,
    )
    return hot, grid


# ---------------------------------------------------------------- top level
def run_thermal_report(md: ReportMetadata, cases: list[ThermalCase], *,
                       substrate: Substrate | str = "FSP-SFLA",
                       layout_file: str | None = None,
                       layout=None,
                       t_limit_c: float = 150.0,
                       efficiency: float = 0.30) -> ThermalReportData:
    """Compute every thermal-report quantity for the given cases.

    ``layout_file`` (a layout JSON with a 'C'/'.' grid) declares where SCAs and
    bare/no-SCA sections are; the hot-spot/heat-map run on that panel.  Without
    it a uniform cell panel is used.  ``layout`` lets a caller pass an
    already-built :class:`PanelLayout` directly (e.g. a grid-as-single-source
    panel that also drives the electrical report) -- it takes precedence over
    ``layout_file``.
    """
    sub = (substrate if isinstance(substrate, Substrate)
           else load_substrate(substrate))
    orbit = md.mission_orbit if md.mission_orbit is not None else DEFAULT_ORBIT
    alpha_f, eps_f, area = cell_optics(md)

    if layout is None and layout_file is not None:
        layout, area = panel_from_grid(md, sub, load_layout_grid(layout_file))

    points = [equilibrium_point(md, sub, c, orbit=orbit, efficiency=efficiency)
              for c in cases]

    # heat-map + hot spot use the hottest case (largest equilibrium T); a
    # single panel solve (with one failed cell) feeds both the map and table.
    ref = max(points, key=lambda p: p.t_front_c).case if points else cases[0]
    hot, grid = hotspot_case(md, sub, ref, layout=layout, area=area,
                             t_limit_c=t_limit_c, orbit=orbit,
                             efficiency=efficiency)

    inputs = {
        "cell_alpha": alpha_f,
        "cell_epsilon": eps_f,
        "cell_area_m2": area,
        "substrate_name": sub.name,
        "substrate_alpha_rear": sub.alpha_rear,
        "substrate_epsilon_rear": sub.epsilon_rear,
        "substrate_conductivity": sub.conductivity,
        "substrate_thickness_m": sub.thickness,
        "substrate_c_cond": sub.c_cond,
        "am0_w_m2": AM0,
    }
    power_budget = compute_power_budget(orbit, season=ref.season,
                                        efficiency=efficiency)
    return ThermalReportData(
        substrate=sub, inputs=inputs, points=points,
        panel_case_label=ref.label, panel_grid_c=grid, hotspot=hot,
        layout=layout,
        power_budget=power_budget,
    )
