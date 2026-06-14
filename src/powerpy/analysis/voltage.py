# -*- coding: utf-8 -*-
"""Series voltage-balance analysis: can the panel's net voltage reach ZERO?

In a series path the array's terminal voltage is the ALGEBRAIC sum of every
segment's voltage: healthy segments add a positive (forward) voltage, reverse-
biased ones add a negative voltage. When the negatives cancel the positives the
array reads ~0 V -- a dangerous *hidden* state: no bus output, yet cells may sit
at large reverse bias (hot-spot risk) while the panel looks "off".

Two models (compare them):
  * raw (no/failed diodes): each failed cell holds a reverse voltage ``v_rev``;
    a handful can cancel many forward cells.
  * diode-clamped: a bypassed segment is held at only the diode drop ``v_diode``
    (~0.7 V), so cancelling the big forward voltage needs an impossible number of
    bypassed blocks -- i.e. **bypass diodes prevent the zero-voltage cancellation**.

Representative constant-voltage model (no IV curve / no ngspice needed): a series
path through ``n_blocks`` series blocks of ``n_series`` SCAs each has
``N = n_blocks*n_series`` cells. Standalone & tested.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


def series_path_length(n_blocks: int, n_series: int) -> int:
    """Number of SCAs in series along the array's output path."""
    return int(n_blocks) * int(n_series)


def panel_voltage_raw(n_blocks: int, n_series: int, n_failed: int, *,
                      v_fwd: float = 2.3, v_rev: float = 2.3) -> float:
    """Array voltage (V) with ``n_failed`` reverse-biased SCAs on the series path:
    ``(N - n_failed)*v_fwd - n_failed*v_rev``. ``v_rev`` = reverse magnitude a
    failed cell sustains (>= v_fwd if driven hard)."""
    N = series_path_length(n_blocks, n_series)
    k = max(0, min(N, int(n_failed)))
    return (N - k) * v_fwd - k * v_rev


def panel_voltage_diode(n_blocks: int, n_series: int, n_bypassed_blocks: int, *,
                        v_fwd: float = 2.3, v_diode: float = 0.7) -> float:
    """Array voltage (V) when whole blocks are bypassed (diode clamps each
    bypassed block to ``-v_diode`` instead of its ``+n_series*v_fwd``)."""
    nb = max(0, min(int(n_blocks), int(n_bypassed_blocks)))
    return (n_blocks - nb) * n_series * v_fwd - nb * v_diode


def is_zero(v_array: float, v_forward_max: float, rel: float = 0.02) -> bool:
    """True if |V_array| is within ``rel`` of the all-healthy forward voltage
    (i.e. the output has effectively collapsed)."""
    return abs(v_array) <= rel * abs(v_forward_max)


@dataclass
class ZeroVoltageReport:
    forward_max_v: float                 # all-healthy array voltage
    raw_no_diode: Dict = field(default_factory=dict)
    diode_clamped: Dict = field(default_factory=dict)


def find_zero_voltage_raw(n_blocks: int, n_series: int, *,
                          v_fwd: float = 2.3, v_rev: float = 2.3) -> Dict:
    """Smallest reverse-biased-cell count that nulls the array (raw model).
    ``(N-k)*v_fwd = k*v_rev`` -> ``k = N*v_fwd/(v_fwd+v_rev)``."""
    N = series_path_length(n_blocks, n_series)
    k_exact = N * v_fwd / (v_fwd + v_rev)
    k_int = int(round(k_exact))
    return {
        "n_series_path": N,
        "k_exact": round(k_exact, 3),
        "n_failed": k_int,
        "fraction_failed": round(k_exact / N, 4),
        "v_at_n_failed": round(panel_voltage_raw(n_blocks, n_series, k_int, v_fwd=v_fwd, v_rev=v_rev), 4),
        "achievable": 0.0 <= k_exact <= N,
    }


def find_zero_voltage_diode(n_blocks: int, n_series: int, *,
                            v_fwd: float = 2.3, v_diode: float = 0.7) -> Dict:
    """Can bypassing whole blocks null the array? (Scan 0..n_blocks bypassed.)
    Normally NO -- the clamp is tiny vs the forward voltage."""
    best_nb, best_v = 0, panel_voltage_diode(n_blocks, n_series, 0, v_fwd=v_fwd, v_diode=v_diode)
    for nb in range(n_blocks + 1):
        v = panel_voltage_diode(n_blocks, n_series, nb, v_fwd=v_fwd, v_diode=v_diode)
        if abs(v) < abs(best_v):
            best_nb, best_v = nb, v
    reachable = abs(best_v) <= v_diode
    return {
        "closest_n_bypassed": best_nb,
        "min_abs_v": round(abs(best_v), 4),
        "zero_reachable": reachable,
        "note": ("a clamp lands near 0" if reachable
                 else "bypass diodes PREVENT zero-cancellation (clamp << forward voltage)"),
    }


def compare_models(n_blocks: int, n_series: int, *, v_fwd: float = 2.3,
                   v_rev: float = 2.3, v_diode: float = 0.7) -> ZeroVoltageReport:
    """Both models side-by-side: with vs without bypass diodes."""
    return ZeroVoltageReport(
        forward_max_v=round(series_path_length(n_blocks, n_series) * v_fwd, 3),
        raw_no_diode=find_zero_voltage_raw(n_blocks, n_series, v_fwd=v_fwd, v_rev=v_rev),
        diode_clamped=find_zero_voltage_diode(n_blocks, n_series, v_fwd=v_fwd, v_diode=v_diode),
    )
