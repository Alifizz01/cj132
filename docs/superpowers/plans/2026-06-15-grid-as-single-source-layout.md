# Grid-as-Single-Source Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **DO NOT START until the `feat/freeform-circuit-layout` branch is untangled from the concurrent power-budget work and this runs on a clean branch off `main` (or off the merged circuit feature).**

**Goal:** Make the 2-D panel grid the single source of truth: derive the electrical circuit from each cell tile's `string` (series) and `block` (parallel section) tags, so the thermal map and electrical circuit can never drift.

**Architecture:** A new `build_array_from_grid` assembles the existing `Cell→String→Section→Panel→Array` tree by grouping cell tiles by `string` (→ series) and strings by `block` (→ parallel). `PanelLayout` gains an optional `circuit_params` block (per-string/block harness R + diode options) parsed from the layout JSON. `build_electrical_report` resolves the electrical source as **circuit override → grid-derived → ArrayLayout legacy**.

**Tech Stack:** Python 3.10+, numpy, openpyxl, pytest. Run tests from repo root with `PYTHONPATH=src python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-06-15-grid-as-single-source-layout-design.md`

**Decisions locked (spec §10):** `string` = series-string id; `block` = parallel-section id; series order = row-major position (no `series_index` — series combine is order-independent for the nominal IV, so it is deferred to a future failure-on-circuit feature); one grid file = one panel; per-string/block params live in a `circuit` block inside the layout JSON.

---

## File Structure

- Modify: `src/powerpy/config/layout.py` — `PanelLayout` gains `circuit_params: dict`; `from_dict` parses an optional `"circuit"` block; add `PanelLayout.cell_strings()` helper.
- Create: `src/powerpy/simulation/grid_build.py` — `build_array_from_grid(...)`.
- Modify: `src/powerpy/schemas/cell.py` — add `grid_reference_file: Path | None = None`.
- Modify: `src/powerpy/loader/cell.py` — read optional `grid_reference_file`.
- Modify: `src/powerpy/app.py` — `build_electrical_report` resolution order (circuit → grid → ArrayLayout).
- Create: `src/powerpy/data/layouts/grid_circuit_demo.json` — small grid with a `circuit` block.
- Test: `tests/test_grid_single_source.py`.

---

### Task 1: `PanelLayout` carries a circuit block + a cell-strings helper

**Files:**
- Modify: `src/powerpy/config/layout.py`
- Test: `tests/test_grid_single_source.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_grid_single_source.py
import numpy as np
from powerpy.config.layout import PanelLayout, TileType, from_dict


def _demo_dict():
    # 2 rows x 3 cols. Row 1 = string s1 (3 cells in series), block bA.
    # Row 2 = string s2 (3 cells), block bA. So block bA has 2 parallel strings.
    return {
        "name": "demo",
        "pitch_mm": 40.0,
        "palette": {
            "1": {"is_cell": True, "string": "s1", "block": "bA"},
            "2": {"is_cell": True, "string": "s2", "block": "bA"},
        },
        "layout": ["1 1 1", "2 2 2"],
        "circuit": {
            "s1": {"n_block_diodes": 1, "block_diode_v_drop": 0.6, "string_shunt_diode": True},
            "bA": {"resistance_ohm": 0.01},
        },
    }


def test_from_dict_parses_circuit_block():
    lay = from_dict(_demo_dict(), substrate=None)
    assert lay.circuit_params["s1"]["n_block_diodes"] == 1
    assert lay.circuit_params["bA"]["resistance_ohm"] == 0.01


def test_circuit_params_defaults_empty_when_absent():
    d = _demo_dict()
    d.pop("circuit")
    lay = from_dict(d, substrate=None)
    assert lay.circuit_params == {}


def test_cell_strings_groups_by_string_and_block():
    lay = from_dict(_demo_dict(), substrate=None)
    strings, string_block = lay.cell_strings()
    # two strings, each 3 cells in series
    assert {sid: len(idxs) for sid, idxs in strings.items()} == {"s1": 3, "s2": 3}
    # both strings live in block bA
    assert string_block == {"s1": "bA", "s2": "bA"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_grid_single_source.py -v`
Expected: FAIL — `AttributeError: 'PanelLayout' object has no attribute 'circuit_params'` (and `cell_strings`).

- [ ] **Step 3: Implement**

