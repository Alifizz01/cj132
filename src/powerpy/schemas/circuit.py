"""Free-form electrical circuit layout (array -> sections -> strings -> cells).

A separate, fully-parameterized circuit specification, decoupled from the
thermal grid. Sections combine in parallel (within a panel, and panels in
parallel across the array); strings combine in parallel within a section; cells
combine in series within a string.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class CircuitString:
    """One string: ``n_series`` cells in series, plus per-string options."""
    id: str
    n_series: int
    series_resistance_ohm: float = 0.0
    block_diode_v_drop: float = 0.6
    n_block_diodes: int = 1
    string_shunt_diode: bool = True

    def __post_init__(self):
        if not self.id:
            raise ValueError("CircuitString.id must be non-empty")
        if self.n_series < 1:
            raise ValueError(
                "CircuitString %r: n_series must be >= 1, got %r"
                % (self.id, self.n_series))
        if self.series_resistance_ohm < 0 or self.block_diode_v_drop < 0:
            raise ValueError("CircuitString %r: resistances/drops must be >= 0" % self.id)
        if self.n_block_diodes < 0:
            raise ValueError("CircuitString %r: n_block_diodes must be >= 0" % self.id)


@dataclass(frozen=True)
class CircuitSection:
    """A parallel group of strings on one panel."""
    id: str
    strings: Tuple[CircuitString, ...]
    panel: str = "panel_1"
    resistance_ohm: float = 0.0

    def __post_init__(self):
        if not self.id:
            raise ValueError("CircuitSection.id must be non-empty")
        if not self.strings:
            raise ValueError("CircuitSection %r: needs >= 1 string" % self.id)
        if self.resistance_ohm < 0:
            raise ValueError("CircuitSection %r: resistance_ohm must be >= 0" % self.id)
        ids = [s.id for s in self.strings]
        if len(set(ids)) != len(ids):
            raise ValueError("CircuitSection %r: duplicate string ids %s" % (self.id, ids))


@dataclass(frozen=True)
class CircuitLayout:
    """The whole circuit: sections combined in parallel (grouped by panel)."""
    name: str
    sections: Tuple[CircuitSection, ...]

    def __post_init__(self):
        if not self.sections:
            raise ValueError("CircuitLayout: needs >= 1 section")
        ids = [s.id for s in self.sections]
        if len(set(ids)) != len(ids):
            raise ValueError("CircuitLayout: duplicate section ids %s" % ids)
