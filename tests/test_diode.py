# -*- coding: utf-8 -*-
"""Tests for bypass-diode clamping (model/diode.py) and its effect on the
hot-spot temperature through the thermal solver."""
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


dio = _load("model/diode.py")
th = _load("solve/thermal.py")

V_CELL = 2.3
I_CELL = 0.48
N = 10                       # 10-cell series string


def test_unprotected_reverse_voltage():
    v = dio.unprotected_reverse_voltage(N, V_CELL)
    assert abs(v - (-(N - 1) * V_CELL)) < 1e-9     # -20.7 V
    assert dio.reverse_power(v, I_CELL) > 9.0       # ~9.94 W


def test_clamp_reduces_voltage_and_shrinks_with_spacing():
    d = dio.BypassDiode(v_forward=0.7)
    v2 = dio.clamped_reverse_voltage(2, V_CELL, d)   # -(0.7 + 1*2.3) = -3.0
    v5 = dio.clamped_reverse_voltage(5, V_CELL, d)   # -(0.7 + 4*2.3) = -9.9
    assert abs(v2 - (-3.0)) < 1e-9
    assert abs(v5 - (-9.9)) < 1e-9
    # fewer cells per diode -> smaller reverse voltage -> safer
    assert abs(v2) < abs(v5) < abs(dio.unprotected_reverse_voltage(N, V_CELL))


def test_reverse_power_zero_when_forward():
    assert dio.reverse_power(+2.3, I_CELL) == 0.0    # generating cell: no reverse heat
    assert dio.reverse_power(-3.0, I_CELL) > 0.0


def test_failed_cell_p_elec_sign_and_magnitude():
    d = dio.BypassDiode(0.7)
    p_un = dio.failed_cell_p_elec(I_CELL, n_series=N, v_cell=V_CELL)              # unprotected
    p_pr = dio.failed_cell_p_elec(I_CELL, n_series=N, v_cell=V_CELL, diode=d, cells_per_diode=2)
    assert p_un < 0 and p_pr < 0                      # both dissipate (negative)
    assert abs(p_un) > abs(p_pr)                      # protection dumps far less heat
    assert abs(p_un + 9.94) < 0.1                     # ~ -9.94 W
    assert abs(p_pr + 1.44) < 0.05                    # ~ -1.44 W


def test_bypass_diode_lowers_hotspot_temperature():
    """Feed the clamped vs unclamped P_elec into the thermal solver."""
    d = dio.BypassDiode(0.7)
    common = dict(area=0.003, alpha_front=0.97, alpha_rear=0.93,
                  epsilon_front=0.90, epsilon_rear=0.89, c_cond=1000.0,
                  p_sun=1367.0, p_albedo=0.0, p_ir=0.0)
    p_un = dio.failed_cell_p_elec(I_CELL, n_series=N, v_cell=V_CELL)
    p_pr = dio.failed_cell_p_elec(I_CELL, n_series=N, v_cell=V_CELL, diode=d, cells_per_diode=2)
    t_un = float(th.solve_thermal(p_elec=p_un, **common).t_front_c[0])
    t_pr = float(th.solve_thermal(p_elec=p_pr, **common).t_front_c[0])
    assert t_un > 180.0          # unprotected ~187 C hot-spot
    assert t_pr < 110.0          # bypass-protected: much cooler
    assert t_un - t_pr > 80.0    # the diode buys a big margin


def test_spacing_scan_monotone():
    d = dio.BypassDiode(0.7)
    scan = dio.spacing_scan(I_CELL, V_CELL, N, d, [1, 2, 5, 10])
    # first entry is the unprotected baseline (cells_per_diode None)
    assert scan[0]["cells_per_diode"] is None
    powers = [row["p_reverse_w"] for row in scan[1:]]
    assert powers == sorted(powers)      # more cells per diode -> more reverse power


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name); passed += 1
    print("\n%d/%d tests passed" % (passed, passed))
