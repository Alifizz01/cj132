"""Panel-level model -- sections wired in PARALLEL.

A panel carries its sections plus the substrate and thermal context.
The thermal coupling (operating temperature from an energy balance) is
a TODO -- see manual chapters 6 and 7.
"""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from powerpy.simulation.base import SimNode
from powerpy.simulation.combine import combine_parallel
from powerpy.simulation.environment import Environment
from powerpy.simulation.section_level import SectionModel


class PanelModel(SimNode):
    """Sections in parallel, on one substrate."""

    def __init__(self, sections: list[SectionModel],
                 name: str = "panel") -> None:
        if not sections:
            raise ValueError("PanelModel: a panel needs >= 1 section")
        self.sections = sections
        self.name = name
        # TODO: substrate properties (alpha/epsilon) and a thermal
        # solve that sets the Environment temperature -- manual ch.6-7.

    @classmethod
    def from_sections(cls, sections: list[SectionModel],
                      name: str = "panel") -> "PanelModel":
        """Build a panel from an explicit list of sections."""
        return cls(list(sections), name)

    @classmethod
    def from_single_section(cls, section: SectionModel, count: int,
                            name: str = "panel") -> "PanelModel":
        """Build a uniform panel by repeating one section ``count`` times."""
        if count < 1:
            raise ValueError("from_single_section: count must be >= 1")
        return cls([deepcopy(section) for _ in range(count)], name)

    def apply(self, env: Environment) -> None:
        for section in self.sections:
            section.apply(env)

    def iv_curve(self) -> tuple[np.ndarray, np.ndarray]:
        return combine_parallel([s.iv_curve() for s in self.sections])