In `src/powerpy/config/layout.py`:

(a) add `field` to the dataclasses import at the top:
```python
from dataclasses import dataclass, field
```

(b) add the `circuit_params` field to `PanelLayout` (immediately after the `name: str = ""` line):
```python
    # optional per-string / per-block electrical params (harness R, diode opts),
    # keyed by the same `string`/`block` ids the tiles carry. Empty unless the
    # layout JSON provides a "circuit" block.
    circuit_params: Dict[str, dict] = field(default_factory=dict)
```

(c) add the `cell_strings` method to `PanelLayout` (after `prop_arrays`):
```python
    def cell_strings(self):
        """Group cell tiles into electrical strings.

        Returns ``(strings, string_block)`` where ``strings`` maps a string id to
        the row-major-ordered list of flat tile indices in that series string, and
        ``string_block`` maps a string id to its parallel-section (``block``) id.
        Tiles sharing a ``string`` are the cells of one series string; series order
        is row-major (irrelevant to the nominal IV, which is order-independent).
        """
        strings: Dict[str, List[int]] = {}
        string_block: Dict[str, str] = {}
        for idx, key in enumerate(self.flat_keys()):
            t = self.palette[key]
            if not t.is_cell:
                continue
            sid = t.string or t.key
            strings.setdefault(sid, []).append(idx)
            string_block[sid] = t.block or "block_default"
        return strings, string_block
```

(d) parse the optional `"circuit"` block in `from_dict` — change the final `return PanelLayout(...)` to include it:
```python
    return PanelLayout(grid=grid, palette=palette,
                       pitch_mm=float(d.get("pitch_mm", 40.0)), name=d.get("name", ""),
                       circuit_params=dict(d.get("circuit", {})))
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_grid_single_source.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `PYTHONPATH=src python -m pytest -q`
Expected: PASS (existing layout/thermal tests unaffected — the new field defaults to `{}`).

- [ ] **Step 6: Commit**

```bash
git add src/powerpy/config/layout.py tests/test_grid_single_source.py
git commit -m "feat: PanelLayout carries an optional circuit block + cell_strings() grouping"
```

---

### Task 2: Build the array from a grid

**Files:**
- Create: `src/powerpy/simulation/grid_build.py`
- Test: `tests/test_grid_single_source.py` (append)

- [ ] **Step 1: Append the failing test**

```python
# append to tests/test_grid_single_source.py
from pathlib import Path
from powerpy.loader.report import load_report_data
from powerpy.simulation.grid_build import build_array_from_grid
from powerpy.simulation.environment import Environment

_PARAMS = Path("params.xlsx")
_DATA_DIR = Path("src/powerpy/data")


def test_build_array_from_grid_structure_and_curve():
    report = load_report_data(_PARAMS, _DATA_DIR)
    lay = from_dict(_demo_dict(), substrate=None)
    array = build_array_from_grid(report.cell, lay, lay.circuit_params,
                                  iv_engine="analytic")
    # one panel; one block bA -> one section; two strings in parallel
    assert len(array.panels) == 1
    sections = list(array.iter_sections())
    assert len(sections) == 1
    assert len(sections[0].strings) == 2
    # each string is 3 cells in series
    assert sorted(len(s.cells) for s in sections[0].strings) == [3, 3]
    # nominal curve finite + positive peak power
    array.apply(Environment(temperature_c=28.0))
    v, i = array.iv_curve()
    p = v * i
    assert np.all(np.isfinite(v)) and float(p.max()) > 0.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_grid_single_source.py -k build_array_from_grid -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'powerpy.simulation.grid_build'`

- [ ] **Step 3: Implement `src/powerpy/simulation/grid_build.py`**

```python
"""Assemble the simulation tree from a PanelLayout grid (the single source).

Cell tiles sharing a ``string`` tag are the cells of one series string; strings
sharing a ``block`` tag are in parallel (a block = a section). Per-string and
per-block electrical params come from the layout's ``circuit_params`` block.
Reuses the existing Cell/String/Section/Panel/Array models unchanged.
"""
from __future__ import annotations

from powerpy.schemas.cell import CellParameters
from powerpy.simulation.array_level import ArrayModel
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.panel_level import PanelModel
from powerpy.simulation.section_level import SectionModel
from powerpy.simulation.string_level import StringModel


