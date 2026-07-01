# Phase 2 — Two-File Database: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the single `params.xlsx` into `design.xlsx` (the hardware: cell, topology, variance) and `scenario.xlsx` (the run: losses, mission, scope, conditions, report-meta), so use case B stops carrying use case A's baggage — with a legacy single-file mode that keeps every existing workflow working.

**Architecture:** Every loader already takes the workbook path as its first argument, so the split is *routing*, not rewriting: a `Workbooks` pair says which file each sheet lives in. `load_report_data` grows an optional `scenario_file` (defaulting to the same file = legacy mode). B (`write_results.py`, `setup_sim.py`) switches from the `load_report_data` mega-loader to the existing `load_cell_parameters` direct entry. A new `topology` sheet (in design.xlsx) absorbs the old `panel` sheet and adds an optional `grid_file` key for spatial arrays. A migration script splits an existing workbook.

**Tech Stack:** Python 3.13, openpyxl, pandas, numpy; pytest; run from source (no install).

## Global Constraints

- **No `pip install`** — tests run as `PYTHONPATH=src python -m pytest`.
- **Legacy single-file mode must keep working end-to-end** until P4 retires it: `powerpy report` with the shipped `params.xlsx`, `write_results.py --params params.xlsx`, and `setup_sim.py --wb params.xlsx` all behave exactly as today.
- **No numeric change** — the split pair must reproduce the single-file report and results.xlsx bit-identically (`atol=1e-9` gates, same pattern as P1).
- `from __future__ import annotations` in every new/edited module; new dataclass fields defaulted.
- Sheet NAMES stay as today (`cell_params`, `sections`, `mission_param`, ...). The split is by FILE. (Renames deferred — see design doc §9.)

## Sheet routing (the single source of truth for this plan)

| File | Sheets |
|---|---|
| `design.xlsx` | `cell_params`, `sections`, `topology` (new — absorbs `panel`, adds `grid_file`; legacy `panel` kept as fallback) |
| `scenario.xlsx` | `losses`, `radiation_fluxes`, `mission_orbit`, `mission_param`, `analysis`, `requirement`, `document`, `structure`, `layer_state`, `layer_shade`, `layer_life`, `layer_incidence` |

---

### Task 1: `Workbooks` pair + discovery

**Files:**
- Create: `src/powerpy/loader/workbooks.py`
- Test: `tests/test_workbooks.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) Workbooks: design: Path; scenario: Path` with `Workbooks.legacy(path) -> Workbooks` (both fields = same file) and `is_split` property (`design != scenario`).
- Produces: `find_workbooks(design=None, scenario=None, legacy_params=None, search_dirs=(...)) -> Workbooks`: explicit pair wins; a lone `legacy_params` (or lone `design`) gives legacy mode; otherwise search each dir for `design.xlsx`+`scenario.xlsx` together, then for `params.xlsx`. Raises `FileNotFoundError` with the searched locations if nothing is found.

- [ ] **Step 1: failing test** — `tests/test_workbooks.py`: legacy fallback (`find_workbooks(legacy_params=<params.xlsx>)` → `design == scenario == params.xlsx`, `is_split is False`); explicit pair honored (`is_split is True`); a tmp dir containing both `design.xlsx` and `scenario.xlsx` is discovered as a pair; empty tmp dir raises `FileNotFoundError`.
- [ ] **Step 2: run — expect FAIL** (`ModuleNotFoundError`). `PYTHONPATH=src python -m pytest tests/test_workbooks.py -v`
- [ ] **Step 3: implement** `loader/workbooks.py` (~50 lines, stdlib + dataclasses only).
- [ ] **Step 4: run — expect PASS.**
- [ ] **Step 5: commit** — `feat(p2): Workbooks pair + discovery (legacy single-file fallback)`

---

### Task 2: `scripts/split_params.py` — migrate one workbook into two

**Files:**
- Create: `scripts/split_params.py`
- Test: `tests/test_split_params.py`

**Interfaces:**
- Produces: `split_params(params_path, design_path, scenario_path, *, overwrite=False) -> tuple[Path, Path]` — copies each sheet (values only) into its routed file per the table above; unknown sheets go to `scenario.xlsx` with a printed warning; the `panel` sheet is copied into design.xlsx **and** duplicated as a `topology` sheet (same rows) so Task 5's loader finds it. Refuses to clobber existing outputs unless `overwrite=True`.
- CLI: `python scripts/split_params.py [params.xlsx] [--out-dir DIR] [--overwrite]`.

