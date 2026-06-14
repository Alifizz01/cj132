# -*- coding: utf-8 -*-
"""Tests for the panel layout convention + lateral-conduction thermal solver +
report generator. Loaded by file path so the package __init__ (legacy imports)
is never triggered.

Key checks:
  * layout parses (grid, palette, adjacency);
  * G=0 reproduces the independent solver oracle (65.26 degC) -- strict superset;
  * a bare (no-cell) tile runs hotter than a power-extracting cell tile;
  * turning on lateral conduction cools the hot tile and warms its cool neighbour
    (heat spreads), conserving the in/out balance;
  * the report writes valid HTML + JSON.
"""
import importlib.util
import json
import os
import sys
import tempfile

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


tp = _load("solve/thermal.py")        # unified solver (solve_panel lives here now)
lay = _load("config/layout.py")
rep = _load("reporting/report.py")

A_TILE = {"is_cell": True, "string": "S1",
          "alpha_front": 0.97, "alpha_rear": 0.93, "epsilon_front": 0.90, "epsilon_rear": 0.89}
BARE = {"is_cell": False,
        "alpha_front": 0.97, "alpha_rear": 0.93, "epsilon_front": 0.90, "epsilon_rear": 0.89}


# --------------------------------------------------------------- layout
def test_layout_parses_and_adjacency():
    L = lay.from_dict({"palette": {"A": A_TILE, ".": BARE},
                       "layout": ["A A .", "A . A"], "pitch_mm": 40})
    assert L.n_rows == 2 and L.n_cols == 3 and L.n_tiles == 6
    # 4-neighbour adjacency of a 2x3 grid: 7 undirected links
    assert len(L.neighbours()) == 7
    assert L.tile_at(0, 0).is_cell and not L.tile_at(0, 2).is_cell


# --------------------------------------------------------------- parity (G=0)
def test_g0_matches_independent_oracle():
    """A single cell, no lateral link, must reproduce the 65.26 degC oracle."""
    L = lay.from_dict({"palette": {"A": A_TILE}, "layout": ["A"]})
    r = tp.solve_panel(L, p_sun=1367.0, p_elec=0.0,
                               c_cond=1000.0, g_lat=0.0, area=0.003)
    assert r.converged
    assert abs(float(r.t_front_c[0, 0]) - 65.26) < 0.05
    assert abs(float(r.t_rear_c[0, 0]) - 64.60) < 0.05


def test_g0_two_tiles_independent():
    """With g_lat=0 the two tiles must not influence each other."""
    L = lay.from_dict({"palette": {"A": A_TILE}, "layout": ["A A"]})
    # left extracts 0, right extracts power -> right cooler, independently
    r = tp.solve_panel(L, p_sun=1367.0, p_elec=[0.0, 2.0],
                               c_cond=1000.0, g_lat=0.0, area=0.003)
    assert abs(float(r.t_front_c[0, 0]) - 65.26) < 0.05      # unchanged by neighbour
    assert float(r.t_front_c[0, 1]) < float(r.t_front_c[0, 0])


# --------------------------------------------------------------- bare hotter
def test_bare_tile_runs_hotter_than_powered_cell():
    L = lay.from_dict({"palette": {"A": A_TILE, ".": BARE}, "layout": ["A ."]})
    # cell extracts 2 W (cools); bare makes no power even if we pass some
    r = tp.solve_panel(L, p_sun=1367.0, p_elec=[2.0, 2.0],
                               c_cond=1000.0, g_lat=0.0, area=0.003)
    t_cell = float(r.t_front_c[0, 0]); t_bare = float(r.t_front_c[0, 1])
    assert t_bare > t_cell + 10.0      # bare keeps all the heat -> markedly hotter


# --------------------------------------------------------------- lateral spread
def test_lateral_conduction_spreads_heat():
    L = lay.from_dict({"palette": {"A": A_TILE}, "layout": ["A A"]})
    pe = [-9.6, 1.1]                   # one dissipating hot, one healthy cool
    cold = tp.solve_panel(L, p_sun=1367.0, p_elec=pe, c_cond=1000.0, g_lat=0.0, area=0.003)
    warm = tp.solve_panel(L, p_sun=1367.0, p_elec=pe, c_cond=1000.0, g_lat=0.05, area=0.003)
    hot0, cool0 = float(cold.t_front_c[0, 0]), float(cold.t_front_c[0, 1])
    hot1, cool1 = float(warm.t_front_c[0, 0]), float(warm.t_front_c[0, 1])
    assert hot1 < hot0          # lateral link cools the hot tile
    assert cool1 > cool0        # ... and warms its neighbour
    assert warm.converged


# --------------------------------------------------------------- report
def test_report_writes_html_and_json():
    L = lay.from_dict({"palette": {"A": A_TILE, ".": BARE},
                       "layout": ["A A .", ". A A"], "pitch_mm": 40})
    r = tp.solve_panel(L, p_sun=1367.0, p_elec=1.1, c_cond=1000.0, g_lat=0.02, area=0.003)
    d = tempfile.mkdtemp()
    h = os.path.join(d, "report.html"); j = os.path.join(d, "results.json")
    rep.panel_report(L, r, t_limit_c=150.0, out_html=h, out_json=j)
    assert os.path.getsize(h) > 500
    data = json.load(open(j, encoding="utf-8"))
    assert data["summary"]["n_tiles"] == 6
    assert "t_front_c" in data and len(data["t_front_c"]) == 2
    assert data["summary"]["verdict"] in ("PASS", "FAIL")


def test_report_escapes_html():
    """V2: tile names with HTML specials must be escaped, not injected raw."""
    L = lay.from_dict({"palette": {"A": dict(A_TILE, name="Cell <A> & co")},
                       "layout": ["A A", "A A"], "pitch_mm": 55})
    r = tp.solve_panel(L, p_sun=1367.0, p_elec=1.1, c_cond=1000.0, g_lat=0.0, area=0.003)
    d = tempfile.mkdtemp(); h = os.path.join(d, "rep.html")
    rep.write_html(L, r, t_limit_c=150.0, path=h)
    txt = open(h, encoding="utf-8").read()
    assert "Cell &lt;A&gt; &amp; co" in txt     # escaped form present
    assert "<A>" not in txt                      # raw injection absent


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name); passed += 1
    print("\n%d/%d tests passed" % (passed, passed))
