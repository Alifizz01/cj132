# -*- coding: utf-8 -*-
"""Tests for the pure logic of the new pipeline modules (breakdown,
electrothermal coupling loop, montecarlo sampling/ranking, orbit flux math,
results assembly). ngspice/hapsira integration points are not exercised here.
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
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


tv = _load("solve/thermal.py")        # registered "thermal"; coupling's fallback import resolves
sub = _load("config/substrate.py")
bd = _load("analysis/breakdown.py")
et = _load("solve/coupling.py")
mc = _load("analysis/montecarlo.py")
env = _load("model/environment.py")

S = sub.load_substrate("msro_case2")


# ----------------------------------------------------------------- breakdown
def test_breakdown_both_criteria():
    r = bd.evaluate_breakdown(
        t_front_c=[45.0, 187.0], v=[2.3, -20.0], i=[0.48, 0.48],
        t_limit_c=150.0, p_rev_limit_w=2.0,
    )
    assert r.destroyed.tolist() == [False, True]
    assert r.temperature_tripped.tolist() == [False, True]
    assert r.reverse_power_tripped.tolist() == [False, True]
    assert abs(float(r.reverse_power_w[1]) - 9.6) < 1e-9
    assert r.n_destroyed == 1


# ------------------------------------------------------------ electrothermal
def test_couple_converges_to_thermal_answer_single_cell():
    out = et.couple(
        power_fn=lambda T: np.zeros_like(T),
        area=0.003, alpha_front=S.alpha_front, alpha_rear=S.alpha_rear,
        epsilon_front=S.epsilon_front, epsilon_rear=S.epsilon_rear, c_cond=S.c_cond,
        p_sun=1367.0,
    )
    assert out.converged
    assert abs(float(out.t_front_c[0]) - 65.26) < 0.1


def test_couple_array_with_hotspot():
    p = np.array([1.1, 1.1, 0.0, -9.6])
    out = et.couple(
        power_fn=lambda T: p,
        area=np.full(4, 0.003), alpha_front=S.alpha_front, alpha_rear=S.alpha_rear,
        epsilon_front=S.epsilon_front, epsilon_rear=S.epsilon_rear, c_cond=S.c_cond,
        p_sun=1367.0, omega=0.6,
    )
    assert out.converged
    assert np.allclose(out.t_front_c, [38.89, 38.89, 65.26, 187.48], atol=0.3)


# --------------------------------------------------------------- montecarlo
def test_pattern_generators_counts_and_repro():
    ids = ["c%d" % i for i in range(10)]
    assert len(mc.position_patterns(ids)) == 10
    cps = mc.count_patterns(ids, ks=[1, 2, 3], samples_per_k=5, seed=1)
    assert len(cps) == 15
    assert sum(1 for p in cps if len(p) == 2) == 5
    # reproducible with same seed
    assert mc.count_patterns(ids, [2], 4, seed=7) == mc.count_patterns(ids, [2], 4, seed=7)
    rps = mc.random_patterns(ids, p_fail=0.3, n_samples=20, seed=2)
    assert len(rps) == 20


def test_run_sweep_and_rank():
    ids = ["c%d" % i for i in range(5)]
    patterns = mc.position_patterns(ids) + mc.count_patterns(ids, [3], 2, seed=0)
    recs = mc.run_sweep(patterns, evaluate=lambda pat: {"max_temp_c": 30.0 + 50.0 * len(pat)})
    assert all("run_id" in r and "n_failed" in r for r in recs)
    ranked = mc.rank(recs, key="max_temp_c")
    assert ranked[0]["n_failed"] >= ranked[-1]["n_failed"]


def test_runs_needed_and_se():
    assert mc.runs_needed(8.0, 100, 2.0) == 1600
    # [0,2]: mean 1, sample var = ((-1)^2+1^2)/(2-1) = 2, std = sqrt(2), SE = sqrt(2)/sqrt(2) = 1
    assert abs(mc.standard_error([0, 2]) - 1.0) < 1e-9


# --------------------------------------------------------------- orbit flux
def test_solar_irradiance_inverse_square_and_eclipse():
    assert abs(env.solar_irradiance(1.0) - 1367.0) < 1e-9
    assert abs(env.solar_irradiance(1.52) - 1367.0 / 1.52 ** 2) < 1e-6
    assert env.solar_irradiance(1.0, eclipsed=True) == 0.0


def test_tilt_and_albedo():
    assert abs(env.cosine_tilt(0, 0) - 1.0) < 1e-12
    assert abs(env.cosine_tilt(30, 0) - np.cos(np.radians(30))) < 1e-12
    assert abs(env.albedo_flux(0.25, 591.0, 0.3) - 44.325) < 1e-6


# (the reporting/store.py long-table test was removed with the module in P3 --
#  the store had no production caller; sweep output is an Excel summary.)


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name); passed += 1
    print("\n%d/%d tests passed" % (passed, passed))