- [ ] **Step 1: failing test** — split the live `src/powerpy/param/params.xlsx` into a tmp dir; assert design.xlsx has exactly `{cell_params, sections, panel, topology}` and scenario.xlsx the 12 scenario sheets; spot-check identical cell values (e.g. `cell_params` B-column entries, one `losses` row) between source and split copies.
- [ ] **Step 2: run — expect FAIL.**
- [ ] **Step 3: implement** with openpyxl (`load_workbook(data_only=True)`, new workbooks, row-wise value copy).
- [ ] **Step 4: run — expect PASS.**
- [ ] **Step 5: commit** — `feat(p2): split_params migration script (one workbook -> design + scenario)`

---

### Task 3: `load_report_data` becomes pair-aware; `powerpy report` gets `--design/--scenario`

**Files:**
- Modify: `src/powerpy/loader/report.py` (signature + per-sheet routing)
- Modify: `src/powerpy/app.py` (`_find_params` → workbook discovery; `report` subparser flags; `build_electrical_report` threads the pair)
- Test: `tests/test_report_build.py` (append the split-equality gate)

**Interfaces:**
- Consumes: `Workbooks` / `find_workbooks` (Task 1), `split_params` (Task 2, in the test).
- Produces: `load_report_data(params_file, data_dir, *, scenario_file=None) -> ReportMetadata`. `scenario_file=None` ⇒ legacy (everything from `params_file`, byte-identical behaviour). When given: `cell` + `array_layout` from `params_file` (=design); `document`, `mission`, `mission_orbit`, `losses`, `radiation_fluxes`, `structure` from `scenario_file`.
- Produces: `build_electrical_report(params, out_pdf, *, scenario=None, ...)`; `_cmd_report` resolves via `find_workbooks(design=args.design, scenario=args.scenario, legacy_params=args.params)`; `load_analysis_scope` and `load_requirement` read the **scenario** file.

- [ ] **Step 1: failing gate test** — in `tests/test_report_build.py`: split the live workbook into tmp (via `split_params`), then assert `load_report_data(design, DATA, scenario_file=scenario)` equals `load_report_data(params, DATA)` field-by-field (compare `document.doc_number`, `array_layout.n_sca_total`, loss tuple length, mission lookups), and that `build_array_for_report` over both gives `atol=1e-9`-identical IV at 28 °C. Expected first failure: `TypeError: unexpected keyword argument 'scenario_file'`.
- [ ] **Step 2: run — expect FAIL.**
- [ ] **Step 3: implement** routing in `report.py`; add flags + discovery in `app.py` (keep the positional `params` argument working).
- [ ] **Step 4: run gate + full suite — expect PASS.** Also smoke: `PYTHONPATH=src python run.py report --design <tmp>/design.xlsx --scenario <tmp>/scenario.xlsx --out reports/_p2_check.pdf` prints the same `phases :` line as the legacy run, then delete the artifacts.
- [ ] **Step 5: commit** — `feat(p2): report path reads a design+scenario pair (legacy single file unchanged)`

---

### Task 4: use case B drops the mega-loader

**Files:**
- Modify: `scripts/write_results.py` (cell via `load_cell_parameters`; layers from scenario; `--design/--scenario` flags)
- Modify: `scripts/setup_sim.py` (same discovery; layers workbook = scenario file)
- Test: `tests/test_b_path_partial_load.py`

**Interfaces:**
- Consumes: `load_cell_parameters(params_file, data_dir)` (`loader/cell.py`, already exists), `find_workbooks` (Task 1).
- Produces: `write_results.py` builds its cell from **design.xlsx only** and reads `layer_*` from **scenario.xlsx**; it must run successfully against a design file that has **no** `document`/`structure`/`losses` sheets at all (the exact coupling P2 exists to break). `--params` keeps legacy behaviour.

- [ ] **Step 1: failing test** — build a minimal design.xlsx in tmp (copy only `cell_params` + `panel`/`topology` from the live workbook via openpyxl) and a scenario.xlsx with only blank `layer_*` sheets; run `write_results.main(["--design", ..., "--scenario", ..., "--out", tmp/"r.xlsx"])`; assert it exits 0 and the output workbook has `summary/strings/cells` sheets with a positive `Pmpp_W`. Today this raises inside `load_report_data` (missing `document` sheet) — that failure IS the point.
- [ ] **Step 2: run — expect FAIL** (validation error from the mega-loader).
- [ ] **Step 3: implement** — replace `load_report_data(params, ...).cell` with `load_cell_parameters(wbs.design, data_dir)`; route `read_panel_config`/`read_topology` at `wbs.design` and `load_condition_layers` at `wbs.scenario`; same for `setup_sim.py` (`--wb` stays as legacy alias for the scenario/conditions file).
- [ ] **Step 4: run new test + full suite — expect PASS.** Also assert (grep in the test) that `write_results.py` no longer imports `load_report_data`.
- [ ] **Step 5: commit** — `feat(p2): B path loads cell-only from design.xlsx (no report baggage)`

