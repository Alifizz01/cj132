# -*- coding: utf-8 -*-
"""Reporting: the machine-readable data store and the human-facing HTML report.

``store``  -> long-format Parquet/HDF5 results table + summaries + Excel export.
``report`` -> HTML panel heat-map + JSON source of truth.
"""
from .report import panel_report, write_html, write_json, summarise_panel
from . import store

__all__ = ["panel_report", "write_html", "write_json", "summarise_panel", "store"]
