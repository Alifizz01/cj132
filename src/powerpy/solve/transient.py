# -*- coding: utf-8 -*-
"""Transient (time-domain) 2-node thermal solver.

The steady solver finds where heat-in = heat-out. The TRANSIENT solver watches
the temperature *evolve* by adding thermal mass: each node stores heat, so

    C * dT/dt = heat-in - heat-out = f(T, t)

(``C`` = heat capacity, J/K). At steady state dT/dt -> 0 -> f = 0, recovering the
steady answer. This lets us watch a hot-spot **climb** after a cell fails, and
the panel **cool** when it enters eclipse.

Integration is **backward (implicit) Euler**, which is unconditionally stable for
this stiff radiative+conduction system. Each step solves, per node (vectorised
over the array, no lateral coupling), the nonlinear system

    g(T) = C*(T - T_prev)/dt - f(T) = 0

with a few Newton iterations using the analytic 2x2 Jacobian (the steady Jacobian
plus C/dt on the diagonal). As dt -> infinity the step reduces to the steady
solve (a parity test pins this).

Standalone (numpy + the shared constants from solve/thermal).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    from .thermal import SIGMA, T_ZERO_C, T_SPACE
except ImportError:                       # loaded by file path for isolated testing
    from thermal import SIGMA, T_ZERO_C, T_SPACE


@dataclass
class TransientResult:
    """Temperature history. ``t_front_c``/``t_rear_c`` are (n_steps x n_cells)."""
    times: np.ndarray
    t_front_c: np.ndarray
    t_rear_c: np.ndarray
    converged: bool


def areal_heat_capacity(area, rho: float, cp: float, thickness: float):
    """Lumped node heat capacity C = rho * cp * thickness * area  (J/K).

    e.g. an aluminium-backed cell: rho ~2700 kg/m^3, cp ~900 J/kgK, thickness in m.
    """
    return rho * cp * thickness * np.asarray(area, float)


def _b(x, n):
    a = np.asarray(x, float)
    return np.full(n, float(a)) if a.ndim == 0 else a.flatten()


def solve_transient(
    area, alpha_front, alpha_rear, epsilon_front, epsilon_rear, c_cond: float,
    heat_capacity, flux_series, p_elec_series,
    *, t_init_c: float = 28.0, step_tol: float = 1e-6, max_step_iter: int = 40,
) -> TransientResult:
    """Integrate the 2-node temperature over a time series of conditions.

    ``flux_series`` : sequence of points with ``.time_s, .p_sun, .p_albedo,
    .p_ir, .tilt`` (e.g. from :func:`environment.orbit_flux_timeline`).
    ``p_elec_series`` : per-step electrical power -- a scalar, a per-cell array
    (constant in time), or a (n_steps x n_cells) array (e.g. a failure injected
    at some step). ``heat_capacity`` : J/K, scalar or per-cell (applied to both
    faces). Returns the temperature at each time point.
    """
    pts = list(flux_series)
    nt = len(pts)
    if nt < 2:
        raise ValueError("need at least 2 flux points to define time steps")
    times = np.array([p.time_s for p in pts], float)

    pe = np.asarray(p_elec_series, float)
    n = int(max(np.asarray(area).size, pe.size if pe.ndim <= 1 else pe.shape[1], 1))
    A = _b(area, n)
    aF, aR = _b(alpha_front, n), _b(alpha_rear, n)
    eF, eR = _b(epsilon_front, n), _b(epsilon_rear, n)
    C = _b(heat_capacity, n)
    CA = c_cond * A
    eFAs, eRAs = eF * A * SIGMA, eR * A * SIGMA
    tsp4 = T_SPACE ** 4

    def pe_at(k):
        if pe.ndim == 2:
            return pe[k]
        if pe.ndim == 1 and pe.size == n:
            return pe
        return np.full(n, float(pe))

    T1 = np.full(n, t_init_c - T_ZERO_C)
    T2 = np.full(n, t_init_c - T_ZERO_C)
    hist1 = np.empty((nt, n)); hist2 = np.empty((nt, n))
    hist1[0] = T1; hist2[0] = T2
    all_converged = True

    for k in range(1, nt):
        p = pts[k]
        dt = float(times[k] - times[k - 1])
        qF = aF * A * p.p_sun * p.tilt
        qR = (aR * p.p_albedo + eR * p.p_ir) * A * p.tilt
        Pe = pe_at(k)
        T1p, T2p = T1.copy(), T2.copy()
        step_ok = False
        for _ in range(max_step_iter):
            f1 = qF - eFAs * (T1 ** 4 - tsp4) - Pe + CA * (T2 - T1)
            f2 = qR - eRAs * (T2 ** 4 - tsp4) - CA * (T2 - T1)
            g1 = C * (T1 - T1p) / dt - f1
            g2 = C * (T2 - T2p) / dt - f2
            a = -4.0 * eFAs * T1 ** 3 - CA
            d = -4.0 * eRAs * T2 ** 3 - CA
            # Jacobian of g = C/dt - (Jacobian of f); off-diagonals -CA
            A_ = C / dt - a; D_ = C / dt - d; B_ = -CA; C_ = -CA
            det = A_ * D_ - B_ * C_
            det = np.where(np.abs(det) < 1e-30, 1e-30, det)
            dT1 = (-D_ * g1 + B_ * g2) / det
            dT2 = (C_ * g1 - A_ * g2) / det
            T1 = T1 + dT1; T2 = T2 + dT2
            if np.max(np.abs(dT1)) < step_tol and np.max(np.abs(dT2)) < step_tol:
                step_ok = True
                break
        all_converged = all_converged and step_ok
        hist1[k] = T1; hist2[k] = T2

    return TransientResult(
        times=times,
        t_front_c=hist1 + T_ZERO_C,
        t_rear_c=hist2 + T_ZERO_C,
        converged=all_converged,
    )


def time_to_threshold(result: TransientResult, limit_c: float, cell: int = 0):
    """First time (s) the given cell's front temperature reaches ``limit_c``,
    or ``None`` if it never does in the series."""
    front = np.asarray(result.t_front_c, float)[:, cell]
    idx = np.nonzero(front >= limit_c)[0]
    return float(result.times[idx[0]]) if idx.size else None
