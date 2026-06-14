"""Pure-math analysis layer.

Takes a loaded :class:`ReportMetadata` and produces
:class:`SimulationResults`.  Every model here is pure behaviour: it
wraps the frozen schema objects and computes -- no file I/O, no
rendering.

The array is modelled as a composition tree, one interface at every
level (see :class:`SimNode`)::

    cell -> string -> section -> panel -> array

Typical use::

    from powerpy.simulation import (
        build_from_report, Environment, run, evaluate, AnalysisCase
    )
    from powerpy.schemas import Phase, LaunchConfig

    cases = [
        AnalysisCase("EOL_SS_dual", Phase.END_OF_LIFE,
                     LaunchConfig.DUAL, temperature_c=51.1, season=0.967),
        AnalysisCase("EOL_VEX_dual", Phase.END_OF_LIFE,
                     LaunchConfig.DUAL, temperature_c=51.1, season=1.008),
    ]
    results = evaluate(report, cases)
"""
from __future__ import annotations

from powerpy.simulation.array_level import ArrayModel, build_from_report
from powerpy.simulation.base import SimNode
from powerpy.simulation.cell_level import (
    CellModel,
    DiodeParams,
    fit_rseries,
    single_diode_iv,
)
from powerpy.simulation.combine import combine_parallel, combine_series
from powerpy.simulation.environment import Environment
from powerpy.simulation.panel_level import PanelModel
from powerpy.simulation.pipeline import (
    AnalysisCase,
    CaseResult,
    CompliancePoint,
    environment_for_phase,
    evaluate,
    run,
)
from powerpy.simulation.results import (
    LevelResult,
    SimulationResults,
    summarize,
)
from powerpy.simulation.section_level import SectionModel
from powerpy.simulation.solver import SimulationError
from powerpy.simulation.string_level import StringModel

__all__ = [
    # core interfaces
    "SimNode", "Environment",
    # models
    "CellModel", "StringModel", "SectionModel", "PanelModel", "ArrayModel",
    # diode helpers
    "DiodeParams", "fit_rseries", "single_diode_iv",
    # combine math
    "combine_series", "combine_parallel",
    # results
    "LevelResult", "SimulationResults", "summarize",
    # high-level pipeline
    "build_from_report", "run", "evaluate",
    "environment_for_phase",
    "AnalysisCase", "CaseResult", "CompliancePoint",
    # errors
    "SimulationError",
]
