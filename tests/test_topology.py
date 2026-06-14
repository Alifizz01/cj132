# -*- coding: utf-8 -*-
"""Tests for panel_from_topology (electrical topology -> physical layout)."""
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


th = _load("solve/thermal.py")
lay = _load("config/layout.py")


def test_side_by_side_shape_and_tags():
    L = lay.panel_from_topology(3, 4, 10)              # 3 blocks series x 4 parallel x 10 series
    assert L.n_rows == 4 and L.n_cols == 30 and L.n_tiles == 120
    keys = L.flat_keys()
    assert len(set(keys)) == 12                        # 3 blocks x 4 strings = 12 distinct strings
    # each string runs 10 SCAs in series -> appears 10 times
    assert keys.count("B2S3") == 10
    tt = L.palette["B2S3"]
    assert tt.is_cell and tt.string == "B2S3" and tt.block == "B2"
    assert "series" in L.name


def test_block_assignment_follows_columns():
    L = lay.panel_from_topology(3, 4, 10, arrangement="side-by-side")
    # columns 0-9 -> B1, 10-19 -> B2, 20-29 -> B3 (row 0)
    assert L.tile_at(0, 5).block == "B1"
    assert L.tile_at(0, 15).block == "B2"
    assert L.tile_at(0, 25).block == "B3"


def test_stacked_arrangement_shape():
    L = lay.panel_from_topology(3, 4, 10, arrangement="stacked")
    assert L.n_rows == 12 and L.n_cols == 10 and L.n_tiles == 120
    assert L.tile_at(0, 0).block == "B1" and L.tile_at(11, 0).block == "B3"


def test_solves_thermally():
    L = lay.panel_from_topology(3, 4, 10)
    pe = np.full(L.n_tiles, 1.1); pe[1 * L.n_cols + 14] = -9.6   # fail one SCA in block 2
    r = th.solve_panel(L, p_sun=1367.0, p_elec=pe, g_lat=0.05, c_cond=1000.0, area=0.003)
    assert r.converged and float(r.t_front_c.max()) > float(np.median(r.t_front_c))


def test_series_count_recoverable():
    L = lay.panel_from_topology(2, 3, 7)               # 7 in series -> each string key appears 7x
    keys = L.flat_keys()
    assert keys.count("B1S2") == 7 and L.n_tiles == 2 * 3 * 7


def test_bad_args_raise():
    for bad in [(0, 4, 10), (3, 0, 10), (3, 4, 0)]:
        try:
            lay.panel_from_topology(*bad); assert False, "expected ValueError"
        except ValueError:
            pass


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name); passed += 1
    print("\n%d/%d tests passed" % (passed, passed))
