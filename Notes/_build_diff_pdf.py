# -*- coding: utf-8 -*-
"""Build a focused CHANGE-SET ('diff') PDF for the layout<->thermal topology +
zero-voltage work. Summary + concept (with figures) + the new/changed code.
Run from Notes/."""
import html, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SRC = os.path.join(ROOT, "src", "powerpy")
TESTS = os.path.join(ROOT, "tests")
BADGE = {"CREATE": "#1f7a44", "UPDATE": "#b9851a"}


def read(p):
    try:
        return open(p, "r", encoding="utf-8", errors="replace").read()
    except Exception as e:
        return "# (could not read: %s)" % e


def slice_from(text, marker):
    i = text.find(marker)
    return text[i:] if i >= 0 else "# (marker %r not found)" % marker


def nlines(s):
    return s.count("\n") + (0 if s.endswith("\n") else 1)


# (display, action, note, code-string)
layout_src = read(os.path.join(SRC, "config", "layout.py"))
ITEMS = [
    ("src/powerpy/config/layout.py  (added TileType.block + panel_from_topology)", "UPDATE",
     "New `block` field on TileType; new panel_from_topology() builds a PanelLayout from an electrical "
     "topology (n_blocks series x n_parallel x n_series). Only the new function is shown.",
     slice_from(layout_src, "def panel_from_topology")),
    ("src/powerpy/config/__init__.py  (export)", "UPDATE",
     "Re-export panel_from_topology.",
     'from .layout import (\n    PanelLayout, TileType, load_layout, from_dict as layout_from_dict,\n'
     '    panel_from_topology,\n)'),
    ("src/powerpy/analysis/voltage.py  (NEW)", "CREATE",
     "Series voltage-balance / zero-voltage analysis: when reverse-bias voltages cancel the forward "
     "voltages so V_array = 0. Raw (no-diode) vs diode-clamped models; evaluate + search.",
     read(os.path.join(SRC, "analysis", "voltage.py"))),
    ("src/powerpy/analysis/__init__.py  (export)", "UPDATE",
     "Re-export the voltage-analysis functions.",
     'from .voltage import (\n    panel_voltage_raw, panel_voltage_diode, is_zero,\n'
     '    find_zero_voltage_raw, find_zero_voltage_diode, compare_models, ZeroVoltageReport,\n)'),
    ("tests/test_topology.py  (NEW, 6/6)", "CREATE",
     "Tests panel_from_topology: shapes, block tagging, series-count recoverable, solves thermally.",
     read(os.path.join(TESTS, "test_topology.py"))),
    ("tests/test_voltage.py  (NEW, 6/6)", "CREATE",
     "Tests the zero-voltage analysis: symmetric half-cancellation, reverse>forward, diodes prevent zero.",
     read(os.path.join(TESTS, "test_voltage.py"))),
]

parts = ['''<!DOCTYPE html><html><head><meta charset="utf-8"><title>PowerPy Change Set</title>
<style>
@page{size:A4;margin:15mm 13mm}
*{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:"Segoe UI",Helvetica,Arial,sans-serif;color:#16222e;margin:0;padding:0}
h1{color:#0b3d63;font-size:25px;margin:0 0 2px}.sub{color:#5d6b79;font-style:italic;margin:2px 0 14px}
.opener{border:1px solid #d6dde4;border-top:6px solid #0b3d63;border-radius:6px;padding:16mm 12mm}
h2{color:#0b3d63;font-size:16px;border-bottom:2px solid #0b3d63;padding-bottom:3px;margin:18px 0 8px}
h2.pb{break-before:page}
p.slow{font-size:11pt;line-height:1.55}
.badge{display:inline-block;color:#fff;font-size:9.5px;font-weight:700;border-radius:3px;padding:1px 7px;margin-right:6px}
.filehdr{break-before:page;border-left:6px solid #0b3d63;background:#eef3f8;border-radius:5px;padding:7px 11px;margin:14px 0 6px}
.filehdr .path{font-family:"Cascadia Mono",Consolas,monospace;font-weight:700;color:#0b3d63;font-size:12px}
.filehdr .meta{font-size:10px;color:#5d6b79;margin-top:2px}
pre{font-family:"Cascadia Mono",Consolas,monospace;font-size:7.7pt;line-height:1.32;background:#f7f8fa;border:1px solid #e2e6ea;border-radius:5px;padding:8px 10px;white-space:pre-wrap;word-break:break-word;margin:0 0 6px}
table.idx{border-collapse:collapse;width:100%;font-size:10px;margin:6px 0}
table.idx td,table.idx th{border:1px solid #d6dde4;padding:4px 7px;text-align:left;vertical-align:top}
table.idx th{background:#eef3f8;color:#0b3d63}
.mono{font-family:"Cascadia Mono",Consolas,monospace}.small{font-size:10.5px;color:#5d6b79}
figure{margin:10px 0;text-align:center}figure img{max-width:100%;border:1px solid #e6e9ee;border-radius:5px}
figcaption{font-size:9pt;color:#5d6b79;margin-top:4px}
.callout{background:#eef6f1;border-left:4px solid #2f8f6b;border-radius:6px;padding:8px 12px;font-size:10.5pt;margin:8px 0}
.tbl{border-collapse:collapse;font-size:10.5px;margin:8px 0}.tbl td,.tbl th{border:1px solid #d6dde4;padding:4px 8px}
</style></head><body>''']

