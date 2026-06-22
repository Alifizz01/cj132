# Phase 1 — One Engine Front Door: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `simulation/spec_build.build_array_from_spec` the single array builder behind the `powerpy report` path, with zero change to any reported number.

**Architecture:** Today `app.py::build_electrical_report` has a nested `_build_array()` that forks across three *legacy* builders (`build_array_from_circuit` / `build_array_from_grid` / `build_from_report`). The adapters (`spec_adapt.adapt_circuit/adapt_grid/adapt_sections`) already re-express each input as an `ArraySpec`, and existing tests prove `adapt_sections`/`adapt_circuit` + `build_array_from_spec` reproduce the legacy IV to `atol=1e-9`. P1 introduces one `build_array_for_report()` dispatcher over the adapters, lets `pipeline.evaluate` accept a pre-built array, rewires both report paths (scope-driven and phase-fallback) onto it, and adds a whole-report equality gate. No behaviour change — only the path the array is built through.

**Tech Stack:** Python 3.13, numpy, pandas, openpyxl; pytest; run from source (no install).

## Global Constraints

- **No `pip install`** — run from source: tests run as `PYTHONPATH=src python -m pytest` (PowerShell: `$env:PYTHONPATH='src'; python -m pytest`).
- **Analytic engine is the mandatory path** — every new call defaults `iv_engine="analytic"`; ngspice stays an opt-in escape hatch.
- **`from __future__ import annotations`** at the top of every new/edited module; every new dataclass field defaulted.
- **No behaviour change in P1** — the equality gate (`atol=1e-9` on the analytic engine) is the definition of done. If any input kind fails to match, that is a finding to record, not a number to "fix" by loosening the tolerance.
- Tests that need `params.xlsx` use the existing skip guard: `pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")`.

---

## File Structure

- **Create:** `src/powerpy/simulation/report_build.py` — one function, `build_array_for_report(report, *, grid_file, iv_engine)`, that picks the right adapter and calls `build_array_from_spec`. One clear responsibility: "report inputs → spec-built ArrayModel".
- **Modify:** `src/powerpy/simulation/pipeline.py` — add an optional `array=` parameter to `evaluate()` so a pre-built array can be reused instead of `build_from_report`.
- **Modify:** `src/powerpy/app.py:160-228` — replace the `_build_array()` closure with a call to `build_array_for_report`; pass the pre-built array into `evaluate` on the fallback path.
- **Create:** `tests/test_report_build.py` — build-level equality (sections / grid / circuit) + whole-report equality gate.

---

### Task 1: `build_array_for_report` dispatcher + build-level equality

**Files:**
- Create: `src/powerpy/simulation/report_build.py`
- Test: `tests/test_report_build.py`

**Interfaces:**
- Consumes: `spec_adapt.adapt_grid(layout)`, `adapt_sections(array_layout)`, `adapt_circuit(circuit)`; `spec_build.build_array_from_spec(cell_params, spec, *, iv_engine="analytic", string_shunt_vf=None, conditions=None)`; `config.layout.load_layout(path)`; `loader.circuit.load_circuit(ref)`; `report.cell.circuit_reference_file` / `report.cell.grid_reference_file` / `report.cell.string_diode.v_forward`; `report.array_layout`.
- Produces: `build_array_for_report(report, *, grid_file: str | None = None, iv_engine: str = "analytic") -> ArrayModel` — mirrors today's `app.py::_build_array` dispatch order (circuit ref → grid ref/grid_file → sections fallback).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report_build.py
from pathlib import Path

import numpy as np
import pytest

from powerpy.loader.report import load_report_data
from powerpy.loader.circuit import load_circuit
from powerpy.config.layout import load_layout
from powerpy.simulation.report_build import build_array_for_report
from powerpy.simulation.array_level import build_from_report
from powerpy.simulation.circuit_build import build_array_from_circuit
from powerpy.simulation.grid_build import build_array_from_grid
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "src" / "powerpy" / "param" / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
GRID = DATA / "layouts" / "grid_3x2x12.json"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def _report():
    return load_report_data(PARAMS, DATA)


def _shunt_vf(report):
    return (report.cell.string_diode.v_forward
            if getattr(report.cell, "string_diode", None) else None)


def _iv(array, env):
    array.apply(env)
    return array.iv_curve()


def test_report_build_sections_matches_legacy():
    report = _report()
    env = Environment(temperature_c=28.0)
    v_new, i_new = _iv(build_array_for_report(report), env)
    v_ref, i_ref = _iv(build_from_report(report, iv_engine="analytic"), env)
    assert np.allclose(v_new, v_ref, rtol=0, atol=1e-9)
    assert np.allclose(i_new, i_ref, rtol=0, atol=1e-9)


