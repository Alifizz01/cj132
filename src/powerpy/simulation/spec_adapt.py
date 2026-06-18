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
