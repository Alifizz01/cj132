# -*- coding: utf-8 -*-
"""Assemble the WHOLE codebase (legacy + existing subsystems + new framework +
LaTeX templates) into ONE printable code-listing PDF, grouped and action-tagged,
for hand-transcription. Vendored ngspice/ is listed but not reproduced.
Run from Notes/ (neutral cwd)."""
import glob
import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SRC = os.path.join(ROOT, "src", "powerpy")
TESTS = os.path.join(ROOT, "tests")

BADGE = {"CREATE": "#1f7a44", "UPDATE": "#b9851a", "REMOVE": "#9a3b3b",
         "LEGACY": "#5d6b79", "EXISTING": "#11507a", "TEMPLATE": "#2f8f6b",
         "DATA": "#6a4ea0", "VENDORED": "#9aa0a6"}

NEW_DIRS = ("config", "model", "solve", "analysis", "reporting")

# ---- curated rich purposes for the NEW framework + key files ----------------
CURATED = {
    "src/powerpy/__init__.py": ("UPDATE", "Package root: layered API docstring + version + power_path; imports NO legacy."),
    "src/powerpy/config/__init__.py": ("CREATE", "config package re-exports (substrate + layout)."),
    "src/powerpy/config/substrate.py": ("CREATE", "Substrate dataclass + loader; c_cond = conductivity/thickness."),
    "src/powerpy/config/layout.py": ("CREATE", "Panel layout convention: grid-map + palette; adjacency & property arrays."),
    "src/powerpy/model/__init__.py": ("CREATE", "model package re-exports (circuit, environment, diode)."),
    "src/powerpy/model/circuit.py": ("CREATE", "Parametric Circuit: topology tree, ids, faults, netlist + probed netlist."),
    "src/powerpy/model/environment.py": ("CREATE", "Orbit fluxes: sun, eclipse, albedo, IR, tilt (was environment_orbit.py)."),
    "src/powerpy/model/diode.py": ("CREATE", "Bypass-diode clamping: reverse-voltage cap -> hot-spot mitigation; spacing scan."),
    "src/powerpy/solve/__init__.py": ("CREATE", "solve package re-exports (thermal, coupling, electrical)."),
    "src/powerpy/solve/thermal.py": ("CREATE", "UNIFIED 2-node solver: solve_thermal(g_lat=0 fast / >0 sparse lateral), solve_panel."),
    "src/powerpy/solve/coupling.py": ("CREATE", "Damped fixed-point electro-thermal coupling loop (was electrothermal.py)."),
    "src/powerpy/solve/electrical.py": ("CREATE", "Probed netlist -> per-cell V*I -> P_elec; make_power_fn for coupling."),
    "src/powerpy/analysis/__init__.py": ("CREATE", "analysis package re-exports (breakdown, montecarlo, study)."),
    "src/powerpy/analysis/breakdown.py": ("CREATE", "Breakdown criteria: temperature OR reverse-power."),
    "src/powerpy/analysis/montecarlo.py": ("CREATE", "3-mode failure sampling, ranking, run-count math."),
    "src/powerpy/analysis/study.py": ("CREATE", "Grid Monte-Carlo failure study with lateral conduction (was panel_study.py)."),
    "src/powerpy/reporting/__init__.py": ("CREATE", "reporting package re-exports (store, report)."),
    "src/powerpy/reporting/store.py": ("CREATE", "Long-format Parquet/HDF5 store + Excel export (was results.py)."),
    "src/powerpy/reporting/report.py": ("CREATE", "HTML panel heat-map report + JSON source of truth."),
}
LEGACY_NOTE = {
    "src/powerpy/cell.py": ("LEGACY", "Legacy cell model. REPAIR: duplicated-self at L156/L436; missing L665-667; isc L274."),
    "src/powerpy/string.py": ("LEGACY", "Legacy series-string model. RENAME (shadows stdlib `string`)."),
    "src/powerpy/eclipse.py": ("REMOVE", "Broken flux path (poliastro/astropy; albedo flagged) -> replaced by model/environment.py."),
    "src/powerpy/thermal.py": ("LEGACY", "Legacy per-cell fsolve thermal solver -> superseded by solve/thermal.py."),
    "src/powerpy/section.py": ("LEGACY", "Legacy parallel-section model (OCR markers)."),
}


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return "# (could not read: %s)" % e


