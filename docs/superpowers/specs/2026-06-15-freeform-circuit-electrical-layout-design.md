# Free-form electrical circuit layout — design

**Date:** 2026-06-15
**Status:** Approved (brainstorming) — pending spec review
**Author:** PowerPy

## 1. Purpose

Today PowerPy has two unrelated "layout" concepts:

- **`PanelLayout`** (`config/layout.py`) — a 2-D thermal tile grid (palette + adjacency) consumed
  by the thermal / failure solver.
- **`ArrayLayout`** (`schemas/layout.py`, the `sections` sheet) — a uniform electrical hierarchy
  (section templates with `n_strings_parallel`, `n_sca_series_per_string`) consumed by the
  electrical report via `build_from_report`.

The electrical side is constrained to *uniform* section templates: every string in a section is
identical. We want **full freedom to define the circuit** — heterogeneous strings, per-element
parameters — and to report the **nominal (no-failure) electrical result** with **all
performance factors applied** (temperature, radiation fluence, losses, season, sun angle,
degradation, and the cell + string shunt diodes).

This is achieved with a **separate, free-form circuit specification** (a JSON file), decoupled
from the thermal grid geometry, that drives the electrical report.

## 2. Scope

**In scope**
- A new circuit JSON format (fixed 4-level hierarchy, per-element parameters).
- Schema + loader for it.
- A builder that assembles the existing simulation tree from the circuit.
- Wiring the report to use the circuit when referenced, with all environmental factors applied,
  for the nominal (no-failure) case, per analysis-scope config.
- Tests.

**Out of scope (YAGNI)**
- Failure injection / hot-spot analysis on the free-form circuit (the thermal grid + failure
  studies remain as-is; this is the *nominal* electrical result only).
- Fully recursive series/parallel nesting (rejected in brainstorming in favour of the fixed
  4-level model).
- Linking circuit cells to specific grid tiles (explicitly decoupled).
- ngspice; the analytic engine is the path.

## 3. Decisions (from brainstorming)

