"""Assemble the simulation tree from a free-form CircuitLayout.

Reuses the existing Cell/String/Section/Panel/Array models, so all
curve-combination, environment and shunt-diode logic is unchanged.
"""
from __future__ import annotations

from powerpy.schemas.cell import CellParameters
from powerpy.schemas.circuit import CircuitLayout
from powerpy.simulation.array_level import ArrayModel
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.panel_level import PanelModel
from powerpy.simulation.section_level import SectionModel
from powerpy.simulation.string_level import StringModel


def build_array_from_circuit(
    cell_params: CellParameters,
    circuit: CircuitLayout,
    *,
    iv_engine: str = "analytic",
    string_shunt_vf: float | None = None,
) -> ArrayModel:
    """Build an :class:`ArrayModel` from a :class:`CircuitLayout`.

    ``string_shunt_vf`` is the forward drop of the string shunt diode (from the
    cell's ``string_diode``); it is applied to strings whose
    ``string_shunt_diode`` flag is True.
    """
    prototype = CellModel(cell_params, iv_engine=iv_engine)
    panels: dict[str, list[SectionModel]] = {}
    for sec in circuit.sections:
        strings = []
        for st in sec.strings:
            vf = string_shunt_vf if st.string_shunt_diode else None
            strings.append(StringModel.from_single_cell(
                prototype, st.n_series,
                block_diode_v_drop=st.block_diode_v_drop,
                n_block_diodes=st.n_block_diodes,
                series_resistance_ohm=st.series_resistance_ohm,
                shunt_diode_v_forward=vf,
                name="%s.%s" % (sec.id, st.id)))
        section = SectionModel.from_strings(
            strings, section_resistance_ohm=sec.resistance_ohm, name=sec.id)
        panels.setdefault(sec.panel, []).append(section)
    panel_models = [PanelModel.from_sections(secs, name=pid)
                    for pid, secs in panels.items()]
    return ArrayModel.from_panels(panel_models)
