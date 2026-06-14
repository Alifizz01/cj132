"""Simulation results -- the immutable output of an analysis run.

A :class:`SimulationResults` is what the simulation layer hands to the
render layer. It is pure data: no methods that compute, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass

from powerpy.simulation.base import SimNode
from powerpy.simulation.environment import Environment


@dataclass(frozen=True)
class LevelResult:
    """The performance summary of one node in the tree."""

    name: str
    isc: float          # A
    voc: float          # V
    v_mp: float         # V
    i_mp: float         # A
    p_mp: float         # W


@dataclass(frozen=True)
class SimulationResults:
    """The full result of one analysis run, at one environment."""

    environment: Environment
    array: LevelResult
    panels: tuple[LevelResult, ...]
    sections: tuple[LevelResult, ...]

    @property
    def array_power_w(self) -> float:
        return self.array.p_mp


def summarize(node: SimNode) -> LevelResult:
    """Reduce one SimNode to its :class:`LevelResult`."""
    v_mp, i_mp, p_mp = node.calc_mp()
    return LevelResult(
        name=node.name,
        isc=node.calc_isc(),
        voc=node.calc_voc(),
        v_mp=v_mp,
        i_mp=i_mp,
        p_mp=p_mp,
    )
