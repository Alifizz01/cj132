# Free-form Electrical Circuit Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user define the electrical circuit freely in a JSON file (heterogeneous strings, per-element params) and drive the nominal (no-failure) electrical report from it, with all environment factors applied.

**Architecture:** A new `CircuitLayout` schema + JSON loader feeds a builder that assembles the existing `CellModel → StringModel → SectionModel → PanelModel → ArrayModel` tree (reusing all curve-combination, environment, and shunt-diode logic). `build_electrical_report` uses the circuit when `cell_params.circuit_reference_file` is set, else falls back to today's `build_from_report`.

**Tech Stack:** Python 3.10+, numpy, openpyxl, pytest. Run tests with `PYTHONPATH=src python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-06-15-freeform-circuit-electrical-layout-design.md`

---

## File Structure

- Create: `src/powerpy/schemas/circuit.py` — frozen `CircuitLayout/CircuitSection/CircuitString` + validation.
- Create: `src/powerpy/loader/circuit.py` — `load_circuit(json_path)`.
- Create: `src/powerpy/simulation/circuit_build.py` — `build_array_from_circuit(...)`.
- Create: `src/powerpy/data/circuits/msro_nominal.json` — sample circuit.
- Modify: `src/powerpy/schemas/cell.py` — add `circuit_reference_file: Path | None = None`.
- Modify: `src/powerpy/loader/cell.py` — read optional `circuit_reference_file`.
- Modify: `src/powerpy/app.py` — `build_electrical_report` uses the circuit when referenced.
- Test: `tests/test_circuit_layout.py` — schema, loader, builder, integration.

---

### Task 1: CircuitLayout schema

**Files:**
- Create: `src/powerpy/schemas/circuit.py`
- Test: `tests/test_circuit_layout.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_circuit_layout.py
import pytest
from powerpy.schemas.circuit import CircuitLayout, CircuitSection, CircuitString


def _string(id="s1", n=22, **kw):
    return CircuitString(id=id, n_series=n, **kw)


def test_string_defaults_and_validation():
    s = _string()
    assert s.n_series == 22
    assert s.block_diode_v_drop == 0.6
    assert s.string_shunt_diode is True
    with pytest.raises(ValueError):
        _string(n=0)                      # n_series must be >= 1
    with pytest.raises(ValueError):
        CircuitString(id="", n_series=5)  # id required


def test_section_requires_strings_and_unique_ids():
    sec = CircuitSection(id="sec_a", strings=(_string("s1"), _string("s2")))
    assert sec.panel == "panel_1"
    assert len(sec.strings) == 2
    with pytest.raises(ValueError):
        CircuitSection(id="sec_a", strings=())               # >= 1 string
    with pytest.raises(ValueError):
        CircuitSection(id="sec_a", strings=(_string("s1"), _string("s1")))  # dup ids


def test_layout_requires_sections_and_unique_ids():
    lay = CircuitLayout(name="c", sections=(
        CircuitSection(id="a", strings=(_string(),)),
        CircuitSection(id="b", strings=(_string(),)),
    ))
    assert lay.name == "c" and len(lay.sections) == 2
    with pytest.raises(ValueError):
        CircuitLayout(name="c", sections=())
    with pytest.raises(ValueError):
        CircuitLayout(name="c", sections=(
            CircuitSection(id="a", strings=(_string(),)),
            CircuitSection(id="a", strings=(_string(),)),
        ))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_circuit_layout.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'powerpy.schemas.circuit'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/powerpy/schemas/circuit.py
"""Free-form electrical circuit layout (array -> sections -> strings -> cells).

A separate, fully-parameterized circuit specification, decoupled from the
thermal grid. Sections combine in parallel (within a panel, and panels in
parallel across the array); strings combine in parallel within a section; cells
combine in series within a string.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class CircuitString:
    """One string: ``n_series`` cells in series, plus per-string options."""
    id: str
    n_series: int
    series_resistance_ohm: float = 0.0
    block_diode_v_drop: float = 0.6
    n_block_diodes: int = 1
    string_shunt_diode: bool = True

    def __post_init__(self):
        if not self.id:
            raise ValueError("CircuitString.id must be non-empty")
        if self.n_series < 1:
            raise ValueError(
                "CircuitString %r: n_series must be >= 1, got %r"
                % (self.id, self.n_series))
        if self.series_resistance_ohm < 0 or self.block_diode_v_drop < 0:
            raise ValueError("CircuitString %r: resistances/drops must be >= 0" % self.id)
        if self.n_block_diodes < 0:
            raise ValueError("CircuitString %r: n_block_diodes must be >= 0" % self.id)


@dataclass(frozen=True)
class CircuitSection:
    """A parallel group of strings on one panel."""
    id: str
    strings: Tuple[CircuitString, ...]
    panel: str = "panel_1"
    resistance_ohm: float = 0.0

    def __post_init__(self):
        if not self.id:
            raise ValueError("CircuitSection.id must be non-empty")
        if not self.strings:
            raise ValueError("CircuitSection %r: needs >= 1 string" % self.id)
        if self.resistance_ohm < 0:
            raise ValueError("CircuitSection %r: resistance_ohm must be >= 0" % self.id)
        ids = [s.id for s in self.strings]
        if len(set(ids)) != len(ids):
            raise ValueError("CircuitSection %r: duplicate string ids %s" % (self.id, ids))


@dataclass(frozen=True)
class CircuitLayout:
    """The whole circuit: sections combined in parallel (grouped by panel)."""
    name: str
    sections: Tuple[CircuitSection, ...]

    def __post_init__(self):
        if not self.sections:
            raise ValueError("CircuitLayout: needs >= 1 section")
        ids = [s.id for s in self.sections]
        if len(set(ids)) != len(ids):
            raise ValueError("CircuitLayout: duplicate section ids %s" % ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_circuit_layout.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/powerpy/schemas/circuit.py tests/test_circuit_layout.py
git commit -m "feat: CircuitLayout schema for free-form electrical circuits"
```