def build_array_from_grid(
    cell_params: CellParameters,
    layout,
    circuit_params: dict | None = None,
    *,
    iv_engine: str = "analytic",
    string_shunt_vf: float | None = None,
) -> ArrayModel:
    """Build an :class:`ArrayModel` from a :class:`PanelLayout`.

    ``layout`` is a PanelLayout whose cell tiles carry ``string`` (series) and
    ``block`` (parallel section) tags. ``circuit_params`` (defaults to
    ``layout.circuit_params``) supplies per-string / per-block electrical options.
    """
    if circuit_params is None:
        circuit_params = getattr(layout, "circuit_params", {}) or {}

    prototype = CellModel(cell_params, iv_engine=iv_engine)
    strings_idx, string_block = layout.cell_strings()
    if not strings_idx:
        raise ValueError("grid has no cell tiles to build an electrical circuit from")

    # build a StringModel per string, grouped into blocks (parallel sections)
    blocks: dict[str, list] = {}
    for sid, idxs in strings_idx.items():
        p = circuit_params.get(sid, {})
        vf = string_shunt_vf if p.get("string_shunt_diode", True) else None
        string = StringModel.from_single_cell(
            prototype, len(idxs),
            block_diode_v_drop=float(p.get("block_diode_v_drop", 0.6)),
            n_block_diodes=int(p.get("n_block_diodes", 1)),
            series_resistance_ohm=float(p.get("series_resistance_ohm", 0.0)),
            shunt_diode_v_forward=vf,
            name=sid)
        blocks.setdefault(string_block[sid], []).append(string)

    sections = []
    for bid, strs in blocks.items():
        bp = circuit_params.get(bid, {})
        sections.append(SectionModel.from_strings(
            strs, section_resistance_ohm=float(bp.get("resistance_ohm", 0.0)), name=bid))

    panel = PanelModel.from_sections(sections, name=layout.name or "panel")
    return ArrayModel.from_panels([panel])
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_grid_single_source.py -k build_array_from_grid -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/powerpy/simulation/grid_build.py tests/test_grid_single_source.py
git commit -m "feat: build_array_from_grid (PanelLayout -> ArrayModel via string/block tags)"
```

---

### Task 3: Carry `grid_reference_file` on the cell

**Files:**
- Modify: `src/powerpy/schemas/cell.py`
- Modify: `src/powerpy/loader/cell.py`
- Test: `tests/test_grid_single_source.py` (append)

- [ ] **Step 1: Append the failing test**

```python
# append to tests/test_grid_single_source.py
def test_cellparameters_has_optional_grid_reference():
    report = load_report_data(_PARAMS, _DATA_DIR)
    assert hasattr(report.cell, "grid_reference_file")
    ref = report.cell.grid_reference_file
    assert ref is None or ref.name.endswith(".json")
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_grid_single_source.py -k grid_reference -v`
Expected: FAIL — `AttributeError: 'CellParameters' object has no attribute 'grid_reference_file'`

- [ ] **Step 3: Add the schema field.** In `src/powerpy/schemas/cell.py`, in `CellParameters`, immediately AFTER the existing `circuit_reference_file: Path | None = None` line, add:

```python
    # optional grid layout JSON whose cell tiles carry string/block tags; when
    # set (and no circuit override), the electrical circuit is DERIVED from it.
    grid_reference_file: Path | None = None
```

- [ ] **Step 4: Read it in the loader.** In `src/powerpy/loader/cell.py`, AFTER the existing `circuit_ref = values.get("circuit_reference_file")` line, add:

```python
    grid_ref = values.get("grid_reference_file")
```

Then in the `return CellParameters(...)` call, AFTER the existing `circuit_reference_file=circuit_ref,` line, add:

```python
        grid_reference_file=grid_ref,
```

- [ ] **Step 5: Run to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_grid_single_source.py -k grid_reference -v`
Expected: PASS. Then full suite: `PYTHONPATH=src python -m pytest -q` → PASS.

- [ ] **Step 6: Commit**

```bash
git add src/powerpy/schemas/cell.py src/powerpy/loader/cell.py tests/test_grid_single_source.py
git commit -m "feat: optional grid_reference_file on CellParameters"
```

---

### Task 4: Resolution order in the report — circuit → grid → ArrayLayout