def nlines(s):
    return s.count("\n") + (0 if s.endswith("\n") else 1)


def relpath(abspath):
    return "src/powerpy/" + os.path.relpath(abspath, SRC).replace("\\", "/")


def classify(rel):
    """Return (group, action, purpose) for a src-relative path."""
    if rel in CURATED:
        a, p = CURATED[rel]
        return ("NEW", a, p)
    parts = rel.split("/")              # ['src','powerpy', ...]
    sub = parts[2] if len(parts) > 3 else None
    stem = os.path.splitext(parts[-1])[0]
    if sub in NEW_DIRS:
        return ("NEW", "CREATE", "new %s-layer module" % sub)
    if sub == "loader":
        return ("EXISTING", "EXISTING", "input loader: %s" % stem)
    if sub == "schemas":
        return ("EXISTING", "EXISTING", "data schema: %s" % stem)
    if sub == "simulation":
        return ("EXISTING", "EXISTING", "legacy simulation framework: %s" % stem)
    if sub == "render":
        return ("EXISTING", "EXISTING", "LaTeX report rendering: %s" % stem)
    if sub == "ngspice":
        return ("VENDORED", "VENDORED", "vendored PySpice ngspice binding")
    # top-level module
    if rel in LEGACY_NOTE:
        a, p = LEGACY_NOTE[rel]
        return ("LEGACY", a, p)
    return ("LEGACY", "LEGACY", "legacy core module: %s" % stem)


# ---- discover all source ----------------------------------------------------
py_files = sorted(glob.glob(os.path.join(SRC, "**", "*.py"), recursive=True))
py_files = [p for p in py_files if "__pycache__" not in p and ".agents" not in p]
tex_files = sorted(glob.glob(os.path.join(SRC, "render", "templates", "**", "*.jinja"), recursive=True))
data_files = sorted(glob.glob(os.path.join(SRC, "data", "**", "*.json"), recursive=True))
test_files = sorted(glob.glob(os.path.join(TESTS, "test_*.py")))

groups = {"PACKAGING": [], "NEW": [], "EXISTING": [], "LEGACY": [], "TEMPLATE": [],
          "DATA": [], "TESTS": [], "VENDORED": []}

groups["PACKAGING"].append(("run.py", os.path.join(ROOT, "run.py"), "CREATE",
                            "Zero-install launcher: run from source with vendored deps, NO pip "
                            "(python run.py run LAYOUT.json ...). See docs/RUNNING_WITHOUT_PIP.md."))
groups["PACKAGING"].append(("pyproject.toml", os.path.join(ROOT, "pyproject.toml"), "UPDATE",
                            "Packaging (optional; office laptop runs without it). ngspice is VENDORED in-tree."))

for ab in py_files:
    rel = relpath(ab)
    grp, action, purpose = classify(rel)
    if rel == "src/powerpy/__init__.py":
        groups["PACKAGING"].append((rel, ab, action, purpose)); continue
    groups[grp].append((rel, ab, action, purpose))

for ab in tex_files:
    rel = "src/powerpy/" + os.path.relpath(ab, SRC).replace("\\", "/")
    groups["TEMPLATE"].append((rel, ab, "TEMPLATE", "LaTeX report template (Jinja): %s" % os.path.basename(ab)))

for ab in data_files:
    rel = relpath(ab)
    act = "CREATE" if ("msro_case2" in ab or "example_panel" in ab) else "DATA"
    groups["DATA"].append((rel, ab, act, "data file: %s" % os.path.basename(ab)))

