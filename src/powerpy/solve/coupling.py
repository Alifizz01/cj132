# -*- coding: utf-8 -*-
"""Electro-thermal coupling loop.

A cell's IV curve depends on its temperature, and its temperature depends on the
electrical power it extracts/dissipates -- a chicken-and-egg coupling. We hunt for
the self-consistent (temperature, operating-point) pair with a damped fixed-point
iteration: build cells at T -> solve circuit -> per-cell P_elec -> vectorised
thermal solve -> new T -> repeat.

The circuit solve is injected as ``power_fn(t_front_c) -> p_elec_array`` so the
loop is independent of *how* the power is obtained. In production ``power_fn``
builds the netlist (``Circuit.build_netlist``), runs ngspice, and reads back each
cell's V and I (``P_elec = V*I``). That ngspice read-back is the main integration
risk and is validated on a tiny 2x2 circuit first; the loop logic here is pure and
tested with a synthetic ``power_fn``.

Status: loop logic standalone & tested; ngspice ``power_fn`` pending a clean
``cell.buildModel`` (legacy cell.py needs OCR repair).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Callable

import numpy as np

try:                                    # normal package use
    from .thermal import solve_thermal
except ImportError:                     # loaded by file path for isolated testing
    from thermal import solve_thermal


@dataclass
class CoupledResult:
    t_front_c: np.ndarray
    t_rear_c: np.ndarray
    p_elec: np.ndarray
    outer_iterations: int
    converged: bool


def couple(
    power_fn: Callable[[np.ndarray], np.ndarray],
    *,
    area,
    alpha_front: float,
    alpha_rear: float,
    epsilon_front: float,
    epsilon_rear: float,
    c_cond: float,
    p_sun: float,
    p_albedo: float = 0.0,
    p_ir: float = 0.0,
    tilt: float = 1.0,
    t_init_c: float = 28.0,
    omega: float = 0.5,
    tol_c: float = 1e-3,
    max_outer: int = 50,
    strict: bool = False,
) -> CoupledResult:
    """Iterate circuit<->thermal to a self-consistent temperature field.

    ``power_fn`` maps the current per-cell front temperatures (degC array) to the
    per-cell extracted electrical power (W array; negative = dissipating). ``omega``
    is the under-relaxation factor (0<omega<=1) damping each update for stability.
    """
    if not (0.0 < omega <= 1.0):
        raise ValueError("omega must be in (0, 1], got %r" % omega)

    n = np.asarray(area).size
    T = np.full(max(n, 1), float(t_init_c))
    p_elec = np.zeros_like(T)
    converged = False
    it = 0
    for it in range(1, max_outer + 1):
        p_elec = np.asarray(power_fn(T), dtype=float)
        res = solve_thermal(
            area=area, alpha_front=alpha_front, alpha_rear=alpha_rear,
            epsilon_front=epsilon_front, epsilon_rear=epsilon_rear, c_cond=c_cond,
            p_sun=p_sun, p_albedo=p_albedo, p_ir=p_ir, p_elec=p_elec, tilt=tilt,
            t_init_c=t_init_c,
        )
        t_new = np.asarray(res.t_front_c, dtype=float)
        step = omega * (t_new - T)
        T = T + step
        if np.max(np.abs(step)) < tol_c:
            converged = True
            break

    # one final consistent thermal solve at the converged T's power
    res = solve_thermal(
        area=area, alpha_front=alpha_front, alpha_rear=alpha_rear,
        epsilon_front=epsilon_front, epsilon_rear=epsilon_rear, c_cond=c_cond,
        p_sun=p_sun, p_albedo=p_albedo, p_ir=p_ir, p_elec=p_elec, tilt=tilt,
        t_init_c=float(np.mean(T)),
    )
    if not converged:
        _msg = ("electro-thermal coupling did not converge in %d outer rounds "
                "(omega=%.2f, tol=%.3g degC)" % (max_outer, omega, tol_c))
        if strict:
            raise RuntimeError(_msg)
        warnings.warn(_msg, RuntimeWarning, stacklevel=2)

    return CoupledResult(
        t_front_c=res.t_front_c, t_rear_c=res.t_rear_c, p_elec=p_elec,
        outer_iterations=it, converged=converged,
    )
