# -*- coding: utf-8 -*-
"""Unified 2-node thermal solver (independent OR laterally-coupled).

ONE public entry point, :func:`solve_thermal`, with a single switch ``g_lat``:

* ``g_lat == 0`` -> cells are independent, the global Jacobian is block-diagonal
  (N separate 2x2 blocks), and we invert each block in closed form, vectorised
  over the whole array. This is the fast path and reproduces the legacy per-cell
  ``scipy.fsolve`` answer exactly (single sunlit cell -> 65.26 degC).
* ``g_lat > 0`` -> neighbouring tiles share heat in-plane, the cells are coupled,
  and we assemble one (2N x 2N) sparse Jacobian (each tile linked to its grid
  neighbours) and take sparse Newton steps.

Because ``g_lat = 0`` is a strict special case, the lateral model is a superset:
turning ``g_lat`` on only *adds* realistic spreading (peak drops, neighbours warm).

:func:`solve_panel` is a thin convenience wrapper that pulls the per-tile property
arrays and 4-neighbour adjacency from a :class:`powerpy.config.layout.PanelLayout`
and returns grid-shaped temperatures.

Standalone: numpy always; scipy.sparse for the lateral path (dense fallback).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

# Physical constants (kept local so this module imports nothing from powerpy).
SIGMA = 5.670367e-8      # Stefan-Boltzmann [W/(m^2 K^4)]
T_ZERO_C = -273.15       # 0 K in degrees Celsius
T_SPACE = 2.7            # deep-space background [K]

try:
    import scipy.sparse as _sp
    import scipy.sparse.linalg as _spla
    _HAVE_SCIPY = True
except Exception:                      # pragma: no cover
    _HAVE_SCIPY = False


@dataclass
class ThermalResult:
    """Flat per-cell converged temperatures (degC) + diagnostics."""
    t_front_c: np.ndarray
    t_rear_c: np.ndarray
    iterations: int
    converged: bool
    max_residual: float
    g_lat: float = 0.0


@dataclass
class PanelThermalResult:
    """Grid-shaped (n_rows x n_cols) converged temperatures (degC) + diagnostics."""
    t_front_c: np.ndarray
    t_rear_c: np.ndarray
    iterations: int
    converged: bool
    max_residual: float
    g_lat: float


def lateral_conductance(k_facesheet: float, thickness_m: float,
                        edge_width_m: float, pitch_m: float) -> float:
    """Lateral conductance g_lat (W/K) between two adjacent tiles, from geometry::

        g_lat = k_facesheet * (edge_width_m * thickness_m) / pitch_m

    e.g. an aluminium facesheet ~150 W/mK, 0.3 mm thick, 55 mm edge & pitch
    -> ~0.045 W/K. Returns 0 for a zero-conductivity / zero-thickness sheet.
    """
    if pitch_m <= 0:
        raise ValueError("pitch_m must be > 0")
    return k_facesheet * (edge_width_m * thickness_m) / pitch_m


def _as_array(x, n: int) -> np.ndarray:
    a = np.asarray(x, dtype=float)
    if a.ndim == 0:
        return np.full(n, float(a))
    a = a.flatten()
    if a.shape[0] != n:
        raise ValueError("expected length %d, got %d" % (n, a.shape[0]))
    return a.astype(float, copy=True)


def solve_thermal(
    area,
    alpha_front,
    alpha_rear,
    epsilon_front,
    epsilon_rear,
    c_cond: float,
    p_sun: float,
    p_albedo: float,
    p_ir: float,
    p_elec,
    *,
    neighbours: Optional[Sequence[Tuple[int, int]]] = None,
    g_lat: float = 0.0,
    tilt: float = 1.0,
    s_solar=1.0,
    t_init_c: float = 28.0,
    tol: float = 1e-6,
    max_iter: int = 100,
    strict: bool = False,
) -> ThermalResult:
    """Solve every cell's 2-node steady-state temperature at once.

    Optical/thermal properties (``alpha_*``, ``epsilon_*``) may be scalars (shared
    by all cells) or length-N arrays (per cell). ``area`` and ``p_elec`` likewise.
    ``p_elec`` is the extracted electrical power per cell (W; negative = a
    reverse-biased dissipating cell).

    ``g_lat == 0`` uses the fast block-diagonal closed-form solve. ``g_lat > 0``
    requires ``neighbours`` (flat-index pairs) and uses a sparse Newton solve.
    """
    n = int(max(np.asarray(area).size, np.asarray(p_elec).size,
                np.asarray(alpha_front).size, 1))
    A = _as_array(area, n)
    Pe = _as_array(p_elec, n)
    aF = _as_array(alpha_front, n)
    aR = _as_array(alpha_rear, n)
    eF = _as_array(epsilon_front, n)
    eR = _as_array(epsilon_rear, n)

    CA = c_cond * A
    # s_solar is a per-cell FRONT-solar factor (shade*incidence): it multiplies
    # only the front solar term qF, never the rear albedo/IR term qR (which
    # arrives from the planet, not the Sun line).  Scalar 1.0 (the default)
    # broadcasts and reproduces today's numbers byte-for-byte.
    sS = _as_array(s_solar, n)
    qF = aF * A * p_sun * tilt * sS
    qR = (aR * p_albedo + eR * p_ir) * A * tilt
    tsp4 = T_SPACE ** 4
    lateral = (g_lat != 0.0) and bool(neighbours)

    # --- precompute the CONSTANT structure ONCE (lateral path) ---------------
    # Across Newton iterations only the radiative diagonal (-4 e A sigma T^3)
    # changes; the front<->rear conduction (CA) and the lateral coupling
    # (g_lat * graph-Laplacian) are fixed. So we build them once here and, each
    # iteration, just ADD the radiative diagonal -- no Python loops per step.
    Jconst = Lap = None
    if lateral:
        pr = np.asarray(list(neighbours), dtype=int)
        ii, jj = pr[:, 0], pr[:, 1]
        ones = np.ones(len(ii))
        if _HAVE_SCIPY:
            adj = _sp.coo_matrix((np.concatenate([ones, ones]),
                                  (np.concatenate([ii, jj]), np.concatenate([jj, ii]))),
                                 shape=(n, n)).tocsr()
            deg = np.asarray(adj.sum(axis=1)).ravel()
            Lap = (_sp.diags(deg) - adj).tocsr()              # graph Laplacian
            CAd = _sp.diags(CA)
            glatLap = (g_lat * Lap).tocsr()
            Jconst = _sp.bmat([[-CAd - glatLap, CAd],
                               [CAd, -CAd - glatLap]], format="csr")
        else:
            adj = np.zeros((n, n)); adj[ii, jj] = 1.0; adj[jj, ii] = 1.0
            deg = adj.sum(axis=1)
            Lap = np.diag(deg) - adj
            CAd = np.diag(CA)
            glatLap = g_lat * Lap
            Jconst = np.block([[-CAd - glatLap, CAd],
                               [CAd, -CAd - glatLap]])

    T1 = np.full(n, t_init_c - T_ZERO_C)
    T2 = np.full(n, t_init_c - T_ZERO_C)

    converged = False
    it = 0
    resid = np.inf
    for it in range(1, max_iter + 1):
        f1 = qF - eF * A * SIGMA * (T1 ** 4 - tsp4) - Pe + CA * (T2 - T1)
        f2 = qR - eR * A * SIGMA * (T2 ** 4 - tsp4) - CA * (T2 - T1)

        if not lateral:
            # --- fast path: closed-form 2x2 per cell, vectorised over the array
            a = -4.0 * eF * A * SIGMA * T1 ** 3 - CA
            b = CA
            c = CA
            d = -4.0 * eR * A * SIGMA * T2 ** 3 - CA
            det = a * d - b * c
            det = np.where(np.abs(det) < 1e-30, 1e-30, det)
            dT1 = -(d * f1 - b * f2) / det
            dT2 = -(-c * f1 + a * f2) / det
            resid = float(np.max(np.abs(f1) + np.abs(f2)))
        else:
            # --- lateral path: flux is a single Laplacian matvec (no pair loop);
            #     Jacobian = constant structure + the changing radiative diagonal
            f1 = f1 - g_lat * Lap.dot(T1)
            f2 = f2 - g_lat * Lap.dot(T2)
            f = np.concatenate([f1, f2])
            rad = np.concatenate([-4.0 * eF * A * SIGMA * T1 ** 3,
                                  -4.0 * eR * A * SIGMA * T2 ** 3])
            if _HAVE_SCIPY:
                J = (Jconst + _sp.diags(rad)).tocsr()
                dx = _spla.spsolve(J, -f)
            else:
                J = Jconst + np.diag(rad)
                dx = np.linalg.solve(J, -f)
            dT1 = dx[:n]; dT2 = dx[n:]
            resid = float(np.max(np.abs(f)))

        T1 = T1 + dT1
        T2 = T2 + dT2
        if np.max(np.abs(dT1)) < tol and np.max(np.abs(dT2)) < tol:
            converged = True
            break

    if not converged:
        _msg = ("thermal solve did not converge in %d iterations "
                "(max|residual| = %.3g W)" % (max_iter, resid))
        if strict:
            raise RuntimeError(_msg)
        warnings.warn(_msg, RuntimeWarning, stacklevel=2)

    return ThermalResult(
        t_front_c=T1 + T_ZERO_C,
        t_rear_c=T2 + T_ZERO_C,
        iterations=it,
        converged=converged,
        max_residual=resid,
        g_lat=g_lat,
    )


def solve_thermal_for_substrate(substrate, area, p_sun, p_albedo, p_ir, p_elec,
                                tilt: float = 1.0, **kw) -> ThermalResult:
    """Convenience wrapper taking a :class:`powerpy.config.substrate.Substrate`."""
    return solve_thermal(
        area=area, alpha_front=substrate.alpha_front, alpha_rear=substrate.alpha_rear,
        epsilon_front=substrate.epsilon_front, epsilon_rear=substrate.epsilon_rear,
        c_cond=substrate.c_cond, p_sun=p_sun, p_albedo=p_albedo, p_ir=p_ir,
        p_elec=p_elec, tilt=tilt, **kw,
    )


def solve_panel(
    layout,
    p_sun: float,
    p_albedo: float = 0.0,
    p_ir: float = 0.0,
    p_elec=None,
    *,
    c_cond: float = 1000.0,
    g_lat: float = 0.0,
    tilt: float = 1.0,
    s_solar=1.0,
    area=None,
    t_init_c: float = 28.0,
    tol: float = 1e-6,
    max_iter: int = 100,
    strict: bool = False,
) -> PanelThermalResult:
    """Solve a whole :class:`PanelLayout` (grid + palette), optionally with lateral
    conduction. Returns grid-shaped temperatures. ``g_lat = 0`` reproduces the
    independent per-tile result exactly.
    """
    props = layout.prop_arrays()
    N = layout.n_tiles
    nrows, ncols = layout.n_rows, layout.n_cols
    if area is None:
        a = (layout.pitch_mm / 1000.0) ** 2
        A = np.full(N, a)
    else:
        A = np.full(N, float(area)) if np.ndim(area) == 0 else np.asarray(area, float).flatten()

    if p_elec is None:
        Pe = np.zeros(N)
    else:
        Pe = np.asarray(p_elec, float).flatten()
        if Pe.size == 1:
            Pe = np.full(N, float(Pe))
    Pe = np.where(props["generates_power"], Pe, 0.0)   # bare/diode tiles make no power

    res = solve_thermal(
        area=A, alpha_front=props["alpha_front"], alpha_rear=props["alpha_rear"],
        epsilon_front=props["epsilon_front"], epsilon_rear=props["epsilon_rear"],
        c_cond=c_cond, p_sun=p_sun, p_albedo=p_albedo, p_ir=p_ir, p_elec=Pe,
        neighbours=layout.neighbours(), g_lat=g_lat, tilt=tilt, s_solar=s_solar,
        t_init_c=t_init_c, tol=tol, max_iter=max_iter, strict=strict,
    )
    return PanelThermalResult(
        t_front_c=np.asarray(res.t_front_c).reshape(nrows, ncols),
        t_rear_c=np.asarray(res.t_rear_c).reshape(nrows, ncols),
        iterations=res.iterations, converged=res.converged,
        max_residual=res.max_residual, g_lat=g_lat,
    )