for ab in test_files:
    rel = "tests/" + os.path.basename(ab)
    groups["TESTS"].append((rel, ab, "CREATE", "test suite: %s" % os.path.basename(ab)))

# order of groups in the book; ngspice is index-only (not dumped)
ORDER = [("PACKAGING", "Packaging &amp; package root"),
         ("NEW", "New framework (config / model / solve / analysis / reporting)"),
         ("EXISTING", "Existing subsystems (loader / schemas / simulation / render)"),
         ("LEGACY", "Legacy core modules"),
         ("TEMPLATE", "LaTeX report templates (Jinja)"),
         ("DATA", "Data files"),
         ("TESTS", "Tests")]

# ============================================================ HTML
parts = ["""<!DOCTYPE html><html><head><meta charset="utf-8"><title>PowerPy Full Code Listing</title>
<style>
@page{size:A4;margin:14mm 12mm}
*{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:"Segoe UI",Helvetica,Arial,sans-serif;color:#16222e;margin:0;padding:0}
h1{color:#0b3d63;font-size:26px;margin:0 0 2px}
.sub{color:#5d6b79;font-style:italic;margin:2px 0 14px}
.opener{border:1px solid #d6dde4;border-top:6px solid #0b3d63;border-radius:6px;padding:18mm 12mm}
h2{color:#0b3d63;font-size:15px;margin:14px 0 4px}
.grouphdr{break-before:page;color:#0b3d63;font-size:17px;border-bottom:2px solid #0b3d63;padding-bottom:4px;margin:0 0 8px}
.filehdr{border-left:6px solid #0b3d63;background:#eef3f8;border-radius:5px;padding:7px 11px;margin:14px 0 6px}
.filehdr.first{break-before:auto}
.filehdr .path{font-family:"Cascadia Mono",Consolas,monospace;font-weight:700;color:#0b3d63;font-size:12.5px}
.filehdr .meta{font-size:10.5px;color:#5d6b79;margin-top:2px}
.badge{display:inline-block;color:#fff;font-size:9.5px;font-weight:700;border-radius:3px;padding:1px 7px;letter-spacing:.05em;vertical-align:middle;margin-right:6px}
pre{font-family:"Cascadia Mono",Consolas,monospace;font-size:7.4pt;line-height:1.3;background:#f7f8fa;border:1px solid #e2e6ea;border-radius:5px;padding:8px 10px;white-space:pre-wrap;word-break:break-word;color:#16222e;margin:0 0 6px}
pre.tex{background:#f5f3ee;border-color:#e0d8c4}
table.idx{border-collapse:collapse;width:100%;font-size:9.5px;margin:6px 0}
table.idx td,table.idx th{border:1px solid #d6dde4;padding:3px 6px;text-align:left;vertical-align:top}
table.idx th{background:#eef3f8;color:#0b3d63}
table.idx tr.grp td{background:#0b3d63;color:#fff;font-weight:700;letter-spacing:.04em}
.mono{font-family:"Cascadia Mono",Consolas,monospace}
.small{font-size:11px;color:#5d6b79}
.note{background:#f3f6fa;border:1px solid #d6dde4;border-radius:6px;padding:8px 12px;font-size:11px;margin:8px 0}
</style></head><body>"""]

# counts
n_dump = sum(len(groups[g]) for g, _ in ORDER)
total_lines = 0
for g, _ in ORDER:
    for _, ab, _, _ in groups[g]:
        if ab.endswith(".json") or ab.endswith(".jinja") or ab.endswith(".py") or ab.endswith(".toml"):
            total_lines += nlines(read(ab))

