"""Assemble the simulation tree from a PanelLayout grid (the single source).

Cell tiles sharing a ``string`` tag are the cells of one series string; strings
sharing a ``block`` tag are in parallel (a block = a section). Per-string and
per-block electrical params come from the layout's ``circuit_params``. Reuses the
existing Cell/String/Section/Panel/Array models unchanged.
"""
from __future__ import annotations

from powerpy.schemas.cell import CellParameters
from powerpy.simulation.array_level import ArrayModel
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.panel_level import PanelModel
from powerpy.simulation.section_level import SectionModel
from powerpy.simulation.string_level import StringModel


def build_array_from_grid(
    cell_params: CellParameters,
    layout,
    circuit_params: dict | None = None,
    *,
    iv_engine: str = "analytic",
    string_shunt_vf: float | None = None,
) -> ArrayModel:
    """Build an :class:`ArrayModel` from a :class:`PanelLayout`.

    ``layout`` cell tiles carry ``string`` (series) and ``block`` (parallel
    section) tags. ``circuit_params`` (defaults to ``layout.circuit_params``)
    supplies per-string / per-block electrical options.
    """
    if circuit_params is None:
        circuit_params = getattr(layout, "circuit_params", {}) or {}

    prototype = CellModel(cell_params, iv_engine=iv_engine)
    strings_idx, string_block = layout.cell_strings()
    if not strings_idx:
        raise ValueError("grid has no cell tiles to build an electrical circuit from")

    blocks: dict[str, list] = {}
    for sid, idxs in strings_idx.items():
        p = circuit_params.get(sid, {})
        vf = string_shunt_vf if p.get("string_shunt_diode", True) else None
        string = StringModel.from_single_cell(
            prototype, len(idxs),
            block_diode_v_drop=float(p.get("block_diode_v_drop", 0.6)),
            n_block_diodes=int(p.get("n_block_diodes", 1)),
            series_resistance_ohm=float(p.get("series_resistance_ohm", 0.0)),
            shunt_diode_v_forward=vf,
            name=sid)
        blocks.setdefault(string_block[sid], []).append(string)

    sections = []
    for bid, strs in blocks.items():
        bp = circuit_params.get(bid, {})
        sections.append(SectionModel.from_strings(
            strs, section_resistance_ohm=float(bp.get("resistance_ohm", 0.0)), name=bid))

    panel = PanelModel.from_sections(sections, name=layout.name or "panel")
    return ArrayModel.from_panels([panel])
