"""String-level model -- cells wired in SERIES.

A string is N cells in series.  They share one current; their voltages
add.  A real string also carries a blocking diode (a small fixed
voltage drop on the string output) and a small series resistance.
Both are modelled as a post-shift on the combined I-V curve.
"""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from powerpy.simulation.base import SimNode
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.combine import combine_series
from powerpy.simulation.environment import Environment


class StringModel(SimNode):
    """N cells in series, plus optional blocking diode and harness R."""

    def __init__(self, cells: list[CellModel],
                 *,
                 block_diode_v_drop: float = 0.6,
                 n_block_diodes: int = 1,
                 series_resistance_ohm: float = 0.0,
                 name: str = "string") -> None:
        if not cells:
            raise ValueError("StringModel: a string needs at least one cell")
        self.cells = cells
        self.block_diode_v_drop = float(block_diode_v_drop)
        self.n_block_diodes = int(n_block_diodes)
        self.series_resistance_ohm = float(series_resistance_ohm)
        self.name = name

    # ----- factories -----
    @classmethod
    def from_single_cell(cls, cell: CellModel, n_series: int,
                         **kwargs) -> "StringModel":
        if n_series < 1:
            raise ValueError("from_single_cell: n_series must be >= 1")
        return cls([deepcopy(cell) for _ in range(n_series)], **kwargs)

    @classmethod
    def from_cells(cls, cells: list[CellModel], **kwargs) -> "StringModel":
        return cls(list(cells), **kwargs)

    # ----- SimNode -----
    def apply(self, env: Environment) -> None:
        for cell in self.cells:
            cell.apply(env)

    def iv_curve(self) -> tuple[np.ndarray, np.ndarray]:
        v, i = combine_series([c.iv_curve() for c in self.cells])
        # drop the block-diode voltage and IR drop
        v_drop = (self.block_diode_v_drop * self.n_block_diodes
                  + i * self.series_resistance_ohm)
        v_out = v - v_drop
        # clip non-physical negative voltage region
        mask = v_out >= 0
        return v_out[mask], i[mask]
