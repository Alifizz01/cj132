"""The SimNode interface — one contract for every level of the array.

cell -> string -> section -> panel -> array. Each level implements the
*same* interface, so a parent never needs to know what kind of children
it has: it just asks each child for an I-V curve and combines them.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from powerpy.simulation.environment import Environment


class SimNode(ABC):
    """A node in the array composition tree.

    Subclasses MUST implement :meth:`iv_curve` and :meth:`apply`.
    Everything else (single-point current, Isc, Voc, max power) is
    derived from the I-V curve and provided here once.
    """

    name: str

    # ---- the two things every level must define -----------------------
    @abstractmethod
    def iv_curve(self) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(voltage, current)`` arrays for this node.

        Voltage is ascending from 0; current is descending from Isc
        towards 0 at Voc.
        """

    @abstractmethod
    def apply(self, env: Environment) -> None:
        """Push an operating environment down to every leaf cell."""

    # ---- derived, shared by every level -------------------------------
    def current_at_voltage(self, v: float) -> float:
        """Current drawn from this node at terminal voltage ``v``."""
        vv, ii = self.iv_curve()
        return float(np.interp(v, vv, ii))

    def calc_isc(self) -> float:
        """Short-circuit current (current at V = 0)."""
        vv, ii = self.iv_curve()
        return float(np.interp(0.0, vv, ii))

    def calc_voc(self) -> float:
        """Open-circuit voltage (voltage at I = 0)."""
        vv, ii = self.iv_curve()
        # current is descending, so reverse both for an ascending x-axis
        return float(np.interp(0.0, ii[::-1], vv[::-1]))

    def calc_mp(self) -> tuple[float, float, float]:
        """Maximum power point as ``(v_mp, i_mp, p_mp)``."""
        vv, ii = self.iv_curve()
        power = vv * ii
        k = int(np.argmax(power))
        return float(vv[k]), float(ii[k]), float(power[k])
