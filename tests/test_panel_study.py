# -*- coding: utf-8 -*-
"""Tests for the grid Monte-Carlo failure study (panel_study.py)."""
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


_th = _load("solve/thermal.py")        # registered "thermal" so study's fallback import resolves
lay = _load("config/layout.py")
mc = _load("analysis/montecarlo.py")   # study imports this by name
ps = _load("analysis/study.py")

A_TILE = {"is_cell": True, "string": "S1",
          "alpha_front": 0.97, "alpha_rear": 0.93, "epsilon_front": 0.90, "epsilon_rear": 0.89}
BARE = {"is_cell": False, "alpha_front": 0.97, "alpha_rear": 0.93,
        "epsilon_front": 0.90, "epsilon_rear": 0.89}


def _layout():
    return lay.from_dict({"palette": {"A": A_TILE, ".": BARE},
                          "layout": ["A A .", "A A A"], "pitch_mm": 55})


def test_cell_indices_excludes_bare():
    L = _layout()
    idx = ps.cell_indices(L)            # tile (0,2) is bare -> flat index 2 excluded
    assert 2 not in idx and len(idx) == 5


def test_make_pe_forces_noncells_zero_and_sets_reverse():
    L = _layout()
    pe = ps.make_pe(L, failed=[0, 2], healthy_w=1.1, reverse_w=-9.6)
    assert pe[0] == -9.6                # cell 0 failed -> reverse
    assert pe[2] == 0.0                 # tile 2 is bare -> always 0 (can't fail)
    assert pe[1] == 1.1                 # healthy cell


def test_failure_sweep_and_rank():
    L = _layout()
    pats = ps.position_sweep_patterns(L)
    recs = ps.failure_sweep(L, pats, t_limit_c=150.0,
                            solve_kwargs=dict(p_sun=1367.0, c_cond=1000.0, g_lat=0.0, area=0.003))
    assert len(recs) == 5 and all(r["converged"] for r in recs)
    ranked = ps.rank(recs)
    # every single-failure run drives one cell to the ~187 C reverse hot-spot
    assert ranked[0]["peak_t_c"] > 150.0
    assert ranked[0]["peak_t_c"] >= ranked[-1]["peak_t_c"]


def test_lateral_lowers_peak_in_sweep():
    L = _layout()
    pats = [[0]]                        # fail one corner cell
    common = dict(p_sun=1367.0, c_cond=1000.0, area=0.003)
    no_lat = ps.failure_sweep(L, pats, t_limit_c=150.0, solve_kwargs=dict(g_lat=0.0, **common))
    lat = ps.failure_sweep(L, pats, t_limit_c=150.0, solve_kwargs=dict(g_lat=0.05, **common))
    assert lat[0]["peak_t_c"] < no_lat[0]["peak_t_c"]   # spreading cools the hot-spot


def test_failure_sweep_parallel_matches_serial():
    """P2: threaded sweep gives identical results (and order) to the serial one."""
    L = _layout()
    pats = ps.position_sweep_patterns(L)
    kw = dict(t_limit_c=150.0,
              solve_kwargs=dict(p_sun=1367.0, c_cond=1000.0, g_lat=0.04, area=0.003))
    serial = ps.failure_sweep(L, pats, **kw)
    parallel = ps.failure_sweep(L, pats, workers=4, **kw)
    assert serial == parallel


def test_worst_case_search_greedy():
    """#5: greedy search returns the requested number of failures, escalating peak,
    and is deterministic."""
    L = _layout()
    kw = dict(max_failures=2, t_limit_c=150.0,
              solve_kwargs=dict(p_sun=1367.0, c_cond=1000.0, g_lat=0.0, area=0.003))
    out = ps.worst_case_search(L, **kw)
    assert len(out["failed"]) == 2
    assert out["peak_t_c"] > 150.0                       # a reverse-biased hot-spot
    assert len(out["trajectory"]) == 2
    peaks = [t["peak_t_c"] for t in out["trajectory"]]
    assert peaks[1] >= peaks[0] - 1e-6                   # adding a failure can't cool the peak
    assert ps.worst_case_search(L, **kw)["failed"] == out["failed"]   # deterministic


def test_auto_monte_carlo_stops_and_reproducible():
    """#5: auto-stop MC halts on the standard-error target and is seed-reproducible."""
    L = _layout()
    kw = dict(t_limit_c=150.0, p_fail=0.5, target_se=1e6, batch=4, max_runs=12, seed=1,
              solve_kwargs=dict(p_sun=1367.0, c_cond=1000.0, g_lat=0.0, area=0.003))
    a = ps.auto_monte_carlo(L, **kw)
    assert a["stopped"] in ("converged", "max_runs")
    assert 0 < a["n_runs"] <= 12 and len(a["records"]) == a["n_runs"]
    assert a["stopped"] == "converged"                   # huge target -> stops after first batch
    b = ps.auto_monte_carlo(L, **kw)
    assert a["mean_peak_c"] == b["mean_peak_c"]          # reproducible for a fixed seed


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name); passed += 1
    print("\n%d/%d tests passed" % (passed, passed))