1. **Circuit source:** a separate free-form spec, decoupled from grid geometry.
2. **Format:** a nested JSON file under `data/circuits/`, referenced from the workbook.
3. **Structure:** fixed 4-level — array → sections (parallel) → strings (series of cells) — with
   every element fully parameterized; cells are abstract (the prototype cell evaluated at each
   case's environment).
4. **Integration:** reuse the existing `CellModel → StringModel → SectionModel → PanelModel →
   ArrayModel` stack and the existing report; do not duplicate IV/combine logic.

## 4. Circuit JSON format

Location: `src/powerpy/data/circuits/<name>.json`.

```json
{
  "name": "msro_nominal",
  "sections": [
    {
      "id": "sec_a",
      "panel": "panel_1",
      "resistance_ohm": 0.0,
      "strings": [
        {
          "id": "s1",
          "n_series": 22,
          "series_resistance_ohm": 0.0,
          "block_diode_v_drop": 0.6,
          "n_block_diodes": 1,
          "string_shunt_diode": true
        }
      ]
    }
  ]
}
```

Field semantics:

| Field | Level | Meaning | Default |
|---|---|---|---|
| `name` | root | identifier | required |
| `sections[]` | root | combined in **parallel** at the array level | required, ≥1 |
| `section.id` | section | unique id | required |
| `section.panel` | section | optional grouping into a panel (sections of the same panel are parallel within the panel; panels are parallel in the array) | `"panel_1"` |
| `section.resistance_ohm` | section | section harness resistance | `0.0` |
| `section.strings[]` | section | combined in **parallel** within the section | required, ≥1 |
| `string.id` | string | unique id within the section | required |
| `string.n_series` | string | number of cells in **series** in this string (may differ per string) | required, ≥1 |
| `string.series_resistance_ohm` | string | string harness resistance | `0.0` |
| `string.block_diode_v_drop` | string | series blocking-diode forward drop | `0.6` |
| `string.n_block_diodes` | string | number of series blocking diodes | `1` |
| `string.string_shunt_diode` | string | apply the cell's string shunt diode clamp to this string | `true` |

Validation: ≥1 section; each section ≥1 string; each string `n_series ≥ 1`; unique section ids;
unique string ids within a section; numeric fields ≥ 0; resistances ≥ 0.

## 5. Components (isolated units)

### 5.1 `schemas/circuit.py`
Frozen dataclasses mirroring the JSON:
- `CircuitString(id, n_series, series_resistance_ohm, block_diode_v_drop, n_block_diodes, string_shunt_diode)`
- `CircuitSection(id, panel, resistance_ohm, strings: tuple[CircuitString, ...])`
- `CircuitLayout(name, sections: tuple[CircuitSection, ...])`

Each `__post_init__` validates as in §4. No I/O, no powerpy imports beyond stdlib — testable in
isolation.

**Interface:** construct directly or via the loader; read-only.

### 5.2 `loader/circuit.py`
- `load_circuit(json_path: Path) -> CircuitLayout` — parse + validate the JSON, raising a clear
  error on malformed input. Tolerates missing optional fields (uses defaults).

**Depends on:** `schemas/circuit.py`, stdlib `json`.

### 5.3 `simulation/circuit_build.py`
- `build_array_from_circuit(cell_params, circuit, *, iv_engine="analytic", string_shunt_vf=None) -> ArrayModel`
  - prototype `CellModel(cell_params, iv_engine=...)`.
  - For each `CircuitString`: `StringModel.from_single_cell(prototype, n_series, block_diode_v_drop,
    n_block_diodes, series_resistance_ohm, shunt_diode_v_forward=string_shunt_vf if string.string_shunt_diode else None)`.
  - For each `CircuitSection`: build a `SectionModel` from its **list** of (possibly
    heterogeneous) `StringModel`s with `section_resistance_ohm` — via the section's
    list constructor (add a `from_strings` classmethod if only `from_single_string` exists today;
    `from_single_string` builds N identical copies, which cannot express heterogeneous strings).
  - Group sections by `panel` into `PanelModel`s; `ArrayModel.from_panels(panels)`.

**Depends on:** the existing `simulation/*_level.py` models and `schemas/circuit.py`. Reuses all
curve-combination and diode logic; adds no new physics.

### 5.4 Integration in `app.py::build_electrical_report`
- Read an optional `circuit_reference_file` (path) from `cell_params`.
- If present: `circuit = load_circuit(path)`; build the array via `build_array_from_circuit(...)`
  (passing the cell's string-shunt-diode `v_forward`); use this array for every analysis-scope
  case via `run(array, env)`.
- If absent: fall back to today's `build_from_report` (no behaviour change).
- `cell_params` loader (`loader/cell.py`) reads the optional `circuit_reference_file` (path type).
- `CellParameters` gains `circuit_reference_file: Path | None = None`.

## 6. Data flow

```
params.xlsx (cell_params.circuit_reference_file) ─┐
data/circuits/<name>.json ── load_circuit ──► CircuitLayout
                                                  │
cell_params + (cell, string) shunt diodes ───────┤
                                                  ▼
                     build_array_from_circuit ──► ArrayModel  (CellModel→String→Section→Panel→Array)
                                                  │
analysis sheet (scope) ─► environment_for_phase ─► Environment (T, dose, losses, season, sun angle)
                                                  ▼
                              run(array, env) ──► SimulationResults (nominal, no failure)
                                                  │
requirement sheet (EOL/EOR power, v_operating) ──► Report.from_results ──► PDF (IV/PV, MPP,
                                                                            per-section, compliance)
```

## 7. Output

The existing electrical report, now driven by the free-form circuit, per analysis-scope config
(`single@End_of_Life`, `dual@End_of_Life`):
- whole-array I–V / P–V curve with the `requirement` power line and `v_operating` line;
- per-section breakdown table (Vmp/Imp/Pmp/Voc);
- array MPP, current/power at `v_operating`, margin vs the binding EOL/EOR requirement.

No new report sections are required; the result is the nominal (no-failure) array performance.

## 8. Error handling

- Missing circuit file referenced by `circuit_reference_file` → clear `FileNotFoundError`.
- Malformed JSON / failed validation → `ValueError` naming the offending section/string.
- No `circuit_reference_file` → silently fall back to `build_from_report` (documented).

## 9. Testing

- **`schemas/circuit.py`**: validation rejects empty sections/strings, `n_series < 1`, duplicate
  ids; accepts a valid heterogeneous circuit.
- **`loader/circuit.py`**: parses a sample JSON (with and without optional fields) into the
  expected dataclasses.
- **`simulation/circuit_build.py`**: a circuit with two sections, heterogeneous string series
  counts → `ArrayModel` with the correct number of panels/sections/strings and per-string series
  counts; the array IV curve is finite and monotone where expected.
- **Integration**: `build_electrical_report` with a `circuit_reference_file` set produces a PDF and
  the array MPP/compliance numbers match a hand-built equivalent; absence of the field reproduces
  today's output (regression).
- Full suite stays green (currently 92 tests).

## 10. Backward compatibility

- No `circuit_reference_file` → identical behaviour to today (ArrayLayout path).
- New schema field defaults to `None`; existing workbooks load unchanged.
- The thermal grid (`PanelLayout`) and failure studies are untouched.
