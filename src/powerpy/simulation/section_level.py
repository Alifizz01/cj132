"""Section-level model -- strings wired in PARALLEL.

A section is M strings in parallel.  They share one voltage; their
currents add.  An optional section-level series resistance is applied
as a post-shift on the combined I-V curve.
"""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from powerpy.simulation.base import SimNode
from powerpy.simulation.combine import combine_parallel
from powerpy.simulation.environment import Environment
from powerpy.simulation.string_level import StringModel


class SectionModel(SimNode):
    """M strings in parallel + optional section harness resistance."""

    def __init__(self, strings: list[StringModel],
                 *,
                 section_resistance_ohm: float = 0.0,
                 name: str = "section") -> None:
        if not strings:
            raise ValueError("SectionModel: a section needs >= 1 string")
        self.strings = strings
        self.section_resistance_ohm = float(section_resistance_ohm)
        self.name = name

    @classmethod
    def from_single_string(cls, string: StringModel, n_parallel: int,
                           **kwargs) -> "SectionModel":
        if n_parallel < 1:
            raise ValueError("from_single_string: n_parallel must be >= 1")
        # deepcopy so each string is an INDEPENDENT object
        # (the [obj] * n trap from the legacy code is fixed here)
        return cls([deepcopy(string) for _ in range(n_parallel)], **kwargs)

    @classmethod
    def from_strings(cls, strings: list[StringModel],
                     **kwargs) -> "SectionModel":
        return cls(list(strings), **kwargs)

    def apply(self, env: Environment) -> None:
        for s in self.strings:
            s.apply(env)

    def iv_curve(self) -> tuple[np.ndarray, np.ndarray]:
        v, i = combine_parallel([s.iv_curve() for s in self.strings])
        v_out = v - i * self.section_resistance_ohm
        mask = v_out >= 0
        return v_out[mask], i[mask]
