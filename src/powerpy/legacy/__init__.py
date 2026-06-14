# -*- coding: utf-8 -*-
"""Quarantined legacy modules.

These are the original OCR-reconstructed flat modules (cell, string, section,
thermal, panel*, electric, datamgmt, definitions, shuntdiode, eclipse, cli, main,
...). They are kept here for reference and gradual repair, **out of the top-level
namespace** so they no longer collide with or clutter the maintained framework
(``powerpy.config / model / solve / analysis / reporting`` and the canonical
``loader / schemas / simulation / render`` subsystems).

Importing individual modules here may still fail until their OCR defects are
repaired (e.g. ``cell.py`` has duplicated-``self`` signatures and missing lines;
see ``docs/CELL_PY_REPAIR.md``). Nothing in the maintained framework imports from
this package — it is dead/quarantined code, retained deliberately, not wired in.
"""
