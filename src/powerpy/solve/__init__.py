# -*- coding: utf-8 -*-
"""Solvers: the unified 2-node thermal solver and the electro-thermal coupling loop."""
from .thermal import (
    solve_thermal, solve_panel, solve_thermal_for_substrate, lateral_conductance,
    ThermalResult, PanelThermalResult, SIGMA, T_ZERO_C, T_SPACE,
)
from .coupling import couple, CoupledResult
from .electrical import (
    Solution, ngspice_runner, per_cell_vi, per_cell_power, make_power_fn,
)
from .transient import (
    solve_transient, TransientResult, areal_heat_capacity, time_to_threshold,
)

__all__ = [
    "solve_thermal", "solve_panel", "solve_thermal_for_substrate", "lateral_conductance",
    "ThermalResult", "PanelThermalResult", "SIGMA", "T_ZERO_C", "T_SPACE",
    "couple", "CoupledResult",
    "Solution", "ngspice_runner", "per_cell_vi", "per_cell_power", "make_power_fn",
    "solve_transient", "TransientResult", "areal_heat_capacity", "time_to_threshold",
]
