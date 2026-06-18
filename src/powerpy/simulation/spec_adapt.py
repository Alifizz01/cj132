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


def adapt_grid(layout: PanelLayout, *, panel_id: str = "panel_1",
               section_id: str = "sec_grid") -> ArraySpec:
    """Express a fully-tagged :class:`PanelLayout` grid as an :class:`ArraySpec`.

    Tiles sharing a ``string`` tag are wired in series in row-major
    (``flat_keys``) order.  Every tile is a cell that MUST belong to a string:
    an untagged tile (``TileType.string is None``) raises ``ValueError`` rather
    than being auto-grouped into a singleton (which could silently invent an
    unintended parallel-of-singletons topology).
    """
    keys = layout.flat_keys()
    palette = layout.palette
    groups: dict[str, list[int]] = {}
    order: list[str] = []
    for idx, key in enumerate(keys):
        tag = palette[key].string
        if tag is None:
            raise ValueError(
                "adapt_grid: tile %d (key %r) has no string tag; every tile "
                "must be wired into a string" % (idx, key))
        if tag not in groups:
            groups[tag] = []
            order.append(tag)
        groups[tag].append(idx)

    strings = tuple(
        StringSpec(id=str(gid), members=tuple(groups[gid])) for gid in order
    )
    section = SectionSpec(id=section_id, strings=strings, panel=panel_id)
    panel = PanelSpec(id=panel_id, sections=(section,))
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