**Files:**
- Modify: `src/powerpy/app.py` (`build_electrical_report`, the `_build_array` inner function only)
- Test: `tests/test_grid_single_source.py` (append)

- [ ] **Step 1: Append the failing test**

```python
# append to tests/test_grid_single_source.py
def test_report_uses_grid_when_referenced(tmp_path, monkeypatch):
    import dataclasses
    import powerpy.simulation.grid_build as gb
    import powerpy.loader.report as report_mod
    from powerpy.app import build_electrical_report

    # write a temp grid JSON so the cell can reference it
    import json
    grid_path = tmp_path / "grid.json"
    grid_path.write_text(json.dumps(_demo_dict()), encoding="utf-8")

    called = {"n": 0}
    real = gb.build_array_from_grid

    def spy(cell_params, layout, circuit_params=None, **kw):
        called["n"] += 1
        return real(cell_params, layout, circuit_params, **kw)

    monkeypatch.setattr(gb, "build_array_from_grid", spy)

    real_load = report_mod.load_report_data

    def patched_load(params, data_dir):
        rep = real_load(params, data_dir)
        cell = dataclasses.replace(rep.cell, grid_reference_file=grid_path,
                                   circuit_reference_file=None)
        return dataclasses.replace(rep, cell=cell)

    monkeypatch.setattr(report_mod, "load_report_data", patched_load)

    pdf, labels, rep = build_electrical_report(
        _PARAMS, tmp_path / "out.pdf", data_dir=_DATA_DIR, engine="analytic")
    assert called["n"] >= 1     # grid path was used
    assert labels
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_grid_single_source.py -k report_uses_grid -v`
Expected: FAIL — `build_electrical_report` does not import/use `build_array_from_grid` yet (the spy is never called → `called["n"] == 0` assertion fails).

- [ ] **Step 3: Modify `_build_array` inside `build_electrical_report`**

In `src/powerpy/app.py`, add to the local imports block at the top of `build_electrical_report` (next to the other `.simulation` / `.loader` imports):

```python
    from .loader.circuit import load_circuit          # (already present)
    from .config.layout import load_layout
    from .simulation.circuit_build import build_array_from_circuit   # (already present)
    from .simulation.grid_build import build_array_from_grid
```

Then replace the existing `_build_array` inner function with:

```python
    def _build_array():
        """Resolve the electrical source: free-form circuit override -> grid-derived
        -> ArrayLayout legacy."""
        circuit_ref = getattr(report.cell, "circuit_reference_file", None)
        grid_ref = getattr(report.cell, "grid_reference_file", None)
        if circuit_ref:
            return build_array_from_circuit(
                report.cell, load_circuit(circuit_ref),
                iv_engine=engine, string_shunt_vf=string_shunt_vf)
        if grid_ref:
            layout = load_layout(str(grid_ref))   # substrate=None: optics irrelevant to the circuit
            return build_array_from_grid(
                report.cell, layout, layout.circuit_params,
                iv_engine=engine, string_shunt_vf=string_shunt_vf)
        return build_from_report(report, iv_engine=engine)
```

(Leave the rest of `build_electrical_report` — `_case_result`, the scope/fallback branches, the `Report.from_results` call — unchanged.)

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_grid_single_source.py -k report_uses_grid -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `PYTHONPATH=src python -m pytest -q`
Expected: PASS. The no-grid / no-circuit default still uses `build_from_report` (the circuit and grid refs are both None in the real workbook), so existing report output is unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/powerpy/app.py tests/test_grid_single_source.py
git commit -m "feat: build_electrical_report resolves circuit -> grid -> ArrayLayout"
```

---

### Task 5: Sample grid + end-to-end demonstration

**Files:**
- Create: `src/powerpy/data/layouts/grid_circuit_demo.json`
- Test: `tests/test_grid_single_source.py` (append)

- [ ] **Step 1: Create the sample grid JSON** `src/powerpy/data/layouts/grid_circuit_demo.json`:

```json
{
  "name": "grid_circuit_demo",
  "pitch_mm": 40.0,
  "palette": {
    "1": {"is_cell": true, "string": "s1", "block": "bA", "cell_type": "3G30LARS_GEO"},
    "2": {"is_cell": true, "string": "s2", "block": "bA", "cell_type": "3G30LARS_GEO"},
    "3": {"is_cell": true, "string": "s3", "block": "bB", "cell_type": "3G30LARS_GEO"},
    ".": {"is_cell": false}
  },
  "layout": ["1 1 1 1", "2 2 2 2", "3 3 3 ."],
  "circuit": {
    "s1": {"string_shunt_diode": true},
    "s2": {"string_shunt_diode": true},
    "s3": {"string_shunt_diode": true},
    "bA": {"resistance_ohm": 0.0},
    "bB": {"resistance_ohm": 0.0}
  }
}
```

(Note: `cell_type` "3G30LARS_GEO" matches `data/cells/3G30LARS_GEO.json` so `from_dict` can read its front alpha; `substrate=None` leaves rear optics at defaults, which are irrelevant to the electrical circuit.)

- [ ] **Step 2: Append the end-to-end test**

```python
# append to tests/test_grid_single_source.py
from powerpy.config.layout import load_layout

