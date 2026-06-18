"""Assemble the simulation tree from a position-mapped ArraySpec (approach B).

One distinct :class:`CellModel` is created per tile index in each string's
``members`` (via :meth:`StringModel.from_cells`), so a per-cell condition can be
attached to each leaf without aliasing.  All curve-combination, environment and
shunt-diode logic is the existing tree's, unchanged.
"""
from __future__ import annotations

from powerpy.schemas.cell import CellParameters
from powerpy.schemas.panel_circuit import ArraySpec
from powerpy.simulation.array_level import ArrayModel
from powerpy.simulation.cell_condition import CellCondition
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.panel_level import PanelModel
from powerpy.simulation.section_level import SectionModel
from powerpy.simulation.string_level import StringModel


def build_array_from_spec(
    cell_params: CellParameters,
    spec: ArraySpec,
    *,
    iv_engine: str = "analytic",
    string_shunt_vf: float | None = None,
    conditions: dict[int, CellCondition] | None = None,
) -> ArrayModel:
    """Build an :class:`ArrayModel` from an :class:`ArraySpec`.

    Each tile index in a string's ``members`` becomes its own ``CellModel``.
    ``string_shunt_vf`` is the forward drop of the string shunt diode; it is
    applied to strings whose ``string_shunt_diode`` flag is True.  ``conditions``
    optionally maps a tile index -> :class:`CellCondition` (absent index uses the
    default no-op condition).
    """
    cond_map = conditions or {}
    panel_models = []
    for pan in spec.panels:
        sections = []
        for sec in pan.sections:
            strings = []
            for st in sec.strings:
                vf = string_shunt_vf if st.string_shunt_diode else None
                cells = [CellModel(cell_params, iv_engine=iv_engine,
                                   condition=cond_map.get(idx, CellCondition()))
                         for idx in st.members]
                strings.append(StringModel.from_cells(
                    cells,
                    block_diode_v_drop=st.block_diode_v_drop,
                    n_block_diodes=st.n_block_diodes,
                    series_resistance_ohm=st.series_resistance_ohm,
                    shunt_diode_v_forward=vf,
                    name="%s.%s" % (sec.id, st.id)))
            sections.append(SectionModel.from_strings(
                strings, section_resistance_ohm=sec.resistance_ohm, name=sec.id))
        panel_models.append(PanelModel.from_sections(sections, name=pan.id))
    return ArrayModel.from_panels(panel_models, name=spec.name)
