#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Zero-install launcher for PowerPy (office-laptop friendly: NO `pip install`).

Adds ``src/`` to the import path and runs the CLI directly from source, using the
**vendored** dependencies (e.g. ``powerpy.ngspice``). Nothing is installed.

    python run.py run   data/layouts/example_panel.json --g-lat 0.045 --report out.html
    python run.py worst data/layouts/example_panel.json --max-failures 3
    python run.py sweep data/layouts/example_panel.json --p-fail 0.05

(Equivalent: ``set PYTHONPATH=src`` then ``python -m powerpy ...``.)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from powerpy.app import main   # noqa: E402  (after sys.path setup)

if __name__ == "__main__":
    raise SystemExit(main())