_SAMPLE_GRID = Path("src/powerpy/data/layouts/grid_circuit_demo.json")


def test_sample_grid_builds_expected_circuit():
    report = load_report_data(_PARAMS, _DATA_DIR)
    lay = load_layout(str(_SAMPLE_GRID))   # substrate=None
    array = build_array_from_grid(report.cell, lay, lay.circuit_params,
                                  iv_engine="analytic")
    sections = list(array.iter_sections())
    # two blocks bA, bB -> two sections; bA has 2 strings, bB has 1
    assert len(sections) == 2
    counts = sorted(len(s.strings) for s in sections)
    assert counts == [1, 2]
    # s1/s2 are 4 cells in series, s3 is 3 (the "." tile generates no power)
    all_series = sorted(len(s.cells) for sec in sections for s in sec.strings)
    assert all_series == [3, 4, 4]
    array.apply(Environment(temperature_c=28.0))
    v, i = array.iv_curve()
    assert float((v * i).max()) > 0.0
```

- [ ] **Step 3: Run to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_grid_single_source.py -k sample_grid -v`
Expected: PASS

- [ ] **Step 4: Run the full suite**

Run: `PYTHONPATH=src python -m pytest -q`
Expected: PASS (all prior + the new grid tests).

- [ ] **Step 5: Commit**

```bash
git add src/powerpy/data/layouts/grid_circuit_demo.json tests/test_grid_single_source.py
git commit -m "feat: sample grid_circuit_demo + end-to-end grid-as-source test"
```

---

## Self-Review

**Spec coverage:**
- §2/§5 derive electrical from grid → Task 2 (`build_array_from_grid`). ✓
- §4 grid additions (circuit params block; `string`/`block` reuse) → Task 1 (`circuit_params`, `cell_strings`). ✓ (`series_index` deliberately omitted — see Decisions note: series combine is order-independent for the nominal IV; deferred to a future failure-on-circuit feature, recorded here so it is not silently dropped.)
- §6 thermal view unchanged → no task needed (no thermal code touched). ✓
- §9 resolution order (circuit → grid → ArrayLayout) → Task 4. ✓
- §3 grid is default electrical source when referenced → Task 3 (`grid_reference_file`) + Task 4. ✓
- §12 validation (cells resolve to string/block) → Task 2 raises on no cell tiles; `cell_strings` falls back string→key and block→"block_default" so every cell resolves. ✓
- §13 backward compat → Task 4 fallback to `build_from_report`; new fields default None/{}. ✓

**Placeholder scan:** No TBD/TODO; every code/step is concrete. ✓

**Type consistency:** `build_array_from_grid(cell_params, layout, circuit_params=None, *, iv_engine, string_shunt_vf)` used identically in Tasks 2, 4, 5. `PanelLayout.circuit_params` (dict) and `PanelLayout.cell_strings() -> (strings, string_block)` used consistently across Tasks 1, 2, 5. `StringModel.from_single_cell(..., shunt_diode_v_forward=)`, `SectionModel.from_strings(..., section_resistance_ohm=)`, `PanelModel.from_sections(..., name=)`, `ArrayModel.from_panels([...])`, `load_layout(path, substrate=None)` all match the verified existing APIs. ✓

**Note on multi-panel:** one grid file = one panel (spec §10.2). A whole array spanning multiple physical panels is represented either as one grid with multiple blocks (sections in parallel — supported here) or, later, by referencing multiple grid files; the latter is a small future extension (a `grid_reference_file` list) and is out of scope for this plan.
