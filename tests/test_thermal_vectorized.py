# -*- coding: utf-8 -*-
"""Tests for the vectorised 2-node thermal solver and the Substrate model.

The solver is pure numpy, so these run in isolation without ngspice or the
(OCR-damaged) legacy cell model. We load the two new modules *by file path* so
the package's __init__ (which imports legacy modules) is never triggered.

Oracle: a hand-worked single-cell energy balance (see Chapter 2 of the notes),
which the solver must reproduce. Run directly (``python tests/...py``) or via
``pytest``.
"""
import importlib.util
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.join(_HERE, "..", "src", "powerpy")


def _load(relpath, name=None):
    name = name or os.path.splitext(os.path.basename(relpath))[0]
    spec = importlib.util.spec_from_file_location(name, os.path.join(_PKG, relpath))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod   # dataclasses needs the module discoverable by name
    spec.loader.exec_module(mod)
    return mod


tv = _load("solve/thermal.py")         # unified solver (was thermal_vectorized)
sub = _load("config/substrate.py")


def test_substrate_loads_and_derives_conduction():
    s = sub.load_substrate("msro_case2")
    assert s.name == "SRP MSRO Case 2"
    assert s.alpha_front == 0.970
    assert s.epsilon_rear == 0.89
    # c_cond = conductivity / thickness = 10 / 0.01 = 1000 W/m^2K
    assert abs(s.c_cond - 1000.0) < 1e-9


def test_single_cell_matches_hand_worked_balance():
    """Sunlit cell, no albedo/IR, no extracted power -> ~65.26 degC (oracle)."""
    s = sub.load_substrate("msro_case2")
    r = tv.solve_thermal_for_substrate(
        s, area=0.003, p_sun=1367.0, p_albedo=0.0, p_ir=0.0, p_elec=0.0, tilt=1.0,
    )
    assert r.converged
    assert abs(float(r.t_front_c[0]) - 65.26) < 0.05
    assert abs(float(r.t_rear_c[0]) - 64.60) < 0.05


def test_vectorised_array_with_reverse_biased_hotspot():
    """One vectorised solve over 4 cells reproduces the per-cell oracle numbers,
    including the reverse-biased hot-spot (P_elec = -9.6 W -> ~187 degC)."""
    s = sub.load_substrate("msro_case2")
    p_elec = np.array([1.1, 1.1, 0.0, -9.6])      # two healthy, one idle, one dissipating
    r = tv.solve_thermal_for_substrate(
        s, area=0.003, p_sun=1367.0, p_albedo=0.0, p_ir=0.0, p_elec=p_elec, tilt=1.0,
    )
    assert r.converged
    front = np.asarray(r.t_front_c)
    expected = np.array([38.89, 38.89, 65.26, 187.48])
    assert np.allclose(front, expected, atol=0.1), (front, expected)
    # The idle cell (index 2) must match the standalone single-cell answer exactly.
    assert abs(front[2] - 65.26) < 0.05
    # Extracting power cools; dissipating power heats.
    assert front[0] < front[2] < front[3]


def test_extracting_power_cools_relative_to_idle():
    s = sub.load_substrate("msro_case2")
    idle = tv.solve_thermal_for_substrate(s, 0.003, 1367.0, 0.0, 0.0, 0.0).t_front_c[0]
    powered = tv.solve_thermal_for_substrate(s, 0.003, 1367.0, 0.0, 0.0, 2.0).t_front_c[0]
    assert powered < idle


def test_strict_raises_on_nonconvergence():
    """V1: strict=True must RAISE rather than silently return a wrong number."""
    s = sub.load_substrate("msro_case2")
    try:
        tv.solve_thermal_for_substrate(s, area=0.003, p_sun=1367.0, p_albedo=0.0,
                                       p_ir=0.0, p_elec=-9.6, max_iter=1, strict=True)
        assert False, "expected RuntimeError on non-convergence"
    except RuntimeError:
        pass


def test_default_warns_on_nonconvergence():
    """V1: default path warns (loud) but still returns, with converged=False."""
    import warnings as _w
    s = sub.load_substrate("msro_case2")
    with _w.catch_warnings(record=True) as rec:
        _w.simplefilter("always")
        r = tv.solve_thermal_for_substrate(s, area=0.003, p_sun=1367.0, p_albedo=0.0,
                                           p_ir=0.0, p_elec=-9.6, max_iter=1)
    assert not r.converged
    assert any(issubclass(x.category, RuntimeWarning) for x in rec)


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
            passed += 1
    print("\n%d/%d tests passed" % (passed, passed))
