# -*- coding: utf-8 -*-
"""Demo: run the lateral-conduction solver on the example asymmetric layout and
generate the HTML heat-map report + JSON. Run from Notes/ (neutral cwd)."""
import importlib.util, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "..", "src", "powerpy")

def load(relpath, name=None):
    name = name or os.path.splitext(os.path.basename(relpath))[0]
    s = importlib.util.spec_from_file_location(name, os.path.join(PKG, relpath))
    mod = importlib.util.module_from_spec(s); sys.modules[name] = mod; s.loader.exec_module(mod); return mod

tp = load("solve/thermal.py"); lay = load("config/layout.py"); rep = load("reporting/report.py")

L = lay.load_layout(os.path.join(PKG, "data", "layouts", "example_panel.json"))
print("layout:", L.name, "(%dx%d)" % (L.n_rows, L.n_cols))
print(L.ascii_art())

# Per-tile electrical power: healthy cells extract +1.1 W (cooler); bare/diode 0;
# inject ONE failed cell driven into reverse bias (-9.6 W) to show a hot-spot.
props = L.prop_arrays()
is_cell = props["generates_power"].reshape(L.n_rows, L.n_cols)
Pe = np.where(is_cell, 1.1, 0.0)
Pe[2, 4] = -9.6                      # failed cell beside the bare notch -> hot-spot
print("\nfailed (reverse-biased) cell at (2,4); bare notch at rows2-3 cols2-3")

common = dict(p_sun=1367.0, c_cond=1000.0, area=0.003, t_init_c=28.0)

# independent (no lateral) vs lateral spreading
indep = tp.solve_panel(L, p_elec=Pe, g_lat=0.0, **common)
later = tp.solve_panel(L, p_elec=Pe, g_lat=0.04, **common)

np.set_printoptions(precision=1, suppress=True)
print("\nFRONT temps, NO lateral conduction (g_lat=0):"); print(np.asarray(indep.t_front_c))
print("peak %.1f C, iters %d" % (indep.t_front_c.max(), indep.iterations))
print("\nFRONT temps, WITH lateral conduction (g_lat=0.04):"); print(np.asarray(later.t_front_c))
print("peak %.1f C, iters %d" % (later.t_front_c.max(), later.iterations))
print("hot-spot peak dropped %.1f -> %.1f C as heat spread to neighbours"
      % (indep.t_front_c.max(), later.t_front_c.max()))

rep.panel_report(L, later, t_limit_c=150.0,
                 out_html=os.path.join(HERE, "panel_report_demo.html"),
                 out_json=os.path.join(HERE, "panel_results_demo.json"))
print("\nwrote panel_report_demo.html + panel_results_demo.json")