---

### Task 5: `topology` sheet — both forms, `panel` as fallback

**Files:**
- Modify: `src/powerpy/loader/sim_config.py`
- Modify: `scripts/write_results.py`, `scripts/setup_sim.py` (layout resolution via the new reader)
- Test: `tests/test_topology_sheet.py`

**Interfaces:**
- Produces: `read_topology(design_path) -> dict` — reads the `topology` sheet if present, else falls back to `panel` (exact `read_panel_config` semantics). Adds one optional key `grid_file` (str path, may be relative to the workbook's folder). Returned dict: the 7 existing keys + `"grid_file": str|None`.
- Produces: `resolve_layout(cfg, *, base_dir) -> PanelLayout` — `grid_file` set ⇒ `load_layout(path)`; else `panel_from_topology(n_blocks, n_parallel, n_series)`. Both scripts use it; an explicit `--layout` CLI flag still wins over the sheet.

- [ ] **Step 1: failing test** — three cases: (a) workbook with only a legacy `panel` sheet → `read_topology` returns its values, `grid_file is None`; (b) workbook with a `topology` sheet holding uniform keys → same resolution as (a) with equal values; (c) `topology` with `grid_file = grid_3x2x12.json` → `resolve_layout` returns that layout (`n_tiles == 72`) and `write_results.analyse` over it matches a direct `--layout` run's `Pmpp_W` exactly.
- [ ] **Step 2: run — expect FAIL** (`ImportError: read_topology`).
- [ ] **Step 3: implement** in `sim_config.py` (reuse `_FIELDS`; `SHEET_TOPOLOGY = "topology"`); wire both scripts.
- [ ] **Step 4: run new test + full suite — expect PASS.**
- [ ] **Step 5: commit** — `feat(p2): topology sheet (uniform or grid_file) absorbs panel, with legacy fallback`

---

### Task 6: whole-phase gate — snapshot identity + A-minimal report

**Files:**
- Test: `tests/test_p2_gate.py`

- [ ] **Step 1: write the gate tests** (these must pass with no further code change):
  1. **Snapshot identity:** run `setup_sim.run_setup_sim` twice over the same layout — once with the legacy single `params.xlsx` conditions, once with the split scenario.xlsx — and assert the two `snapshot.json` files are byte-identical.
  2. **A-minimal report:** a scenario.xlsx containing NO `layer_*` sheets (delete them from a tmp copy) still produces a report whose scoped MPP numbers equal the legacy run at `atol=1e-9` — A never sees B's sheets.
  3. **Legacy end-to-end:** `build_electrical_report(params.xlsx, ...)` (single file, no flags) still returns the same phases and compiles.
- [ ] **Step 2: run — expect PASS; any failure is a Task 1–5 bug, fix there.**
- [ ] **Step 3: full suite green, commit** — `test(p2): phase gate (snapshot identity, A-minimal report, legacy end-to-end)`

---

## Self-Review

- **Coverage vs design doc P2 row:** split ✔ (T1–T3), topology absorbs sections+panel — *partially deliberate*: `panel` absorbed (T5); the `sections` sheet stays as-is inside design.xlsx (full sections→topology merge deferred to P4 with the CLI rework; noted in design doc §9). Lazy/partial loaders ✔ (T4 breaks the mega-loader coupling; per-sheet loaders were already partial). Cell-only entry for B ✔ (T4). Gate ✔ (T6 = the design doc's three-part gate verbatim).
- **Type consistency:** `Workbooks(design, scenario)` used identically in T1/T3/T4; `read_topology`/`resolve_layout` defined T5, consumed T5 only.
- **Risk:** `load_condition_layers` accepts a path *or* an openpyxl workbook (both call styles exist today — write_results passes a path, setup_sim a wb object); T4 must preserve both.

## Execution Handoff

1. **Subagent-Driven** — fresh subagent per task, review between tasks.
2. **Inline** — execute T1–T6 in-session with gates at each step (as done for P1).
