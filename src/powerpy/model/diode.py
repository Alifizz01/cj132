# -*- coding: utf-8 -*-
"""Bypass-diode clamping — the real hot-spot mitigator.

A bypass diode is wired across a *substring* of series cells. While the substring
generates, the diode is reverse-biased and off. If a cell in the substring fails
(or is shaded) and blocks the string current, the rest of the string drives the
substring into reverse; the diode then turns **on**, carries the current at its
forward drop, and **clamps** the substring voltage. That caps how negative the
failed cell's voltage can swing -- and therefore caps the reverse power (V*I) it
dissipates, which is what sets the hot-spot temperature.

Design consequence (the question this answers): the fewer cells a single bypass
diode protects, the smaller the worst-case reverse voltage across a failed cell,
and the cooler the hot-spot. "What diode spacing is safe?" becomes a number.

Model (clean, first-order). With a diode of forward drop ``v_forward`` across a
substring of ``cells_per_diode`` series cells, a single failed cell in that
substring is reverse-biased to at most::

    |V_failed| <= v_forward + (cells_per_diode - 1) * v_cell

With no diode (or one diode spanning the whole N-cell string) the failed cell
sees nearly the full live stack, |V| ~ (N - 1) * v_cell (e.g. ~20 V). The reverse
power is then |V_failed| * I, which feeds the thermal solver as a negative
``P_elec`` (heat in).

Standalone (stdlib only); tested.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BypassDiode:
    """A bypass diode characterised by its forward voltage drop (V)."""
    v_forward: float = 0.7          # ~0.7 V silicon; use ~0.3 for Schottky


def unprotected_reverse_voltage(n_series: int, v_cell: float) -> float:
    """Reverse voltage across one failed cell with NO bypass protection:
    the rest of the series string (n_series-1 live cells) drives it backwards."""
    return -max(0, n_series - 1) * v_cell


def clamped_reverse_voltage(cells_per_diode: int, v_cell: float,
                            diode: BypassDiode) -> float:
    """Reverse voltage across one failed cell inside a diode-protected substring
    of ``cells_per_diode`` series cells: bounded by the diode forward drop plus
    the (forward) drops of the other cells in that substring."""
    return -(diode.v_forward + max(0, cells_per_diode - 1) * v_cell)


def reverse_power(v: float, i: float) -> float:
    """Heat dissipated by a reverse-biased cell, |V*I| (W). Zero if not reverse."""
    return abs(v * i) if v < 0 else 0.0


def failed_cell_p_elec(i: float, *, n_series: int, v_cell: float,
                       diode: BypassDiode = None, cells_per_diode: int = None) -> float:
    """``P_elec`` (W, negative = dissipating heat) for a failed cell.

    With ``diode`` + ``cells_per_diode`` the reverse voltage is clamped; otherwise
    it is the unprotected full-string reverse voltage. The returned value is
    negative (heat into the cell) and is what you pass to the thermal solver /
    ``panel_study`` as the failed tile's power.
    """
    if diode is not None and cells_per_diode is not None:
        v = clamped_reverse_voltage(cells_per_diode, v_cell, diode)
    else:
        v = unprotected_reverse_voltage(n_series, v_cell)
    return -reverse_power(v, i)      # negative: dissipated as heat


def spacing_scan(i: float, v_cell: float, n_series: int, diode: BypassDiode,
                 cells_per_diode_options):
    """For each candidate diode spacing, the failed-cell reverse voltage & power.

    Returns a list of dicts ``{cells_per_diode, v_reverse, p_reverse_w}`` plus the
    unprotected baseline (``cells_per_diode = None``) — a ready-made table for the
    "how close must the diodes be?" trade study.
    """
    out = [{
        "cells_per_diode": None,
        "v_reverse": unprotected_reverse_voltage(n_series, v_cell),
        "p_reverse_w": reverse_power(unprotected_reverse_voltage(n_series, v_cell), i),
    }]
    for cpd in cells_per_diode_options:
        v = clamped_reverse_voltage(cpd, v_cell, diode)
        out.append({"cells_per_diode": cpd, "v_reverse": v,
                    "p_reverse_w": reverse_power(v, i)})
    return out