def test_report_build_grid_matches_legacy():
    report = _report()
    env = Environment(temperature_c=28.0)
    layout = load_layout(str(GRID))
    v_new, i_new = _iv(build_array_for_report(report, grid_file=str(GRID)), env)
    ref = build_array_from_grid(report.cell, layout, layout.circuit_params,
                                iv_engine="analytic", string_shunt_vf=_shunt_vf(report))
    v_ref, i_ref = _iv(ref, env)
    assert np.allclose(v_new, v_ref, rtol=0, atol=1e-9)
    assert np.allclose(i_new, i_ref, rtol=0, atol=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_report_build.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'powerpy.simulation.report_build'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/powerpy/simulation/report_build.py
"""Build the report's ArrayModel through the single spec builder.

Mirrors the dispatch order of the legacy app.py::_build_array (circuit ref ->
grid ref -> report sections), but routes every kind through
spec_adapt + build_array_from_spec so there is one assembly path.
"""
from __future__ import annotations

from powerpy.config.layout import load_layout
from powerpy.loader.circuit import load_circuit
from powerpy.simulation.array_level import ArrayModel
from powerpy.simulation.spec_adapt import adapt_circuit, adapt_grid, adapt_sections
from powerpy.simulation.spec_build import build_array_from_spec


def build_array_for_report(report, *, grid_file: str | None = None,
                           iv_engine: str = "analytic") -> ArrayModel:
    """Return the report array, assembled via build_array_from_spec.

    Dispatch (unchanged from the legacy builder): a free-form circuit JSON if the
    cell references one; else a grid (grid-as-single-source) when referenced or
    passed via ``grid_file``; otherwise the report's section layout.
    """
    string_shunt_vf = (report.cell.string_diode.v_forward
                       if getattr(report.cell, "string_diode", None) else None)

    circuit_ref = getattr(report.cell, "circuit_reference_file", None)
    if circuit_ref:
        spec = adapt_circuit(load_circuit(circuit_ref))
    else:
        grid_ref = grid_file or getattr(report.cell, "grid_reference_file", None)
        if grid_ref:
            spec = adapt_grid(load_layout(grid_ref))
        else:
            spec = adapt_sections(report.array_layout)

    return build_array_from_spec(report.cell, spec, iv_engine=iv_engine,
                                 string_shunt_vf=string_shunt_vf)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_report_build.py -v`
Expected: PASS for both `test_report_build_sections_matches_legacy` and `test_report_build_grid_matches_legacy`.

> **VERIFIED 2026-06-22 (autonomous check):** on `grid_3x2x12.json` the grid path matches exactly (`max|dV|=0`, `max|dI|≈9e-16`, Pmp 197.9673 W both). **Caveat:** that grid's `circuit_params` are all *defaults* (`resistance_ohm: 0.0`, `string_shunt_diode: True`). `adapt_grid` (spec_adapt.py:17-47) **does not read `layout.circuit_params` at all** — it emits default `StringSpec`s. So the gate passes here only because the defaults coincide. A grid carrying non-default per-string knobs (real series resistance, `n_block_diodes>1`, or `string_shunt_diode: False`) would silently diverge. See Task 1b.

If `test_report_build_grid_matches_legacy` FAILS on a non-default grid: do NOT loosen the tolerance — go to Task 1b.

- [ ] **Step 5: Commit**

```bash
git add src/powerpy/simulation/report_build.py tests/test_report_build.py
git commit -m "feat(p1): single spec-based array builder for the report path"
```

---

### Task 2: `evaluate()` accepts a pre-built array

**Files:**
- Modify: `src/powerpy/simulation/pipeline.py:163-214` (the `evaluate` function)
- Test: `tests/test_report_build.py` (append)

**Interfaces:**
- Consumes: existing `evaluate(report, cases, *, bus_voltage_v=None, launch_config=LaunchConfig.SINGLE, build_kwargs=None)`.
- Produces: `evaluate(..., array=None)` — when `array` is given, it is used as-is and `build_from_report` is NOT called; `build_kwargs` is ignored in that case. Behaviour with `array=None` is unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report_build.py  (append)
from powerpy.simulation.pipeline import evaluate, AnalysisCase
from powerpy.schemas import Phase


def _first_phase(report):
    return sorted({f.phase for f in report.losses}, key=lambda p: p.value)[0]


def test_evaluate_with_prebuilt_array_matches_internal_build():
    report = _report()
    phase = _first_phase(report)
    cases = [AnalysisCase(label=str(phase), phase=phase)]

    ref = evaluate(report, cases, build_kwargs={"iv_engine": "analytic"})
    pre = evaluate(report, cases, array=build_array_for_report(report))

    r0, p0 = ref[0].results.array, pre[0].results.array
    assert np.isclose(r0.p_mp, p0.p_mp, rtol=0, atol=1e-9)
    assert np.isclose(r0.v_mp, p0.v_mp, rtol=0, atol=1e-9)
    assert np.isclose(r0.i_mp, p0.i_mp, rtol=0, atol=1e-9)
    assert np.isclose(r0.isc, p0.isc, rtol=0, atol=1e-9)
    assert np.isclose(r0.voc, p0.voc, rtol=0, atol=1e-9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_report_build.py::test_evaluate_with_prebuilt_array_matches_internal_build -v`
Expected: FAIL — `TypeError: evaluate() got an unexpected keyword argument 'array'`.

- [ ] **Step 3: Write minimal implementation**

In `src/powerpy/simulation/pipeline.py`, change the `evaluate` signature and the single build line. Current (pipeline.py:163-178):

```python
def evaluate(
    report: ReportMetadata,
    cases: Iterable[AnalysisCase],
    *,
    bus_voltage_v: float | None = None,
    launch_config: LaunchConfig = LaunchConfig.SINGLE,
    build_kwargs: dict | None = None,
) -> list[CaseResult]:
    ...
    array = build_from_report(report, **(build_kwargs or {}))
```

Replace with:

```python
def evaluate(
    report: ReportMetadata,
    cases: Iterable[AnalysisCase],
    *,
    bus_voltage_v: float | None = None,
    launch_config: LaunchConfig = LaunchConfig.SINGLE,
    build_kwargs: dict | None = None,
    array: ArrayModel | None = None,
) -> list[CaseResult]:
    ...
    if array is None:
        array = build_from_report(report, **(build_kwargs or {}))
```

(Leave the rest of `evaluate` untouched. `ArrayModel` is already imported at pipeline.py:29.)

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_report_build.py -v`
Expected: all three tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/powerpy/simulation/pipeline.py tests/test_report_build.py
git commit -m "feat(p1): evaluate() can reuse a pre-built array"
```

---

### Task 3: Rewire `app.py` onto the dispatcher + whole-report equality gate

**Files:**
- Modify: `src/powerpy/app.py:120-230` (the `build_electrical_report` body)
- Test: `tests/test_report_build.py` (append the report-level gate)

**Interfaces:**
- Consumes: `build_array_for_report` (Task 1), `evaluate(..., array=...)` (Task 2).
- Produces: `build_electrical_report` unchanged signature/return `(pdf, phases, report)`; both the scope-driven and phase-fallback paths build their array via `build_array_for_report`.

- [ ] **Step 1: Write the failing test (the gate)**

```python
# tests/test_report_build.py  (append)
import dataclasses
from powerpy.loader.analysis import load_analysis_scope
from powerpy.simulation.pipeline import environment_for_phase, run, CompliancePoint


def test_whole_report_numbers_unchanged_scope_path():
    """Every scoped case's array MPP + bus power is identical old-vs-new."""
    report = _report()
    scope = load_analysis_scope(PARAMS)
    if not scope:
        pytest.skip("no analysis sheet -> scope path not exercised")

    legacy = build_from_report(report, iv_engine="analytic")
    spec = build_array_for_report(report)

    for cfg in scope:
        env = environment_for_phase(
            report, phase=cfg.phase, launch_config=cfg.launch,
            temperature_c=cfg.temperature_c, season=cfg.season,
            angle_alpha_deg=cfg.sun_angle_deg)
        if cfg.string_loss != 1.0:
            env = dataclasses.replace(env, current_loss=env.current_loss * cfg.string_loss)
        r_leg = run(legacy, env).array
        r_new = run(spec, env).array
        for attr in ("isc", "voc", "v_mp", "i_mp", "p_mp"):
            assert np.isclose(getattr(r_leg, attr), getattr(r_new, attr),
                              rtol=0, atol=1e-9), (cfg.label, attr)
```

- [ ] **Step 2: Run test to verify it fails or passes-against-legacy**

Run: `PYTHONPATH=src python -m pytest tests/test_report_build.py::test_whole_report_numbers_unchanged_scope_path -v`
Expected: PASS (it compares two builders directly; it is the *gate* that must stay green after Step 3 rewires `app.py`). If it FAILS now, a builder divergence exists — STOP and record it (same rule as Task 1 Step 4).

- [ ] **Step 3: Rewire `app.py::build_electrical_report`**

In `src/powerpy/app.py`, add the import near the other local imports inside `build_electrical_report` (the heavy-imports block at app.py:135-145):

```python
    from .simulation.report_build import build_array_for_report
```

Replace the nested `_build_array()` closure (app.py:160-175) and its call site (app.py:178, `array = _build_array()`) — delete the closure and write:

```python
    array = build_array_for_report(report, grid_file=grid_file, iv_engine=engine)
```

In the FALLBACK path (no analysis sheet, app.py:217-230), change the `evaluate` call to pass the pre-built array so it too goes through the spec builder:

```python
    cases = [AnalysisCase(label=ph, phase=ph) for ph in phases]
    case_results = evaluate(report, cases, array=array)
    rpt = Report.from_results(report, case_results, array=array, iv_engine=engine)
```

(Note: the fallback previously called `Report.from_results(report, case_results, build_array=True, ...)` and let `evaluate` build internally. Now `array` is already built at the top of the function for both paths, so pass it through and drop `build_array=True`.) Move the single `array = build_array_for_report(...)` line so it runs for BOTH the `if scope:` and fallback branches (i.e. build it once, before the `if scope:` test).

- [ ] **Step 4: Run the full suite + the gate + a real report**

Run: `PYTHONPATH=src python -m pytest tests/ -q`
Expected: all pass (no regressions in `test_pipeline.py`, `test_cli.py`, `test_spec_adapt_*`).

Run the actual report and eyeball the phase line + doc number are unchanged:
`PYTHONPATH=src python run.py report --out reports/_p1_check.pdf`
Expected: same `phases :` list and per-phase behaviour as before P1; `OK -> ...pdf` (or the "pdflatex not found" workspace-only message on a machine without LaTeX — still a pass for P1, since the gate is the numeric test, not the PDF).

- [ ] **Step 5: Commit**

```bash
git add src/powerpy/app.py tests/test_report_build.py
git commit -m "feat(p1): report path builds via the single spec builder (no behaviour change)"
```

---

## Self-Review

- **Spec coverage:** P1 in the design doc = "rewire `app.py::_build_array` onto `build_array_from_spec` (via adapters), no behaviour change, analytic `allclose` gate." Task 1 = dispatcher; Task 2 = let `evaluate` reuse it; Task 3 = rewire both report paths + whole-report gate. Covered.
- **Not in P1 (deferred):** the legacy builders (`build_from_report`/`build_array_from_grid`/`build_array_from_circuit`) are still imported by their tests and by the adapters' regression tests — they are NOT deleted here (that is P5, after every consumer is off them). P1 only stops `app.py` from calling them directly.
- **Type consistency:** `build_array_for_report(report, *, grid_file=None, iv_engine="analytic") -> ArrayModel` is used identically in Tasks 1, 2, 3. `evaluate(..., array=None)` matches between Task 2 def and Task 3 call.
- **Open risk (now characterised, 2026-06-22):** `adapt_grid` ignores `layout.circuit_params`. The current fixtures pass because their circuit_params are all-default, but the grid path is NOT generally equivalent. Do Task 1b before relying on the grid path for any non-default grid. The sections path (the workbook default) is fully equivalent and unaffected, so Task 3 can proceed for the shipping report; Task 1b is required only to make the grid input safe.

---

### Task 1b (conditional): teach `adapt_grid` to carry `circuit_params`

Do this task **only if** a real grid with non-default `circuit_params` must round-trip (otherwise the all-default grids already match). It removes the latent divergence found on 2026-06-22.

**Files:**
- Modify: `src/powerpy/simulation/spec_adapt.py:17-47` (`adapt_grid`)
- Test: `tests/test_report_build.py` (append a non-default-grid case)

**Interfaces:**
- Produces: `adapt_grid(layout, *, panel_id="panel_1", section_id="sec_grid")` unchanged signature, but each `StringSpec` now reads its per-string knobs (`series_resistance_ohm`, `block_diode_v_drop`, `n_block_diodes`, `string_shunt_diode`) and each `SectionSpec` its `resistance_ohm` from `layout.circuit_params[tag]`, falling back to the schema defaults when a key is absent.

- [ ] **Step 1: Write the failing test** — build a small grid JSON whose `circuit_params` set a non-default `string_shunt_diode: False` on one string and `resistance_ohm` on its block, then assert `adapt_grid + build_array_from_spec` matches `build_array_from_grid` to `atol=1e-9`. (Reuse the `_iv`/`_shunt_vf` helpers already in the test module.)
- [ ] **Step 2: Run it — expect FAIL** (the non-default knob is dropped, IV differs).
- [ ] **Step 3: Implement** — in `adapt_grid`, look up `cp = layout.circuit_params.get(tag, {})` per string tag and pass its keys into `StringSpec(...)`; look up the block tag's `resistance_ohm` for the `SectionSpec`. Match exactly how `build_array_from_grid` consumes `circuit_params` (read that function first to mirror its key names and defaults).
- [ ] **Step 4: Run it — expect PASS**, and re-run the whole `tests/test_report_build.py` to confirm the all-default grid still matches.
- [ ] **Step 5: Commit** — `git commit -m "fix(p1): adapt_grid carries per-string circuit_params"`.

## Execution Handoff

Two options:
1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** — execute Tasks 1–3 in-session with checkpoints.
