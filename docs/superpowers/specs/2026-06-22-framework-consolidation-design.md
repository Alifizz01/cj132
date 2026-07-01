# powerpy Framework Consolidation — Design (the "proper solution")

> Status: agreed direction, 2026-06-22. Supersedes the *implicit* "two divergent
> paths" architecture. This is the governing design; detailed bite-sized TDD
> plans are written **one per phase** under `docs/superpowers/plans/`.

## 0. The real problem (grounded, verified against source)

The framework feels messy because it serves two use cases over one database —
but that framing is a symptom, not the cause. The verified cause is:

**The unified core (`ArraySpec` + per-cell condition layers, the "approach-B /
per-cell-circuit" work) was fully built and merged to `main` (Phase 0–3), but
the three older paths it replaced were never removed, and the CLI still
dispatches the old ones.** The mess is *transition debris*, not a flaw in the
destination.

Concrete evidence (file-level, from the architecture map 2026-06-22):

1. **4 array builders coexist** — `simulation/array_level.build_from_report`,
   `simulation/grid_build.build_array_from_grid`,
   `simulation/circuit_build.build_array_from_circuit`, and the intended
   replacement `simulation/spec_build.build_array_from_spec`. `app.py::_build_array`
   still forks on the *old* circuit-vs-report path; `spec_build` (the only
   builder that makes one distinct `CellModel` per tile, so conditions can
   attach) is reached only by `scripts/write_results.py`.
2. **Use Case B carries all of A's baggage** — `scripts/write_results.py:131`
   calls `load_report_data` (A's mega-loader) only to read `.cell`, which forces
   validation of `document`, `mission_*`, `sections`, `losses`,
   `radiation_fluxes`, `structure` that B never uses. No `cell`-only entry point
   is exposed.
3. **4 output writers, 3 "report" folders** — PDF (`render/`), HTML+JSON
   (`reporting/report.py`), a **dead** Parquet/HDF5/Excel store
   (`reporting/store.py`, zero callers), and a hand-rolled openpyxl writer in
   `scripts/write_results.py` (outside the package). `analysis/thermal_report.py`
   / `analysis/montecarlo_report.py` are *data* producers misleadingly named
   `*_report`.
4. **A built-but-unwired electro-thermal subsystem** — `solve/electrical.py`,
   `solve/coupling.py`, `solve/transient.py`, plus the 2019 OCR-damaged
   `cell.py` / `electric.py` / `cell_schema.py` / `cell_static.py` stack:
   implemented, tested, **never called in production** (blocked on a `cell.py`
   repair that never happened). `simulation/solver.py` is two
   `NotImplementedError` stubs.
5. **Two divergent workbook builders** — `scripts/build_params.py` and
   `scripts/build_sample_params.py` emit *different sheet names*; the latter
   produces a workbook no current loader reads (dead).
6. **De-scoped machinery still present** — `is_cell`/bare-tile handling and
   lateral conduction (`g_lat`) were explicitly dropped by the owner (approach-B
   REFINEMENTS §1–2) but the code paths remain.

## 1. Target architecture — one pipeline, three stages

A and B are **the same pipeline**. They differ only in how much input is filled
in and which output sink is chosen at the end.

```
   INPUT                         ENGINE                         OUTPUT
   (workbooks -> Scenario)       (one core, fidelity opt-in)    (pick a sink)
   ------------------------      ------------------------       -----------------
   design.xlsx     ┐                                         ┌-> PDF report   (A)
   scenario.xlsx   ├-> resolve -> build_array_from_spec ->   ├-> results.xlsx (B)
   condition layers┘   (snapshot)  run -> results            └-> HTML heatmap/JSON
   (optional; blank = default)
```

**The rule that removes the mess:**
> The simple report = the detailed analysis with the optional condition layers
> left blank.

A leaves condition layers empty -> they default to no-op -> today's nominal
report. B fills them in. One engine, one data model, fidelity opt-in, output
chosen at the end.

The unification axis (one spec feeds both electrical and thermal) is
**orthogonal** to the A-vs-B product split. Both are served by the same
`build_array_from_spec`:
- **A** = `build_array_from_spec` with all-default conditions -> nominal IV -> PDF.
- **B** = `build_array_from_spec` with populated conditions -> `percell_power` +
  thermal -> `results.xlsx`.

## 2. Decisions (locked 2026-06-22)

| # | Decision | Choice |
|---|---|---|
| D1 | Scope | **Full consolidation, phased.** Rewire CLI onto the spec engine, collapse output writers, restructure the database, prune dead/legacy code. |
| D2 | Database | **Two files: `design.xlsx` + `scenario.xlsx`.** This intentionally **reverses** commit `9996b4a` ("single workbook"). |
| D3 | CLI | **Intent verbs: `report` / `analyse` / `sweep`.** Input is a flag, not a separate command. |

Honored constraints (load-bearing, from the specs/README): **no `pip install`**
(run from source via `run.py` / `PYTHONPATH=src`); **analytic engine is the
mandatory path, numpy-only**; **ngspice is a vendored escape hatch with
automatic fallback**; **Python 3.13**, `from __future__ import annotations`
everywhere, every new dataclass field defaulted; **Excel-as-UI**, simulator
consumes a resolved JSON snapshot, not live Excel; **HTML deliverables
self-contained, no CDN**.

## 3. Database — two workbooks

### 3.1 `design.xlsx` (the hardware library — authored once per array)

| Sheet | Format | Holds | From today's |
|---|---|---|---|
| `cell` | key-value | Cell identity, geometry, JSON refs (`cell_reference_file`, shunt/string-diode refs). | `cell_params` |
| `topology` | key-value or grid | The array wiring **in one place**: uniform `n_blocks / n_parallel / n_series`, OR a grid map (string/block tags + harness `series_resistance` / `block_diode_v_drop` / `n_block_diodes` / `string_shunt_diode`). | merges today's split `sections` + `panel` |
| `variance` | key-value | Per-cell manufacturing spread: `imp_sigma`, `pmax_sigma`, `variance_seed` (default 0 = no-op). | from `panel` |

`topology` ends the **three competing array representations** (`sections` sheet
vs grid JSON vs `panel` n_blocks/parallel/series) by giving wiring a single home
that resolves to `ArraySpec` via an adapter.

### 3.2 `scenario.xlsx` (the run — changes every analysis)

| Sheet | Format | Holds | Use case |
|---|---|---|---|
| `losses` | long | Given loss factors by `phase` + `level`. | A + B |
| `mission` | long / key-value | Operating points + environment per launch/phase (bus voltage, temps, fluxes). | A + B |
| `analysis` | table | The scope: which `launch/phase/season/temperature/string_loss/v_operating` configs to run. | A + B |
| `requirement` | key-value | Compliance targets (power/voltage min). | A (compliance line) |
| `layer_state` / `layer_shade` / `layer_life` / `layer_incidence` | grid | Per-cell condition maps; **blank = schema default**. | **B only** |
| `document` | key-value | PDF cover page. | A only |
| `structure` | long | PDF table-of-contents. | A only |

**Minimal sheet-set for a report (A):** `losses` + `analysis` + `mission`
(+ `document`/`structure` for presentation). The `layer_*` sheets are simply
**absent** for A -> conditions default to no-op -> A never sees B's complexity.

### 3.3 Resolution (unchanged — already built in Phase 3)

`setup_sim.py` reads `design.xlsx` + `scenario.xlsx`, normalises the condition
layers to the topology shape, runs `validate_bijection`, and emits a per-run
`runs/<run_id>/snapshot.json` (a serialized `ArraySpec` + `conditions`). The
engine consumes the JSON snapshot, never live Excel. `sun_angle` raw degrees are
resolved to the per-cell `incidence` cosine factor here (the analytic engine
ignores raw angle).

## 4. Engine — one builder

- Keep `simulation/spec_build.build_array_from_spec` as the **single** builder.
- `build_from_report`, `build_array_from_grid`, `build_array_from_circuit` become
  thin `adapt_* -> build_array_from_spec` shims (adapters already exist in
  `simulation/spec_adapt.py`) — or are deleted once nothing imports them.
- `app.py::_build_array` is rewired to resolve a `Scenario` -> `ArraySpec` ->
  `build_array_from_spec`. The old circuit-vs-report fork is removed.
- `analysis/study.make_pe` (the fabricated `+1.1`/`-9.6 W` heuristic) stays as
  the **default fast path** for failure-study dissipation; physics-derived
  per-cell `p_elec` (`simulation/percell_power`) is opt-in behind a flag (per
  approach-B Phase-2 decision). No regression to the 65.26 °C / -9.6 W
  calibration.

## 5. Output — one package

New `output/` package; every renderer consumes the **same** results object
(`SimulationResults` / `CaseResult` / per-cell results):

- `output/pdf.py` — the `Report` builder (from `render/report.py`). Shared
  `_templates_dir()` / `compile_pdf()` helpers de-duplicated (today copy-pasted
  into three render classes).
- `output/excel.py` — the `results.xlsx` writer (promoted from
  `scripts/write_results.write_xlsx` into the package; `summary` / `strings` /
  `cells` sheets).
- `output/html.py` — the panel heat-map + JSON (`reporting/report.panel_report`).

Deleted: `reporting/store.py` (dead). `analysis/thermal_report.py` /
`analysis/montecarlo_report.py` renamed to reflect they compute data, not
reports (e.g. `analysis/thermal.py`), and their cross-module private-helper
borrowing is cleaned up.

## 6. CLI — intent verbs

`src/powerpy/app.py`, one program:

```
powerpy report   [--design design.xlsx] [--scenario scenario.xlsx] [--out report.pdf]
                 # USE CASE A: resolve -> run nominal -> PDF
powerpy analyse  [--design ...] [--scenario ...] [--out results.xlsx] [--thermal] [--engine analytic|ngspice]
                 # USE CASE B: resolve (+condition layers) -> run (+ per-cell thermal) -> results.xlsx
powerpy sweep    [--design ...] [--scenario ...] [--out store.parquet] [--worst] [--max-failures K]
                 # Monte-Carlo / worst-case failure study -> results store
```

- All three share one `resolve -> build -> run` spine; they differ only in the
  output sink and how much condition data they pick up.
- The old layout-JSON `run` / `worst` commands are absorbed: failure injection is
  expressed as condition layers (`state=failed_open`); worst-case search becomes
  `sweep --worst`.
- `scripts/write_results.py` logic moves into `powerpy analyse`.
- `examples/build_noNG_elec_report.py` (verbatim duplicate of `report`) deleted.
- The one-sheet mutator scripts (`add_analysis_sheet`, `add_requirement_sheet`,
  `set_mission_orbit`, `edit_structure`) fold into the workbook templates /
  `setup_sim.py` (no more edit-constant-then-rerun scripts).

## 7. Prune list (dead / superseded — remove during the relevant phase)

Remove only after confirming no live importer remains (tests may need updating):

- `solve/electrical.py`, `solve/coupling.py`, `solve/transient.py` — unwired
  ngspice electro-thermal loop. (Keep `solve/thermal.py` — live.)
- `cell.py`, `electric.py`, `cell_schema.py`, `cell_static.py` — 2019 legacy cell
  stack, only reached via the ngspice fallback.
- `simulation/solver.py` — both functions `NotImplementedError`.
- `reporting/store.py` — dead.
- `analysis/montecarlo.py` generic `run_sweep` / injected-`evaluate` / `rank`
  (keep the RNG/stats helpers `study.py` uses).
- `analysis/voltage.py`, `analysis/breakdown.py` — orphaned, exported as if live.
- `scripts/build_sample_params.py`, `scripts/_gen_build_params.py` — divergent /
  dev-only.
- `is_cell`/bare-tile and lateral-conduction (`g_lat`) code paths — de-scoped by
  the owner.

## 8. Phase map (each phase = one detailed plan, each ends green & committed)

| Phase | Goal | Verification gate |
|---|---|---|
| **P1 — One engine front door** | Add a `Scenario` resolver + rewire `app.py::_build_array` onto `build_array_from_spec` (via adapters). No behaviour change. | Analytic-only `np.allclose(atol<1e-9)` IV + exact Isc/Voc/Pmp/Vmp vs today's `powerpy report` on `simple_3block`, `grid_3x2x12`, and a sections report. |
| **P2 — Two-file database** | Split `params.xlsx` into `design.xlsx` + `scenario.xlsx`; `topology` sheet absorbs `sections`+`panel`; lazy/partial loaders; `cell`-only entry point for B. | `setup_sim.py` resolves the two files to a snapshot identical to today's; B no longer imports `load_report_data`; a report runs with only the A-minimal sheets present. |
| **P3 — One output package** | Create `output/{pdf,excel,html}.py`; both `report` and `analyse` emit through it; delete `reporting/store.py`; de-dup the render boilerplate. | `powerpy report` PDF byte-equivalent figures; `powerpy analyse` produces the same `results.xlsx` as today's `write_results.py`. |
| **P4 — CLI intent verbs** | Implement `report` / `analyse` / `sweep`; absorb `run`/`worst`; move `write_results` into `analyse`; delete the duplicate example + mutator scripts. | Each verb runs end-to-end on the two-file DB; old commands' outputs reproduced; `--help` is clean. |
| **P5 — Prune** | Delete the §7 dead/legacy/ de-scoped code; drop `is_cell` + `g_lat`. | Full test suite green with the dead modules gone; `grep` confirms no live import of any removed symbol. |

Phases are ordered so each leaves a working tree: P1 makes the new engine the
single path *without* changing behaviour (safest first), P5 (deletion) is last
so nothing is removed until its replacement is proven.

## 9. Open items — RESOLVED (user confirmed 2026-07-01: "do all your recommendations")

1. `topology` sheet: **both forms.** Uniform `n_blocks/n_parallel/n_series`
   keys for simple arrays, plus an optional `grid_file` key referencing a grid
   layout JSON for spatial arrays. (A native in-Excel grid map can be added
   later if needed; the JSON layout schema already carries string/block tags and
   harness params.)
2. `sweep` output: **Excel summary only** (works in the locked-down offline
   environment, no pyarrow). The Parquet long-table stays deleted with
   `store.py`.
3. Legacy ngspice cell stack: **prune in P5** (cell.py / electric.py /
   cell_schema.py / cell_static.py and the unwired solve/ electro-thermal loop).
   The vendored `powerpy.ngspice` package and the analytic fallback stay.

P2 implementation note (conscious simplification vs §3.1): the `topology` sheet
absorbs the old `panel` sheet wholesale (same key-value format, extended with
`grid_file`), including the variance keys — no separate `variance` sheet. One
sheet, one loader, fewer moving parts. Also, P2 keeps today's sheet NAMES
(`cell_params`, `sections`, `mission_param`, ...) — the split is by FILE;
cosmetic renames are deferred so no loader schema changes are needed.

**STATUS: P1 merged to main 2026-06-22 (081f7fb), verified bit-identical.**