total = sum(nlines(c) for _, _, _, c in ITEMS)
parts.append('''<section class="opener">
<h1>PowerPy &mdash; Change Set</h1>
<div class="sub">Connecting the layout we want to the thermal analysis: the topology&rarr;layout helper and
the zero-voltage analysis.</div>
<p class="small">Diff for the work answering: <i>"the series number of SCAs, how many series in parallel then
a block &mdash; how do we draw that and connect the dots between the layout and the thermal analysis?"</i>
%d source lines across %d files. Tests: 12/12 new (full suite 68).</p>
</section>''' % (total, len(ITEMS)))

# index
rows = "".join("<tr><td><span class='badge' style='background:%s'>%s</span></td><td class='mono'>%s</td>"
               "<td style='text-align:right'>%d</td><td>%s</td></tr>"
               % (BADGE[a], a, html.escape(d), nlines(c), html.escape(note))
               for d, a, note, c in ITEMS)
parts.append("<section style='padding:0 12mm'><h2>What changed</h2><table class='idx'>"
             "<tr><th>Action</th><th>File</th><th>Lines</th><th>What</th></tr>" + rows + "</table>")

# concept
parts.append('''<h2>Connecting the layout to the thermal analysis</h2>
<p class="slow">The electrical layout is a <b>logical wiring</b> (N_series SCAs in series = a string; strings in
parallel, joined at nodes = a block; blocks in series). The thermal layout is a <b>physical 2-D grid</b> (where
each tile sits, who its neighbours are for lateral conduction). A real panel is both at once &mdash; and the
<b>per-tile <span class="mono">block</span> / <span class="mono">string</span> label is the bridge</b>:
the string's series count sets <i>how much</i> reverse-bias heat a failed SCA makes; its physical grid position
sets <i>where</i> that heat goes and which neighbours it cooks.</p>
<p class="slow"><b><span class="mono">panel_from_topology(n_blocks, n_parallel, n_series)</span></b> generates the
physical grid from the electrical topology, tagging every tile with its block and string, ready for
<span class="mono">solve_panel</span>. For 3 blocks (series) &times; 4 parallel &times; 10 series &rarr; a 4&times;30
= 120-cell grid with node bus bars between the series blocks:</p>
<figure><img src="../reports/fig_panel_series_blocks.png"><figcaption>3 blocks IN SERIES &times; 4 parallel
strings &times; 10 series SCAs. Vertical bars N0&ndash;N3 = the nodes where each block's 4 parallels meet;
colour = block; rows = parallel strings; a failed SCA's heat (red) spreads to PHYSICAL neighbours.</figcaption></figure>
<div class="callout"><b>Reverse bias is bounded per block.</b> Because the parallels rejoin at every node, a
failed SCA is back-driven only by its block's ~10-series voltage (not the full 30), and the 3 parallel siblings
shunt around it &mdash; so this architecture limits hot-spots by design.</div>
<h2 class="pb">The zero-voltage case</h2>
<p class="slow">A related analysis: the array's terminal voltage is the algebraic sum along the series path
&mdash; healthy cells add +, reverse-biased cells add &minus;. When they cancel, <b>V_array = 0</b>: no bus
output, yet cells may sit at high reverse bias (a hidden hot-spot). <span class="mono">analysis/voltage.py</span>
computes this and finds the failure that nulls the panel, with vs without bypass diodes.</p>
<table class="tbl"><tr><th>3 blocks &times; 10 series (69 V healthy)</th><th>V &rarr; 0 when&hellip;</th></tr>
<tr><td>No diodes, reverse = forward</td><td><b>15 of 30</b> SCAs reverse-biased (50%)</td></tr>
<tr><td>No diodes, reverse 3&times; forward</td><td>only <b>8 of 30</b> (25%)</td></tr>
<tr><td>With bypass diodes</td><td><b>unreachable</b> &mdash; clamp 0.7 V &Lt; 69 V; diodes prevent it</td></tr></table>''')

# code dumps
for d, a, note, c in ITEMS:
    parts.append("<div class='filehdr'><span class='badge' style='background:%s'>%s</span>"
                 "<span class='path'>%s</span><div class='meta'>%d lines &middot; %s</div></div><pre>%s</pre>"
                 % (BADGE[a], a, html.escape(d), nlines(c), html.escape(note), html.escape(c)))

parts.append("</body></html>")
out = os.path.join(HERE, "Change_Set_Topology_and_Voltage.html")
open(out, "w", encoding="utf-8").write("".join(parts))
print("wrote", out, "(%d files, %d lines)" % (len(ITEMS), total))
