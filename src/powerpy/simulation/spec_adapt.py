"""Adapters: build an ArraySpec from the existing inputs (grid / report / circuit).

Phase 0 keeps behaviour identical -- the section/circuit adapters re-express
today's inputs as a position-mapped :class:`ArraySpec` so the spec-built tree
reproduces the LIVE builders' analytic IV.  The grid adapter has no live
electrical builder to regress against (the grid feeds the thermal solver), so
its gate is structural-equivalence only.
"""
from __future__ import annotations

from powerpy.config.layout import PanelLayout
from powerpy.schemas.panel_circuit import (
    StringSpec, SectionSpec, PanelSpec, ArraySpec,
)


def adapt_grid(layout: PanelLayout, *, panel_id: str = "panel_1") -> ArraySpec:
    """Express a :class:`PanelLayout` grid as an :class:`ArraySpec`.

    Faithful mirror of :func:`powerpy.simulation.grid_build.build_array_from_grid`:
    grouping is delegated to :meth:`PanelLayout.cell_strings`, which **skips
    non-cell (bare / diode) tiles** and falls back to a tile's palette key when its
    ``string`` tag is absent. Strings sharing a ``block`` tag are the parallel
    strings of one section, in row-major first-appearance order. Per-string and
    per-block electrical options (``series_resistance_ohm``, ``block_diode_v_drop``,
    ``n_block_diodes``, ``string_shunt_diode``, section ``resistance_ohm``) come
    from ``layout.circuit_params``, defaulting to the schema defaults when absent.

    Note: the resulting spec covers only the grid's CELL tiles (bare tiles carry
    no electrical power). A caller that needs a total tile bijection -- e.g.
    per-cell thermal -- must run ``validate_bijection`` against an all-cell grid.
    """
    circuit_params = getattr(layout, "circuit_params", {}) or {}
    strings_idx, string_block = layout.cell_strings()
    if not strings_idx:
        raise ValueError("adapt_grid: grid has no cell tiles to wire into strings")

    # one StringSpec per string (carrying its circuit params), grouped into
    # sections by block, in row-major first-appearance order.
    section_strings: dict[str, list[StringSpec]] = {}
    section_order: list[str] = []
    for sid, idxs in strings_idx.items():
        p = circuit_params.get(sid, {})
        string = StringSpec(
            id=str(sid),
            members=tuple(idxs),
            series_resistance_ohm=float(p.get("series_resistance_ohm", 0.0)),
            block_diode_v_drop=float(p.get("block_diode_v_drop", 0.6)),
            n_block_diodes=int(p.get("n_block_diodes", 1)),
            string_shunt_diode=bool(p.get("string_shunt_diode", True)))
        blk = string_block[sid]
        if blk not in section_strings:
            section_strings[blk] = []
            section_order.append(blk)
        section_strings[blk].append(string)

    sections = tuple(
        SectionSpec(
            id=str(blk),
            strings=tuple(section_strings[blk]),
            panel=panel_id,
            resistance_ohm=float(circuit_params.get(blk, {}).get("resistance_ohm", 0.0)))
        for blk in section_order
    )
    panel = PanelSpec(id=panel_id, sections=sections)
    return ArraySpec(name=layout.name or "grid", panels=(panel,))


from powerpy.schemas.layout import ArrayLayout
from powerpy.schemas.circuit import CircuitLayout


def adapt_sections(layout: ArrayLayout, *,
                   string_series_resistance_ohm: float = 0.0,
                   section_resistance_ohm: float = 0.0) -> ArraySpec:
    """Express the report's :class:`ArrayLayout` as an :class:`ArraySpec`.

    Mirrors :func:`powerpy.simulation.array_level.build_from_report`: each
    physical section expands to ``n_strings_parallel`` strings of
    ``n_sca_series_per_string`` consecutive tile indices.
    """
    next_idx = 0
    panels: dict[str, list[SectionSpec]] = {}
    panel_order: list[str] = []
    for phys in layout.physical_sections:
        st = phys.section_type
        strings = []
        for k in range(st.n_strings_parallel):
            members = tuple(range(next_idx, next_idx + st.n_sca_series_per_string))
            next_idx += st.n_sca_series_per_string
            strings.append(StringSpec(
                id="%s.string%d" % (phys.instance_id, k),
                members=members,
                series_resistance_ohm=string_series_resistance_ohm))
        r_sec = phys.resistance_ohm or section_resistance_ohm
        section = SectionSpec(id=phys.instance_id, strings=tuple(strings),
                              panel=phys.panel_id, resistance_ohm=r_sec)
        if phys.panel_id not in panels:
            panels[phys.panel_id] = []
            panel_order.append(phys.panel_id)
        panels[phys.panel_id].append(section)
    panel_specs = tuple(
        PanelSpec(id=pid, sections=tuple(panels[pid])) for pid in panel_order
    )
    return ArraySpec(name="array_layout", panels=panel_specs)


def adapt_circuit(circuit: CircuitLayout) -> ArraySpec:
    """Express a free-form :class:`CircuitLayout` as an :class:`ArraySpec`.

    Mirrors :func:`powerpy.simulation.circuit_build.build_array_from_circuit`:
    each string's ``n_series`` becomes ``n_series`` consecutive tile indices,
    with the per-string electrical knobs carried straight across.
    """
    next_idx = 0
    panels: dict[str, list[SectionSpec]] = {}
    panel_order: list[str] = []
    for sec in circuit.sections:
        strings = []
        for st in sec.strings:
            members = tuple(range(next_idx, next_idx + st.n_series))
            next_idx += st.n_series
            strings.append(StringSpec(
                id=st.id, members=members,
                series_resistance_ohm=st.series_resistance_ohm,
                block_diode_v_drop=st.block_diode_v_drop,
                n_block_diodes=st.n_block_diodes,
                string_shunt_diode=st.string_shunt_diode))
        section = SectionSpec(id=sec.id, strings=tuple(strings),
                              panel=sec.panel, resistance_ohm=sec.resistance_ohm)
        if sec.panel not in panels:
            panels[sec.panel] = []
            panel_order.append(sec.panel)
        panels[sec.panel].append(section)
    panel_specs = tuple(
        PanelSpec(id=pid, sections=tuple(panels[pid])) for pid in panel_order
    )
    return ArraySpec(name=circuit.name, panels=panel_specs)
