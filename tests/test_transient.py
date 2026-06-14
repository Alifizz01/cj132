# -*- coding: utf-8 -*-
"""Tests for the transient (time-domain) solver + the orbit flux timeline."""
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
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


th = _load("solve/thermal.py")          # registered "thermal" for transient's import
tr = _load("solve/transient.py")
env = _load("model/environment.py")

CELL = dict(area=0.003, alpha_front=0.97, alpha_rear=0.93,
            epsilon_front=0.90, epsilon_rear=0.89, c_cond=1000.0)
FP = env.FluxPoint


def _const_series(n, dt, p_sun, p_albedo=0.0, p_ir=0.0, tilt=1.0, eclipsed=False):
    return [FP(time_s=k * dt, p_sun=p_sun, p_albedo=p_albedo, p_ir=p_ir,
               tilt=tilt, eclipsed=eclipsed) for k in range(n)]


def test_areal_heat_capacity():
    assert abs(float(tr.areal_heat_capacity(0.003, 2700.0, 900.0, 0.01)) - 72.9) < 1e-6


def test_steady_recovery_large_dt():
    """dt -> infinity must reproduce the steady 65.26 C oracle."""
    fps = [FP(0.0, 1367.0, 0.0, 0.0, 1.0, False),
           FP(1e12, 1367.0, 0.0, 0.0, 1.0, False)]
    r = tr.solve_transient(**CELL, heat_capacity=50.0, flux_series=fps,
                           p_elec_series=0.0, t_init_c=28.0)
    assert abs(float(r.t_front_c[-1, 0]) - 65.26) < 0.1


def test_hotspot_rise_monotone_to_steady():
    """A cell fails (P_elec=-9.6) under sun: T climbs monotonically toward 187 C."""
    fps = _const_series(300, 10.0, 1367.0)
    r = tr.solve_transient(**CELL, heat_capacity=30.0, flux_series=fps,
                           p_elec_series=-9.6, t_init_c=65.0)
    front = np.asarray(r.t_front_c)[:, 0]
    assert front[-1] > front[0]
    assert np.all(np.diff(front) >= -1e-6)         # monotone up
    assert abs(front[-1] - 187.48) < 2.0           # approaches the steady hot-spot
    assert tr.time_to_threshold(r, 150.0) is not None


def test_eclipse_cooldown_monotone_down():
    """Sun off (eclipse), no power: T falls monotonically."""
    fps = _const_series(120, 10.0, 0.0, eclipsed=True)
    r = tr.solve_transient(**CELL, heat_capacity=30.0, flux_series=fps,
                           p_elec_series=0.0, t_init_c=65.0)
    front = np.asarray(r.t_front_c)[:, 0]
    assert front[-1] < front[0]
    assert np.all(np.diff(front) <= 1e-6)
    assert tr.time_to_threshold(r, 150.0) is None  # never reaches 150 while cooling


def test_orbit_flux_timeline_shape():
    tl = env.orbit_flux_timeline(5400.0, 20, eclipse_fraction=0.35)
    assert len(tl) == 20
    assert all(p.p_sun == 0.0 for p in tl if p.eclipsed)
    assert all(p.p_sun > 0.0 for p in tl if not p.eclipsed)
    assert all(p.p_ir > 0.0 for p in tl)           # planet glows even in shadow
    assert any(p.eclipsed for p in tl) and any(not p.eclipsed for p in tl)


def test_transient_over_orbit_swings():
    """Run the transient over one orbit: eclipse temperatures dip below sunlit peak."""
    tl = env.orbit_flux_timeline(5400.0, 60, eclipse_fraction=0.35)
    r = tr.solve_transient(**CELL, heat_capacity=200.0, flux_series=tl,
                           p_elec_series=0.0, t_init_c=20.0)
    front = np.asarray(r.t_front_c)[:, 0]
    ecl = [front[k] for k, p in enumerate(tl) if p.eclipsed]
    lit = [front[k] for k, p in enumerate(tl) if not p.eclipsed]
    assert min(ecl) < max(lit)
    assert r.converged


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name); passed += 1
    print("\n%d/%d tests passed" % (passed, passed))