parts.append("""<section class="opener">
<h1>PowerPy &mdash; Full Code Listing</h1>
<div class="sub">The complete codebase: legacy modules, the existing subsystems, the new framework, and the
LaTeX report templates &mdash; grouped, action-tagged, for hand-transcription.</div>
<p class="small">Generated 2026-06-14 &middot; %d files reproduced (+%d LaTeX templates) &middot; ~%d lines.
Action tags: <b>CREATE</b> new, <b>UPDATE</b> modified, <b>EXISTING</b> prior subsystem, <b>LEGACY</b>
older/OCR-damaged, <b>TEMPLATE</b> LaTeX, <b>REMOVE</b> retire. The vendored <span class="mono">ngspice/</span>
PySpice binding (%d files) is listed in the index but not reproduced (it is a third-party dependency,
installable via PySpice). Run tests from the repo root: <span class="mono">python tests/test_*.py</span>.</p>
</section>""" % (n_dump, len(groups["TEMPLATE"]), total_lines, len(groups["VENDORED"])))

# index
idx_rows = []
for g, title in ORDER:
    items = groups[g]
    if not items:
        continue
    idx_rows.append("<tr class='grp'><td colspan='4'>%s &mdash; %d file(s)</td></tr>" % (title, len(items)))
    for rel, ab, action, purpose in items:
        ln = nlines(read(ab))
        idx_rows.append("<tr><td><span class='badge' style='background:%s'>%s</span></td>"
                        "<td class='mono'>%s</td><td style='text-align:right'>%d</td><td>%s</td></tr>"
                        % (BADGE[action], action, html.escape(rel), ln, html.escape(purpose)))
# vendored index rows
if groups["VENDORED"]:
    idx_rows.append("<tr class='grp'><td colspan='4'>Vendored ngspice (PySpice) &mdash; %d file(s), not reproduced</td></tr>" % len(groups["VENDORED"]))
    for rel, ab, action, purpose in groups["VENDORED"]:
        idx_rows.append("<tr><td><span class='badge' style='background:%s'>%s</span></td>"
                        "<td class='mono'>%s</td><td style='text-align:right'>%d</td><td>%s</td></tr>"
                        % (BADGE["VENDORED"], "VENDORED", html.escape(rel), nlines(read(ab)), html.escape(purpose)))

parts.append("<section style='padding:0 12mm'><h2>File index</h2><table class='idx'>"
             "<tr><th>Tag</th><th>File</th><th>Lines</th><th>Purpose</th></tr>"
             + "".join(idx_rows) + "</table>"
             "<div class='note'><b>Reorganization (new framework):</b> the new layers replace the old flat "
             "modules &mdash; <span class='mono'>thermal_vectorized.py + thermal_panel.py &rarr; solve/thermal.py</span> "
             "(merged), <span class='mono'>electrothermal&rarr;solve/coupling</span>, "
             "<span class='mono'>panel_study&rarr;analysis/study</span>, "
             "<span class='mono'>results&rarr;reporting/store</span>, "
             "<span class='mono'>environment_orbit&rarr;model/environment</span>.</div></section>")

# dump each group
for g, title in ORDER:
    items = groups[g]
    if not items:
        continue
    parts.append("<h2 class='grouphdr'>%s</h2>" % title)
    for rel, ab, action, purpose in items:
        src = read(ab)
        cls = "tex" if ab.endswith(".jinja") else ""
        parts.append(
            "<div class='filehdr'><span class='badge' style='background:%s'>%s</span>"
            "<span class='path'>%s</span><div class='meta'>%d lines &middot; %s</div></div>"
            "<pre class='%s'>%s</pre>"
            % (BADGE[action], action, html.escape(rel), nlines(src), html.escape(purpose),
               cls, html.escape(src)))

parts.append("</body></html>")

out = os.path.join(HERE, "PowerPy_Code_Listing.html")
with open(out, "w", encoding="utf-8") as f:
    f.write("".join(parts))
print("wrote %s (%d dumped files, %d templates, %d vendored-indexed, ~%d lines)"
      % (out, n_dump, len(groups["TEMPLATE"]), len(groups["VENDORED"]), total_lines))
