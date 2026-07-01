# Phase 3 — One Output Package: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the three scattered output subsystems — `render/` (LaTeX→PDF), `reporting/` (HTML+JSON + a dead Parquet/Excel store), and the loose openpyxl writer in `scripts/write_results.py` — into ONE `output/` package, with the copy-pasted PDF boilerplate de-duplicated and the dead code deleted.

**Architecture:** `render/` is renamed wholesale to `output/` (the templates travel with it; the `importlib.resources` anchors change from `powerpy.render` to `powerpy.output`). `reporting/report.py` moves in as `output/html.py`; `reporting/store.py` (zero callers, confirmed twice) is deleted along with the `reporting/` package. `write_xlsx` is promoted from `scripts/write_results.py` into `output/excel.py`. The three PDF classes' identical `_templates_dir()` + `compile_pdf()` methods collapse into shared helpers. Finally `analysis/thermal_report.py`/`analysis/montecarlo_report.py` are renamed to `*_data.py` (they compute data, they don't report) and their cross-module private-helper borrowing is made explicit.

**Tech Stack:** Python 3.13, jinja2 templates via importlib.resources, openpyxl, matplotlib; pytest.

## Global Constraints

- **Byte gates** — outputs must be byte-identical to the pre-P3 baselines captured from main 8894373 (scratchpad `p3_baseline/`): `report.tex` + figure PNGs, `results.xlsx` values, panel HTML+JSON.
- No `pip install`; suite runs `PYTHONPATH=src python -m pytest`.
- `pyproject.toml` package-data globs (`data/*`) are unaffected, but check nothing references `render/templates` by path.
- Notes/ doc-generator scripts referencing `powerpy.render` get their imports updated mechanically (they are archived one-shots; imports only, no behaviour work).

## Import sites to update (verified by grep)

| Old | Sites |
|---|---|
| `powerpy.render` | internal cross-imports in the 3 report classes + `__init__` + figures; `app.py:146`; `examples/build_grid_reports.py:37`; `examples/run_montecarlo.py:35`; `Notes/_build_cookbook.py` (8 lines) |
| `ir.files("powerpy.render")` | `render/report.py:44`, `render/thermal_report.py:34`, `render/montecarlo_report.py:23` (collapse to one helper in Task 2) |
| `powerpy.reporting` | `app.py:24`; `src/powerpy/__init__.py:17`; docstrings |

---

### Task 1: rename `render/` → `output/`
`git mv src/powerpy/render src/powerpy/output`; update every import string and the three `ir.files("powerpy.render")` anchors; update `app.py`, both examples, `Notes/_build_cookbook.py`. Gate: full suite green + fresh `report.tex` byte-equal to baseline.

### Task 2: de-dup the PDF boilerplate
The three classes each carry an identical `_templates_dir()` and a near-identical `compile_pdf()` tail. Move one `templates_dir()` into `output/templating.py` (it owns the Jinja env) and one `compile_report_pdf(workdir, out_pdf, jobname)` into `output/compile.py`; the three classes call them. Gate: suite + tex bytes unchanged.

### Task 3: `reporting/report.py` → `output/html.py`; delete `reporting/`
Move the module; update `app.py:24`, `src/powerpy/__init__.py`, and any test imports; delete `reporting/store.py` (dead, zero callers) and the `reporting/` package. Gate: suite + `powerpy run` HTML/JSON byte-equal to baseline.

### Task 4: `write_xlsx` → `output/excel.py`
Promote the writer from `scripts/write_results.py` as `output/excel.py::write_results_xlsx(path, layout_name, summary, strings, cells)`; the script imports it. Gate: `results.xlsx` values identical to baseline.

### Task 5: rename `analysis/*_report.py` → `*_data.py` + un-private the borrowed helpers
`analysis/thermal_report.py` → `analysis/thermal_data.py`, `analysis/montecarlo_report.py` → `analysis/montecarlo_data.py`; `montecarlo_data` imports `cell_optics/cell_palette/p_elec_per_cell` as public names instead of `_underscore` borrowing; update `output/thermal_report.py`, `output/montecarlo_report.py`, `analysis/__init__.py`, tests. Gate: suite.

### Task 6: phase gate
`tests/test_p3_gate.py`: (1) grep-assert no `powerpy.render` / `powerpy.reporting` references remain under `src/`; (2) `output/` exports `Report`, `panel_report`, `write_results_xlsx` from one package; (3) `reporting/store.py` gone. Byte gates re-run manually (tex/xlsx/html/json vs baseline) since they need pdflatex-independent artifacts.

## Self-Review
- Covers design doc §5 fully: one package ✔, de-dup ✔, store.py deleted ✔, `analysis/*_report` renamed + helper borrowing cleaned ✔.
- Risk: the `ir.files` anchor strings are the one non-mechanical piece of Task 1 — they MUST change with the package name or template loading breaks at runtime (caught by the tex byte gate, which actually renders).
- `powerpy analyse` emitting through `output/excel.py` arrives with P4; in P3 its consumer is `scripts/write_results.py`.
