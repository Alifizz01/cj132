"""Series and parallel combination of I-V curves.

Every join in the array tree is one of two rules:

  * SERIES   (cells inside a string)  -- same current, voltages add.
  * PARALLEL (strings, sections, ...) -- same voltage, currents add.

Both live here, once, so every composite level is just a few lines.
"""
from __future__ import annotations

import numpy as np

Curve = tuple[np.ndarray, np.ndarray]


def _voc_of(v: np.ndarray, i: np.ndarray) -> float:
    """Open-circuit voltage of one curve (voltage where current hits 0)."""
    return float(np.interp(0.0, i[::-1], v[::-1]))


def _isc_of(v: np.ndarray, i: np.ndarray) -> float:
    """Short-circuit current of one curve (current at V = 0)."""
    return float(np.interp(0.0, v, i))


def combine_series(curves: list[Curve], n: int = 400) -> Curve:
    """Combine curves in SERIES.

    Series elements share one current; their voltages add. The combined
    curve is limited by the smallest Isc among the children.
    """
    if not curves:
        raise ValueError("combine_series: no curves given")

    isc_min = min(_isc_of(v, i) for v, i in curves)
    i_grid = np.linspace(0.0, isc_min, n)

    v_total = np.zeros_like(i_grid)
    for v, i in curves:
        # invert each curve to V(I); current is descending, so reverse
        v_total += np.interp(i_grid, i[::-1], v[::-1])

    # return ascending-voltage order
    return v_total[::-1], i_grid[::-1]


def combine_parallel(curves: list[Curve], n: int = 400) -> Curve:
    """Combine curves in PARALLEL.

    Parallel elements share one voltage; their currents add. The
    combined curve is limited by the smallest Voc among the children.
    """
    if not curves:
        raise ValueError("combine_parallel: no curves given")

    voc_min = min(_voc_of(v, i) for v, i in curves)
    v_grid = np.linspace(0.0, voc_min, n)

    i_total = np.zeros_like(v_grid)
    for v, i in curves:
        i_total += np.interp(v_grid, v, i)

    return v_grid, i_total
