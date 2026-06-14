# -*- coding: utf-8 -*-
"""Breakdown / melt criteria for a converged cell state.

A cell is flagged *destroyed* if EITHER criterion trips (the project's decision):

  1. temperature:    T_front >= t_limit_c            (e.g. aluminium-honeycomb limit)
  2. reverse power:  V < 0 and |V*I| >= p_rev_limit_w (driven hard into reverse bias)

Temperature captures the steady thermal outcome; reverse power captures the
electrical stress -- either can flag a failure the other misses, so we OR them.

Status: standalone (numpy only) -- pure and tested.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BreakdownReport:
    temperature_tripped: np.ndarray   # bool per cell
    reverse_power_tripped: np.ndarray # bool per cell
    destroyed: np.ndarray             # bool per cell (OR of the two)
    reverse_power_w: np.ndarray       # |V*I| where V<0 else 0 [W]

    @property
    def n_destroyed(self) -> int:
        return int(np.count_nonzero(self.destroyed))


def evaluate_breakdown(t_front_c, v, i, t_limit_c: float, p_rev_limit_w: float) -> BreakdownReport:
    """Apply both breakdown criteria elementwise over arrays (or scalars)."""
    t = np.asarray(t_front_c, dtype=float)
    V = np.asarray(v, dtype=float)
    I = np.asarray(i, dtype=float)

    temp = t >= t_limit_c
    p_rev = np.where(V < 0, np.abs(V * I), 0.0)
    rev = p_rev >= p_rev_limit_w
    return BreakdownReport(
        temperature_tripped=temp,
        reverse_power_tripped=rev,
        destroyed=np.logical_or(temp, rev),
        reverse_power_w=p_rev,
    )
