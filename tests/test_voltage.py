# -*- coding: utf-8 -*-
"""Tests for the series voltage-balance / zero-voltage analysis."""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.join(_HERE, "..", "src", "powerpy")


def _load(relpath, name=None):
    name = name or os.path.splitext(os.path.basename(relpath))[0]
    spec = importlib.util.spec_from_file_location(name, os.path.join(_PKG, relpath))
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod
    spec.loader.exec_module(mod); return mod


v = _load("analysis/voltage.py")


def test_all_healthy_forward_voltage():
    assert abs(v.panel_voltage_raw(3, 10, 0, v_fwd=2.3) - 69.0) < 1e-9   # 30 * 2.3


def test_raw_zero_at_half_when_symmetric():
    r = v.find_zero_voltage_raw(3, 10, v_fwd=2.3, v_rev=2.3)
    assert r["n_series_path"] == 30
    assert abs(r["k_exact"] - 15.0) < 1e-9 and r["n_failed"] == 15
    assert abs(r["v_at_n_failed"]) < 1e-9            # exactly cancels
    assert abs(r["fraction_failed"] - 0.5) < 1e-9 and r["achievable"]


def test_raw_fewer_failures_when_reverse_is_larger():
    r = v.find_zero_voltage_raw(3, 10, v_fwd=2.3, v_rev=6.9)   # reverse 3x forward
    assert abs(r["k_exact"] - 7.5) < 1e-9                       # 30 * 2.3/(2.3+6.9)


def test_diode_clamp_prevents_zero():
    assert abs(v.panel_voltage_diode(3, 10, 3, v_fwd=2.3, v_diode=0.7) - (-2.1)) < 1e-9
    d = v.find_zero_voltage_diode(3, 10, v_fwd=2.3, v_diode=0.7)
    assert not d["zero_reachable"]
    assert d["min_abs_v"] > 1.0                       # never near zero by cancellation


def test_is_zero_threshold():
    assert v.is_zero(0.5, 69.0) and not v.is_zero(40.0, 69.0)


def test_compare_models_returns_both():
    rep = v.compare_models(3, 10, v_fwd=2.3, v_rev=2.3, v_diode=0.7)
    assert abs(rep.forward_max_v - 69.0) < 1e-9
    assert rep.raw_no_diode["achievable"] is True
    assert rep.diode_clamped["zero_reachable"] is False


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name); passed += 1
    print("\n%d/%d tests passed" % (passed, passed))
