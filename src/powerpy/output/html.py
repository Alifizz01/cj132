# -*- coding: utf-8 -*-
"""Analysis report generator: an HTML panel heat-map + a JSON data source.

The human-facing artefact is a self-contained **HTML** report whose centrepiece
is a colour-coded **panel temperature map** (each tile shaded cold->hot, tiles
over the melt limit outlined in red), plus a summary table and the layout key.
It prints straight to PDF. The reproducible **source of truth** is a JSON file
holding the per-tile temperatures, flags and summary, so any run can be re-read
or re-analysed without re-simulating.

Status: standalone (numpy + stdlib only), tested.
"""
from __future__ import annotations

import html
import json
from typing import Optional

import numpy as np


def _heat_color(t: float, tmin: float, tmax: float) -> str:
    """Blue (cold) -> amber -> red (hot) fill for a tile."""
    if tmax <= tmin:
        x = 0.5
    else:
        x = max(0.0, min(1.0, (t - tmin) / (tmax - tmin)))
    r = int(40 + 215 * x)
    g = int(90 + 120 * (1 - abs(2 * x - 1)))
    b = int(200 * (1 - x) + 30)
    return "rgb(%d,%d,%d)" % (r, g, b)


def summarise_panel(layout, result, t_limit_c: float) -> dict:
    """Build the summary + per-tile records from a PanelThermalResult."""
    front = np.asarray(result.t_front_c, float)
    rear = np.asarray(result.t_rear_c, float)
    keys = np.array(layout.flat_keys()).reshape(front.shape)
    powers = layout.prop_arrays()["generates_power"].reshape(front.shape)

    over = front >= t_limit_c
    tiles = []
    for r in range(front.shape[0]):
        for c in range(front.shape[1]):
            tt = layout.tile_at(r, c)
            tiles.append({
                "row": r, "col": c, "key": str(keys[r, c]),
                "name": tt.name, "is_cell": bool(tt.is_cell),
                "t_front_c": round(float(front[r, c]), 2),
                "t_rear_c": round(float(rear[r, c]), 2),
                "over_limit": bool(over[r, c]),
            })
    summary = {
        "name": layout.name,
        "grid": [int(front.shape[0]), int(front.shape[1])],
        "pitch_mm": layout.pitch_mm,
        "g_lat": getattr(result, "g_lat", None),
        "t_limit_c": t_limit_c,
        "peak_t_c": round(float(front.max()), 2),
        "peak_tile": [int(np.argmax(front) // front.shape[1]), int(np.argmax(front) % front.shape[1])],
        "mean_t_c": round(float(front.mean()), 2),
        "margin_to_limit_c": round(float(t_limit_c - front.max()), 2),
        "n_over_limit": int(over.sum()),
        "n_tiles": int(front.size),
        "n_cells": int(powers.sum()),
        "verdict": "FAIL" if over.any() else "PASS",
        "converged": bool(result.converged),
    }
    return {"summary": summary, "tiles": tiles}


def write_json(layout, result, t_limit_c: float, path: str) -> str:
    """Write the reproducible JSON source of truth."""
    data = summarise_panel(layout, result, t_limit_c)
    data["t_front_c"] = np.asarray(result.t_front_c, float).round(3).tolist()
    data["t_rear_c"] = np.asarray(result.t_rear_c, float).round(3).tolist()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def write_html(layout, result, t_limit_c: float, path: str) -> str:
    """Write the human-facing HTML report with the colour-coded heat map."""
    front = np.asarray(result.t_front_c, float)
    s = summarise_panel(layout, result, t_limit_c)["summary"]
    tmin, tmax = float(front.min()), float(front.max())

    cells_html = []
    for r in range(front.shape[0]):
        row_html = []
        for c in range(front.shape[1]):
            tt = layout.tile_at(r, c)
            t = float(front[r, c])
            bg = _heat_color(t, tmin, tmax)
            over = t >= t_limit_c
            border = "3px solid #c0142c" if over else "1px solid #00000022"
            txtcol = "#fff" if (t - tmin) > 0.55 * (tmax - tmin) else "#10222e"
            label = html.escape(str(layout.grid[r, c]))
            mark = " !" if over else ""
            row_html.append(
                "<td style='background:%s;border:%s;color:%s'>"
                "<div class='k'>%s</div><div class='t'>%.0f&deg;%s</div></td>"
                % (bg, border, txtcol, label, t, mark)
            )
        cells_html.append("<tr>" + "".join(row_html) + "</tr>")
    grid_table = "<table class='panel'>" + "".join(cells_html) + "</table>"

    legend = []
    for tt in layout.palette.values():
        role = "cell" if tt.is_cell else ("diode" if tt.is_diode else "bare substrate")
        legend.append("<li><b>%s</b> &mdash; %s (%s)</li>"
                      % (html.escape(tt.key), html.escape(tt.name or role), html.escape(role)))
    legend_html = "<ul class='legend'>" + "".join(legend) + "</ul>"

    verdict_color = "#1f7a44" if s["verdict"] == "PASS" else "#c0142c"
    html_out = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Panel Thermal Report</title>
<style>
@page{{size:A4;margin:16mm}}
*{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
body{{font-family:"Segoe UI",Helvetica,Arial,sans-serif;color:#16222e;max-width:900px;margin:0 auto;padding:20px;background:#fff}}
h1{{color:#0b3d63;font-size:22px;margin:0 0 2px}}
.sub{{color:#5d6b79;font-style:italic;margin:0 0 18px}}
.verdict{{display:inline-block;font-weight:700;color:#fff;background:{vc};padding:4px 14px;border-radius:6px;font-size:15px}}
table.panel{{border-collapse:collapse;margin:14px 0}}
table.panel td{{width:54px;height:54px;text-align:center;vertical-align:middle;font-size:11px;line-height:1.15}}
table.panel .k{{font-weight:700;font-size:12px;opacity:.85}}
table.panel .t{{font-variant-numeric:tabular-nums}}
table.stats{{border-collapse:collapse;font-size:13px;margin:10px 0}}
table.stats td,table.stats th{{border:1px solid #d6dde4;padding:5px 12px;text-align:left}}
table.stats th{{background:#eef3f8;color:#0b3d63}}
.legend{{list-style:none;padding:0;font-size:12.5px;color:#33485c;columns:2}}
.legend li{{margin:.2em 0}}
.bar{{height:14px;width:240px;border:1px solid #ccc;border-radius:3px;
 background:linear-gradient(90deg,rgb(40,90,230),rgb(170,150,80),rgb(255,90,30))}}
.small{{font-size:11px;color:#5d6b79}}
</style></head><body>
<h1>Panel Thermal Analysis &mdash; {name}</h1>
<p class="sub">{rows}&times;{cols} tiles &middot; pitch {pitch}&nbsp;mm &middot; lateral conductance g_lat = {glat} W/K</p>
<p><span class="verdict">{verdict}</span> &nbsp;<span class="small">melt limit {tlim}&nbsp;&deg;C</span></p>

<h3>Panel temperature map (front face)</h3>
{grid}
<div class="bar"></div>
<p class="small">cold {tmin:.0f}&deg;C &rarr; hot {tmax:.0f}&deg;C &middot; tiles outlined in red exceed the melt limit</p>

<h3>Summary</h3>
<table class="stats">
<tr><th>Peak temperature</th><td>{peak:.2f} &deg;C at tile {ptile}</td></tr>
<tr><th>Mean temperature</th><td>{mean:.2f} &deg;C</td></tr>
<tr><th>Margin to melt limit</th><td>{margin:.2f} &deg;C</td></tr>
<tr><th>Tiles over limit</th><td>{nover} of {ntiles}</td></tr>
<tr><th>Cells / total tiles</th><td>{ncells} cells, {ntiles} tiles</td></tr>
<tr><th>Solver converged</th><td>{conv}</td></tr>
</table>

<h3>Layout key</h3>
{legend}
<p class="small">Generated by PowerPy report.py &middot; reproducible data in the companion .json</p>
</body></html>""".format(
        vc=verdict_color, name=html.escape(s["name"] or "(unnamed)"),
        rows=s["grid"][0], cols=s["grid"][1], pitch=s["pitch_mm"], glat=s["g_lat"],
        verdict=s["verdict"], tlim=s["t_limit_c"], grid=grid_table,
        tmin=tmin, tmax=tmax, peak=s["peak_t_c"], ptile=tuple(s["peak_tile"]),
        mean=s["mean_t_c"], margin=s["margin_to_limit_c"], nover=s["n_over_limit"],
        ntiles=s["n_tiles"], ncells=s["n_cells"], conv=s["converged"], legend=legend_html,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_out)
    return path


def panel_report(layout, result, t_limit_c: float, out_html: str, out_json: Optional[str] = None):
    """Convenience: write both the HTML report and the JSON source of truth."""
    write_html(layout, result, t_limit_c, out_html)
    if out_json:
        write_json(layout, result, t_limit_c, out_json)
    return out_html, out_json