---

### Task 2: Circuit JSON loader + sample file

**Files:**
- Create: `src/powerpy/loader/circuit.py`
- Create: `src/powerpy/data/circuits/msro_nominal.json`
- Test: `tests/test_circuit_layout.py` (append)

- [ ] **Step 1: Create the sample circuit JSON**

```json
{
  "name": "msro_nominal",
  "sections": [
    {
      "id": "sec_a",
      "panel": "panel_1",
      "resistance_ohm": 0.0,
      "strings": [
        { "id": "s1", "n_series": 22, "series_resistance_ohm": 0.0,
          "block_diode_v_drop": 0.6, "n_block_diodes": 1, "string_shunt_diode": true },
        { "id": "s2", "n_series": 22, "string_shunt_diode": true }
      ]
    },
    {
      "id": "sec_b",
      "panel": "panel_1",
      "strings": [
        { "id": "s1", "n_series": 20 }
      ]
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

```python
# append to tests/test_circuit_layout.py
from pathlib import Path
from powerpy.loader.circuit import load_circuit

_SAMPLE = Path("src/powerpy/data/circuits/msro_nominal.json")


def test_load_circuit_parses_sample():
    c = load_circuit(_SAMPLE)
    assert c.name == "msro_nominal"
    assert [s.id for s in c.sections] == ["sec_a", "sec_b"]
    sec_a = c.sections[0]
    assert sec_a.panel == "panel_1"
    assert [s.id for s in sec_a.strings] == ["s1", "s2"]
    assert sec_a.strings[0].n_series == 22
    # defaults applied where omitted
    assert sec_a.strings[1].block_diode_v_drop == 0.6
    assert c.sections[1].strings[0].n_series == 20
    assert c.sections[1].resistance_ohm == 0.0


def test_load_circuit_missing_file():
    with pytest.raises(FileNotFoundError):
        load_circuit(Path("does/not/exist.json"))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_circuit_layout.py -k load_circuit -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'powerpy.loader.circuit'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/powerpy/loader/circuit.py
"""Load a free-form circuit JSON into a CircuitLayout."""
from __future__ import annotations

import json
from pathlib import Path

from powerpy.schemas.circuit import CircuitLayout, CircuitSection, CircuitString


