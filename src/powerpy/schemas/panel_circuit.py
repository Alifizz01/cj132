"""Position-mapped circuit spec (approach B): tile-index members per string.

Structural twin of :mod:`powerpy.schemas.circuit`, but a string lists the
ORDERED flat tile indices it wires in series (``members``) instead of a scalar
``n_series``.  This makes the cell <-> physical-position mapping explicit so a
per-cell condition (shade/life/failure) can be attached downstream.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StringSpec:
    """One string: ``members`` cells in series, plus per-string options."""
    id: str
    members: tuple[int, ...]
    series_resistance_ohm: float = 0.0
    block_diode_v_drop: float = 0.6
    n_block_diodes: int = 1
    string_shunt_diode: bool = True

    def __post_init__(self):
        if not self.id:
            raise ValueError("StringSpec.id must be non-empty")
        if not self.members:
            raise ValueError("StringSpec %r: needs >= 1 member" % self.id)
        if len(set(self.members)) != len(self.members):
            raise ValueError("StringSpec %r: duplicate tile indices %s"
                             % (self.id, self.members))
        if self.series_resistance_ohm < 0:
            raise ValueError("StringSpec %r: series_resistance_ohm must be >= 0"
                             % self.id)
        if self.block_diode_v_drop < 0:
            raise ValueError("StringSpec %r: block_diode_v_drop must be >= 0"
                             % self.id)
        if self.n_block_diodes < 0:
            raise ValueError("StringSpec %r: n_block_diodes must be >= 0" % self.id)


@dataclass(frozen=True)
class SectionSpec:
    """A parallel group of strings on one panel."""
    id: str
    strings: tuple[StringSpec, ...]
    panel: str = "panel_1"
    resistance_ohm: float = 0.0

    def __post_init__(self):
        if not self.id:
            raise ValueError("SectionSpec.id must be non-empty")
        if not self.strings:
            raise ValueError("SectionSpec %r: needs >= 1 string" % self.id)
        ids = [s.id for s in self.strings]
        if len(set(ids)) != len(ids):
            raise ValueError("SectionSpec %r: duplicate string ids %s"
                             % (self.id, ids))
        if self.resistance_ohm < 0:
            raise ValueError("SectionSpec %r: resistance_ohm must be >= 0" % self.id)


@dataclass(frozen=True)
class PanelSpec:
    """Sections combined in parallel on one panel."""
    id: str
    sections: tuple[SectionSpec, ...]

    def __post_init__(self):
        if not self.id:
            raise ValueError("PanelSpec.id must be non-empty")
        if not self.sections:
            raise ValueError("PanelSpec %r: needs >= 1 section" % self.id)
        ids = [s.id for s in self.sections]
        if len(set(ids)) != len(ids):
            raise ValueError("PanelSpec %r: duplicate section ids %s"
                             % (self.id, ids))


@dataclass(frozen=True)
class ArraySpec:
    """The whole array: panels combined in parallel."""
    name: str
    panels: tuple[PanelSpec, ...]

    def __post_init__(self):
        if not self.name:
            raise ValueError("ArraySpec.name must be non-empty")
        if not self.panels:
            raise ValueError("ArraySpec: needs >= 1 panel")
        ids = [p.id for p in self.panels]
        if len(set(ids)) != len(ids):
            raise ValueError("ArraySpec: duplicate panel ids %s" % ids)

    def all_members(self) -> list[int]:
        """Every string's ``members`` concatenated in panel->section->string order."""
        out: list[int] = []
        for panel in self.panels:
            for section in panel.sections:
                for string in section.strings:
                    out.extend(string.members)
        return out
