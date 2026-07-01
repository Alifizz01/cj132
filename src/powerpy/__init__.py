# -*- coding: utf-8 -*-
"""PowerPy — satellite solar-array circuit & electro-thermal framework.

Layered subpackages (import what you need; nothing legacy is pulled in here, so
this import never fails on the OCR-damaged legacy modules):

    powerpy.config     inputs        -> Substrate, load_substrate, PanelLayout, load_layout
    powerpy.model      physics       -> Circuit, solar_irradiance, albedo_flux, ...
    powerpy.solve      solvers       -> solve_thermal, solve_panel, lateral_conductance, couple
    powerpy.analysis   analysis      -> evaluate_breakdown, montecarlo, failure_sweep, rank
    powerpy.output     outputs       -> Report (LaTeX PDF), panel_report (HTML heat-map),
                                        write_results_xlsx (Excel results)

Quick start::

    from powerpy.config import load_layout
    from powerpy.solve import solve_panel, lateral_conductance
    from powerpy.output.html import panel_report

    L = load_layout("data/layouts/example_panel.json")
    g = lateral_conductance(150.0, 0.0003, 0.055, 0.055)        # ~0.045 W/K
    res = solve_panel(L, p_sun=1367.0, g_lat=g, c_cond=1000.0, area=0.003)
    panel_report(L, res, t_limit_c=150.0, out_html="report.html", out_json="results.json")

The legacy flat modules (cell.py, string.py, section.py, thermal.py, eclipse.py)
are NOT imported here and are being repaired/retired separately; importing them
is opt-in (``import powerpy.cell``) and may fail until that repair lands.
"""
from __future__ import annotations

import os

__version__ = "0.2.0"

# Absolute path to this package (back-compat with older code that used
# ``pkg_resources``; derived from __file__ so importing PowerPy never requires
# setuptools to be installed).
power_path = os.path.abspath(os.path.dirname(__file__))

# Note: subpackages are imported on demand (``from powerpy.solve import ...``)
# rather than eagerly here, so that importing the package stays lightweight and
# does not force scipy/pandas to load unless the relevant layer is used.
__all__ = ["config", "model", "solve", "analysis", "output", "power_path", "__version__"]