def load_circuit(json_path: Path) -> CircuitLayout:
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError("circuit file not found: %s" % json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sections = []
    for sec in data.get("sections", []):
        strings = tuple(
            CircuitString(
                id=str(s["id"]),
                n_series=int(s["n_series"]),
                series_resistance_ohm=float(s.get("series_resistance_ohm", 0.0)),
                block_diode_v_drop=float(s.get("block_diode_v_drop", 0.6)),
                n_block_diodes=int(s.get("n_block_diodes", 1)),
                string_shunt_diode=bool(s.get("string_shunt_diode", True)),
            )
            for s in sec.get("strings", [])
        )
        sections.append(CircuitSection(
            id=str(sec["id"]),
            strings=strings,
            panel=str(sec.get("panel", "panel_1")),
            resistance_ohm=float(sec.get("resistance_ohm", 0.0)),
        ))
    return CircuitLayout(name=str(data.get("name", json_path.stem)),
                         sections=tuple(sections))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_circuit_layout.py -k load_circuit -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add src/powerpy/loader/circuit.py src/powerpy/data/circuits/msro_nominal.json tests/test_circuit_layout.py
git commit -m "feat: load_circuit JSON loader + sample circuit"
```

---

### Task 3: Build the simulation tree from a circuit

**Files:**
- Create: `src/powerpy/simulation/circuit_build.py`
- Test: `tests/test_circuit_layout.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_circuit_layout.py
import numpy as np
from powerpy.loader.report import load_report_data
from powerpy.simulation.circuit_build import build_array_from_circuit
from powerpy.simulation.environment import Environment

_DATA_DIR = Path("src/powerpy/data")
_PARAMS = Path("params.xlsx")


def test_build_array_from_circuit_structure_and_curve():
    report = load_report_data(_PARAMS, _DATA_DIR)
    circuit = load_circuit(_SAMPLE)
    array = build_array_from_circuit(report.cell, circuit, iv_engine="analytic")
    # one panel ("panel_1"), two sections, strings 2 + 1
    assert len(array.panels) == 1
    sections = list(array.iter_sections())
    assert len(sections) == 2
    assert [len(s.strings) for s in sections] == [2, 1]
    # heterogeneous series counts preserved
    assert sections[0].strings[0].cells.__len__() == 22
    assert sections[1].strings[0].cells.__len__() == 20
    # nominal curve is finite with a positive peak power
    array.apply(Environment(temperature_c=28.0))
    v, i = array.iv_curve()
    p = v * i
    assert np.all(np.isfinite(v)) and np.all(np.isfinite(i))
    assert float(p.max()) > 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_circuit_layout.py -k build_array_from_circuit -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'powerpy.simulation.circuit_build'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/powerpy/simulation/circuit_build.py
"""Assemble the simulation tree from a free-form CircuitLayout.

Reuses the existing Cell/String/Section/Panel/Array models, so all
curve-combination, environment and shunt-diode logic is unchanged.
"""
from __future__ import annotations

from powerpy.schemas.cell import CellParameters
from powerpy.schemas.circuit import CircuitLayout
from powerpy.simulation.array_level import ArrayModel
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.panel_level import PanelModel
from powerpy.simulation.section_level import SectionModel
from powerpy.simulation.string_level import StringModel


def build_array_from_circuit(
    cell_params: CellParameters,
    circuit: CircuitLayout,
    *,
    iv_engine: str = "analytic",
    string_shunt_vf: float | None = None,
) -> ArrayModel:
    """Build an :class:`ArrayModel` from a :class:`CircuitLayout`.

    ``string_shunt_vf`` is the forward drop of the string shunt diode (from the
    cell's ``string_diode``); it is applied to strings whose
    ``string_shunt_diode`` flag is True.
    """
    prototype = CellModel(cell_params, iv_engine=iv_engine)
    panels: dict[str, list[SectionModel]] = {}
    for sec in circuit.sections:
        strings = []
        for st in sec.strings:
            vf = string_shunt_vf if st.string_shunt_diode else None
            strings.append(StringModel.from_single_cell(
                prototype, st.n_series,
                block_diode_v_drop=st.block_diode_v_drop,
                n_block_diodes=st.n_block_diodes,
                series_resistance_ohm=st.series_resistance_ohm,
                shunt_diode_v_forward=vf,
                name="%s.%s" % (sec.id, st.id)))
        section = SectionModel.from_strings(
            strings, section_resistance_ohm=sec.resistance_ohm, name=sec.id)
        panels.setdefault(sec.panel, []).append(section)
    panel_models = [PanelModel.from_sections(secs, name=pid)
                    for pid, secs in panels.items()]
    return ArrayModel.from_panels(panel_models)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_circuit_layout.py -k build_array_from_circuit -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/powerpy/simulation/circuit_build.py tests/test_circuit_layout.py
git commit -m "feat: build_array_from_circuit (CircuitLayout -> ArrayModel)"
```

---

### Task 4: Carry `circuit_reference_file` on the cell

**Files:**
- Modify: `src/powerpy/schemas/cell.py`
- Modify: `src/powerpy/loader/cell.py`
- Test: `tests/test_circuit_layout.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_circuit_layout.py
from powerpy.schemas.cell import CellParameters


def test_cellparameters_has_optional_circuit_reference():
    # default is None on a freshly loaded cell (no circuit row in workbook yet)
    report = load_report_data(_PARAMS, _DATA_DIR)
    assert hasattr(report.cell, "circuit_reference_file")
    assert report.cell.circuit_reference_file is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_circuit_layout.py -k circuit_reference -v`
Expected: FAIL — `AttributeError: 'CellParameters' object has no attribute 'circuit_reference_file'`

- [ ] **Step 3: Add the schema field**

In `src/powerpy/schemas/cell.py`, in `CellParameters`, immediately after the existing
`string_diode_reference_file: Path | None = None` line, add:

```python
    # optional free-form circuit JSON; when set, drives the electrical solve
    # instead of the ArrayLayout sections.
    circuit_reference_file: Path | None = None
```

- [ ] **Step 4: Read it in the loader**

In `src/powerpy/loader/cell.py`, inside `load_cell_parameters`, after the
`string_diode = (...)` block and before the `return CellParameters(`, add:

```python
    circuit_ref = values.get("circuit_reference_file")
```

Then in the `return CellParameters(...)` call, after the
`string_diode_reference_file=string_diode_ref,` line, add:

```python
        circuit_reference_file=circuit_ref,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_circuit_layout.py -k circuit_reference -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/powerpy/schemas/cell.py src/powerpy/loader/cell.py tests/test_circuit_layout.py
git commit -m "feat: optional circuit_reference_file on CellParameters"
```

---

### Task 5: Drive the report from the circuit

**Files:**
- Modify: `src/powerpy/app.py` (`build_electrical_report`)
- Test: `tests/test_circuit_layout.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_circuit_layout.py
from powerpy.app import build_electrical_report


def test_build_electrical_report_uses_circuit(tmp_path, monkeypatch):
    # point the loaded cell at the sample circuit and confirm the array the
    # report builds matches build_array_from_circuit (2 sections: 2 + 1 strings).
    import powerpy.app as app
    captured = {}
    real = app.build_array_from_circuit

    def spy(cell_params, circuit, **kw):
        arr = real(cell_params, circuit, **kw)
        captured["sections"] = [len(s.strings) for s in arr.iter_sections()]
        return arr

    monkeypatch.setattr(app, "build_array_from_circuit", spy)

    # force the cell to reference the sample circuit
    from powerpy.loader import report as report_mod
    real_load = report_mod.load_report_data

    def patched_load(params, data_dir):
        rep = real_load(params, data_dir)
        import dataclasses
        cell = dataclasses.replace(rep.cell, circuit_reference_file=_SAMPLE.resolve())
        return dataclasses.replace(rep, cell=cell)

    monkeypatch.setattr(app, "load_report_data", patched_load)

    pdf, labels, rep = build_electrical_report(
        _PARAMS, tmp_path / "out.pdf", data_dir=_DATA_DIR, engine="analytic")
    assert captured.get("sections") == [2, 1]   # circuit path was used
    assert labels                                # at least one scoped case
```

Note: this test asserts the circuit path is taken; it does not require pdflatex
(if `pdf` is None because pdflatex is absent, the assertions on `captured`/`labels`
still hold).

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_circuit_layout.py -k uses_circuit -v`
Expected: FAIL — `AttributeError: module 'powerpy.app' has no attribute 'build_array_from_circuit'` (it is imported lazily inside the function today)

- [ ] **Step 3: Modify `build_electrical_report`**

In `src/powerpy/app.py`, replace the body of `build_electrical_report` from the
import block down to the end of the function with the following. The change:
(a) imports `load_circuit` and `build_array_from_circuit` at module-function top so
they are patchable and reusable, (b) adds a single `_build_array()` helper used by
BOTH the scope and fallback branches, (c) the fallback branch now loops phases
manually (mirroring the scope branch) instead of calling `evaluate`, so the circuit
is honoured in both branches.

```python
    import dataclasses
    from .loader.report import load_report_data
    from .loader.analysis import load_analysis_scope
    from .loader.requirement import load_requirement
    from .loader.circuit import load_circuit
    from .simulation.pipeline import (
        AnalysisCase, CaseResult, CompliancePoint, environment_for_phase, run)
    from .simulation.array_level import build_from_report
    from .simulation.circuit_build import build_array_from_circuit
    from .render import Report

    params = Path(params)
    data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data"
    out_pdf = Path(out_pdf).resolve()
    workdir = Path(workdir) if workdir else out_pdf.parent / ("_build_" + out_pdf.stem)

    report = load_report_data(params, data_dir)
    scope = load_analysis_scope(params)
    requirement = load_requirement(params, data_dir)

    # string shunt-diode forward drop (if the cell carries one)
    string_shunt_vf = (report.cell.string_diode.v_forward
                       if getattr(report.cell, "string_diode", None) else None)

    def _build_array():
        """Build the array from the free-form circuit if referenced, else the
        ArrayLayout sections."""
        ref = getattr(report.cell, "circuit_reference_file", None)
        if ref:
            circuit = load_circuit(ref)
            return build_array_from_circuit(
                report.cell, circuit, iv_engine=engine, string_shunt_vf=string_shunt_vf)
        return build_from_report(report, iv_engine=engine)

    def _case_result(label, phase, launch, *, temperature_c=None, season=1.0,
                     sun_angle_deg=0.0, string_loss=1.0, v_operating=None, array=None):
        env = environment_for_phase(
            report, phase=phase, launch_config=launch,
            temperature_c=temperature_c, season=season, angle_alpha_deg=sun_angle_deg)
        if string_loss != 1.0:
            env = dataclasses.replace(env, current_loss=env.current_loss * string_loss)
        res = run(array, env)
        v_bus = v_operating
        if v_bus is None and requirement is not None:
            v_bus = requirement.voltage_operating_v
        bus = None
        if v_bus is not None:
            i_bus = array.current_at_voltage(v_bus)
            bus = CompliancePoint(bus_voltage_v=v_bus, current_a=float(i_bus),
                                  power_w=float(v_bus * i_bus))
        case = AnalysisCase(label=label, phase=phase, launch_config=launch,
                            temperature_c=temperature_c, season=season)
        return CaseResult(case=case, environment=env, results=res, bus=bus)

    array = _build_array()

    if scope:
        case_results = [
            _case_result(cfg.label, cfg.phase, cfg.launch,
                         temperature_c=cfg.temperature_c, season=cfg.season,
                         sun_angle_deg=cfg.sun_angle_deg, string_loss=cfg.string_loss,
                         v_operating=cfg.v_operating, array=array)
            for cfg in scope]
        labels = [c.label for c in scope]
        requirement_w = (min(requirement.power_min_for_phase(c.phase) for c in scope)
                         if requirement is not None else None)
    else:
        present = {f.phase for f in report.losses}
        if not present:
            raise SystemExit("ERROR: no phases found and no `analysis` sheet in the workbook.")
        phases = [p for p in _PHASE_ORDER if p in present]
        phases += sorted(p for p in present if p not in _PHASE_ORDER)
        case_results = [_case_result(ph, ph, "single", array=array) for ph in phases]
        labels = phases
        requirement_w = (min(requirement.power_min_for_phase(ph) for ph in phases)
                         if requirement is not None else None)

    rpt = Report.from_results(report, case_results, array=array,
                              requirement_w=requirement_w, iv_engine=engine)
    rpt.render(workdir)
    return rpt.compile_pdf(out_pdf), labels, report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_circuit_layout.py -k uses_circuit -v`
Expected: PASS

- [ ] **Step 5: Run the full suite (regression)**

Run: `PYTHONPATH=src python -m pytest -q`
Expected: PASS (previous 92 + new tests). If `test_cli.py`'s report test relied on
`evaluate`, confirm it still passes — the report output for the no-circuit path is
unchanged because `_case_result` reproduces `evaluate`'s per-phase environment and
bus-voltage logic.

- [ ] **Step 6: Commit**

```bash
git add src/powerpy/app.py tests/test_circuit_layout.py
git commit -m "feat: build_electrical_report drives the array from the free-form circuit"
```

---

### Task 6: Wire the sample circuit into the workbook + verify end-to-end

**Files:**
- Modify: `params.xlsx` (add `circuit_reference_file` row to `cell_params`)
- Modify: `scripts/build_params.py` (regenerate to include the new row)

- [ ] **Step 1: Add the circuit reference row to cell_params**

Run (with `params.xlsx` closed in Excel):

```bash
PYTHONPATH=src python - <<'PY'
import openpyxl
wb = openpyxl.load_workbook("params.xlsx")
ws = wb["cell_params"]
header = [c.value for c in ws[1]]
have = any((r[0].value == "circuit_reference_file") for r in ws.iter_rows(min_row=2))
if not have:
    row = [None] * ws.max_column
    row[0] = "circuit_reference_file"
    if len(row) > 1: row[1] = "Circuit reference File"
    if len(row) > 2: row[2] = "circuits/msro_nominal.json"
    if "type" in header: row[header.index("type")] = "path"
    ws.append(row)
    wb.save("params.xlsx")
    print("added circuit_reference_file row")
else:
    print("already present")
PY
```

- [ ] **Step 2: Generate the report from the circuit**

Run: `python run.py report --out reports/_noNG_elec.pdf`
Expected: prints `phases : single@End_of_Life, dual@End_of_Life` and `OK -> ...pdf`.
The whole-array I–V/P–V figure now reflects the circuit's strings (2 sections, series counts 22/22 and 20).

- [ ] **Step 3: Regenerate build_params.py so the full builder includes the new row**

Run: `PYTHONPATH=src python scripts/_gen_build_params.py`
Expected: `wrote .../scripts/build_params.py (10 sheets)`

- [ ] **Step 4: Verify build_params reproduces the workbook (incl. the new row)**

Run:

```bash
python scripts/build_params.py params_gen_test.xlsx
PYTHONPATH=src python -c "import openpyxl; ws=openpyxl.load_workbook('params_gen_test.xlsx')['cell_params']; print('circuit row:', any(r[0].value=='circuit_reference_file' for r in ws.iter_rows(min_row=2)))"
```

Expected: `circuit row: True`. Then remove the temp file: `rm -f params_gen_test.xlsx`

- [ ] **Step 5: Run the full suite again**

Run: `PYTHONPATH=src python -m pytest -q`
Expected: PASS (the builder test in Task 3/4 now sees `circuit_reference_file` present
on the loaded cell — `test_cellparameters_has_optional_circuit_reference` asserts the
attribute exists; update that test's value assertion if you added the row, see note).

> NOTE: after Step 1 the workbook's cell has `circuit_reference_file` set, so
> `test_cellparameters_has_optional_circuit_reference` (Task 4) must change its last
> line from `assert report.cell.circuit_reference_file is None` to
> `assert report.cell.circuit_reference_file is None or report.cell.circuit_reference_file.name == "msro_nominal.json"`.
> Make that edit in this step and re-run.

- [ ] **Step 6: Commit**

```bash
git add params.xlsx scripts/build_params.py tests/test_circuit_layout.py
git commit -m "feat: reference the free-form circuit from params.xlsx; report runs from it"
```

---

## Self-Review

**Spec coverage:**
- §4 JSON format → Task 1 (schema), Task 2 (loader + sample). ✓
- §5.1 schema → Task 1. ✓
- §5.2 loader → Task 2. ✓
- §5.3 builder → Task 3. ✓
- §5.4 integration (`circuit_reference_file`, fallback) → Task 4 (field/loader) + Task 5 (report). ✓
- §6 data flow (factors via environment) → Task 5 `_case_result` reuses `environment_for_phase`. ✓
- §7 output → Task 5 (Report.from_results) + Task 6 (end-to-end). ✓
- §8 error handling (missing file, fallback) → Task 2 (FileNotFoundError), Task 5 (`_build_array` fallback). ✓
- §9 testing → Tasks 1–6 tests. ✓
- §10 backward compat → Task 5 fallback branch + Task 4 default None. ✓

**Placeholder scan:** No TBD/TODO; all steps have concrete code/commands. ✓

**Type consistency:** `build_array_from_circuit(cell_params, circuit, *, iv_engine, string_shunt_vf)` used identically in Task 3 and Task 5. `CircuitString.string_shunt_diode`, `CircuitSection.panel/resistance_ohm`, `CircuitLayout.sections` consistent across tasks. `StringModel.from_single_cell(..., shunt_diode_v_forward=)`, `SectionModel.from_strings(..., section_resistance_ohm=)`, `PanelModel.from_sections`, `ArrayModel.from_panels` match the existing code. ✓
