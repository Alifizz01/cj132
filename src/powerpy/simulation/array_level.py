"""Array-level model -- panels in PARALLEL -- and the tree builder.

:class:`ArrayModel` is the single top-level object handed to the report
and the energy balance.  :func:`build_from_report` assembles the whole
cell -> string -> section -> panel -> array tree from a loaded
:class:`~powerpy.schemas.ReportMetadata`.
"""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from powerpy.schemas import ReportMetadata
from powerpy.simulation.base import SimNode
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.combine import combine_parallel
from powerpy.simulation.environment import Environment
from powerpy.simulation.panel_level import PanelModel
from powerpy.simulation.section_level import SectionModel
from powerpy.simulation.string_level import StringModel


class ArrayModel(SimNode):
    """Panels in parallel -- the whole solar array."""

    def __init__(self, panels: list[PanelModel],
                 name: str = "array") -> None:
        if not panels:
            raise ValueError("ArrayModel: an array needs >= 1 panel")
        self.panels = panels
        self.name = name

    @classmethod
    def from_panels(cls, panels: list[PanelModel],
                    name: str = "array") -> "ArrayModel":
        return cls(list(panels), name)

    def apply(self, env: Environment) -> None:
        for p in self.panels:
            p.apply(env)

    def iv_curve(self) -> tuple[np.ndarray, np.ndarray]:
        return combine_parallel([p.iv_curve() for p in self.panels])

    # convenience iterators
    def iter_sections(self):
        for p in self.panels:
            yield from p.sections


def build_from_report(
    report: ReportMetadata,
    *,
    block_diode_v_drop: float = 0.6,
    n_block_diodes: int = 1,
    string_series_resistance_ohm: float = 0.0,
    section_resistance_ohm: float = 0.0,
    iv_engine: str = "analytic",
) -> ArrayModel:
    """Assemble the full simulation tree from loaded report data.

    The block-diode drop and any harness resistance are framework-wide
    knobs here; you can override them per-string or per-section by
    constructing the tree manually if needed.  ``iv_engine`` selects the
    cell I-V model: ``"analytic"`` (default, no ngspice) or ``"ngspice"``
    (the vendored SPICE path, with automatic fallback to analytic).
    """
    prototype = CellModel(report.cell, iv_engine=iv_engine)
    layout = report.array_layout

    # group physical sections by their panel instance
    panels: dict[str, list[SectionModel]] = {}
    for phys in layout.physical_sections:
        st = phys.section_type
        string = StringModel.from_single_cell(
            prototype, st.n_sca_series_per_string,
            block_diode_v_drop=block_diode_v_drop,
            n_block_diodes=n_block_diodes,
            series_resistance_ohm=string_series_resistance_ohm,
            name=f"{phys.instance_id}.string")
        # per-section harness resistance (distance from the yoke); falls back to
        # the framework-wide knob when a section carries none.
        r_sec = phys.resistance_ohm or section_resistance_ohm
        section = SectionModel.from_single_string(
            string, st.n_strings_parallel,
            section_resistance_ohm=r_sec,
            name=phys.instance_id)
        panels.setdefault(phys.panel_id, []).append(section)

    panel_models = [PanelModel.from_sections(secs, name=panel_id)
                    for panel_id, secs in panels.items()]
    return ArrayModel.from_panels(panel_models)
