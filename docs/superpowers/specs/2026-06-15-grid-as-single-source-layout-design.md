# Grid-as-single-source layout — design

**Date:** 2026-06-15
**Status:** Draft — design approved in direction; data-model specifics have open decisions (see §10). Pending spec review.
**Author:** PowerPy
**Supersedes the layout strategy of:** `2026-06-15-freeform-circuit-electrical-layout-design.md` (the free-form circuit becomes an *optional override*, not the primary source — see §9).

## 1. Problem

PowerPy currently needs **two** layout artifacts that describe the same physical array:

- **`PanelLayout`** (`config/layout.py`) — the 2-D tile grid: cell positions, optical/thermal
  properties, 4-neighbour adjacency. Consumed by the thermal/failure solver.
- An **electrical layout** — either the legacy `ArrayLayout` (`sections` sheet) or the new
  free-form **circuit JSON** — describing strings (series) and sections (parallel). Consumed by
  the electrical report.

Maintaining both by hand is error-prone and, crucially, **nothing forces them to agree**. A cell
can be in "string 3" electrically but sit anywhere thermally; a failed tile in the thermal model
is not tied to any specific electrical cell. The two descriptions can silently drift, and there is
no guarantee of correlation.

## 2. The idea — one placement, two views

Stop maintaining two layouts. Maintain **one grid in which each cell tile carries its electrical
identity**, and *derive* both perspectives from it:

- **Thermal view** = tile positions + 4-neighbour adjacency (exactly what `PanelLayout` already
  produces).
- **Electrical view** = group cell tiles by their `string` tag → cells in series; group strings by
  their `section` tag → strings in parallel; group sections by panel → the array.

Because there is only one artifact, correlation is **structural, not a promise**: the two views
cannot drift, and the cell at grid index *k* is the *same* object thermally and electrically. This
also makes the per-cell electro-thermal couple (`solve/coupling.py::couple()`) work with **no
bridge/mapping code** — same cells on both sides.

## 3. Decisions

1. **The grid is the single source of truth.** `PanelLayout` (plus a small amount of electrical
   metadata) yields BOTH the thermal map and the electrical circuit.
2. **The electrical circuit is derived, not authored separately** — via a new
   `build_array_from_grid(...)`.
3. **The free-form circuit JSON stays as an optional override** for abstract / what-if studies that
   have no geometry (§9). When a grid is present, it is the default electrical source.
4. **Correlation is guaranteed by construction** — there is exactly one placement of cells.

## 4. What the grid already has, and what it needs

`PanelLayout.TileType` already carries: `is_cell`, optical/thermal props, `string` (electrical
group id), `block` (series-block id), `generates_power`. The grid is ~80% of a single source. To
derive a full electrical circuit it needs three small additions:

| Need | Why | Proposed form (see §10 for open choice) |
|---|---|---|
| **Series order within a string** | blocking-diode placement and the reverse-bias chain need cell order | optional `series_index` on the cell tile; **fallback: row-major scan order** of that string's tiles |
| **Parallel grouping (section)** | strings combine in parallel within a section | a `section` tag per cell tile (reuse/rename `block`, or add `section`) |
| **Per-string / per-section electrical params** | harness R, blocking/shunt diodes, section harness R | a small side-table keyed by the SAME `string`/`section` ids the tiles use (a workbook sheet or a block in the layout JSON) |

Everything else needed for the electrical solve (series/parallel combine, environment factors,
cell + string shunt diodes) already exists and is reused unchanged.

## 5. Deriving the electrical view — `build_array_from_grid`

A new builder (mirroring `build_array_from_circuit`) constructs the existing
`Cell → String → Section → Panel → Array` tree from the grid:

1. Take the prototype `CellModel(report.cell, iv_engine=...)`.
2. Collect cell tiles (`is_cell`/`generates_power`), grouped by `string` id; order each group by
   `series_index` (or row-major position). Each group → a `StringModel` of `len(group)` cells in
   series, with per-string params from the side-table (harness R, blocking diode, string shunt
   diode forward drop).
3. Group strings by `section` id → `SectionModel` (parallel), with per-section harness R.
4. Group sections by panel → `PanelModel`; all panels → `ArrayModel`.

The result is an `ArrayModel` identical in type to today's, so the report, environment pipeline,
and curve-combination are untouched.

## 6. Deriving the thermal view

Unchanged: `PanelLayout.prop_arrays()` (per-tile optical/thermal arrays) and `neighbours()`
(adjacency) feed `solve_panel` / `solve_thermal` exactly as today. No change to the thermal solver.

## 7. The correlation guarantee & coupled-solve payoff

- Each cell occupies one grid index *k*. Its thermal node is *k* (via `prop_arrays`); its
  electrical identity is `(string, series_index)`. The map is the identity on *k* — built once,
  from one artifact.
- This enables a **true per-cell electro-thermal coupled run** with no new bridge: build the array
  and the thermal grid from the same grid, then run the existing damped fixed-point loop —
  per-tile temperature → per-cell IV → per-cell `P_elec` → per-tile heat. A failed tile is the same
  cell electrically (drives its string into reverse) and thermally (the hot-spot), automatically.
  *(Implementing the coupled run is out of scope here — this design only guarantees it becomes
  possible without a mapping layer.)*

## 8. Data flow

```
ONE grid (positions + per-cell string/section/series_index)  +  per-string/section params
        │                                                            │
        ├── prop_arrays() + neighbours() ──► THERMAL view ──► solve_panel / failure studies
        │                                                            
        └── build_array_from_grid() ───────► ELECTRICAL view ─► ArrayModel ─► report (nominal)
                                                                     
   (both views reference the SAME cell tiles → guaranteed correlation; coupled solve = same cells)
```

## 9. Relationship to the free-form circuit (already built)

The free-form circuit JSON (`schemas/circuit.py`, `loader/circuit.py`,
`simulation/circuit_build.py`, `cell.circuit_reference_file`) is **kept** and becomes an explicit
**override**:

- **Default:** if the workbook references a grid with electrical tags, the electrical circuit is
  *derived* from the grid (`build_array_from_grid`).
- **Override:** if `circuit_reference_file` is set, the free-form circuit is used instead (for
  abstract / what-if topologies decoupled from geometry).
- **Legacy:** if neither, fall back to the `ArrayLayout` (`sections` sheet) via
  `build_from_report` (unchanged).

Resolution order in `build_electrical_report`: **circuit override → grid-derived → ArrayLayout**.

## 10. Open decisions (to confirm before the implementation plan)

1. **Series order:** explicit `series_index` per tile, or infer from row-major scan order of a
   string's tiles? (Recommend: infer by position, with optional explicit override.)
2. **Multi-panel arrays:** one grid file per physical panel (referenced by the workbook), or a
   `panel` tag per tile in a single grid? (Recommend: one grid per panel — matches hardware.)
3. **Where per-string/section electrical params live:** a new workbook sheet (e.g. `circuit_params`
   keyed by string/section id), or a block inside the layout JSON? (Recommend: a block in the
   layout JSON, so the grid file is self-contained.)
4. **`block` vs `section`:** reuse the existing `block` field as the parallel-section id, or add a
   distinct `section` field and keep `block` for series sub-blocks (bypass-diode groups)?

## 11. Scope

**In scope:** the single-source grid model (electrical tags + params), `build_array_from_grid`,
wiring it as the default electrical source with the override/legacy fallbacks, validation that
every cell tile has a resolvable string/section, tests.

**Out of scope (YAGNI):** implementing the per-cell coupled electro-thermal run (this design only
removes the bridge barrier); fully recursive topologies; auto-inferring electrical topology from
raw geometry without tags.

## 12. Validation & correlation checks

- Every `is_cell` tile must resolve to a `string`, and every `string` to a `section`; loader raises
  with the offending tile/string id otherwise.
- A derived-array sanity check: total series cells and parallel paths match the grid's cell counts.
- Because there is one artifact, no cross-layout consistency check is needed — the class of "the
  two layouts disagree" bug is eliminated by construction.

## 13. Backward compatibility

- Workbooks with no grid: unchanged (ArrayLayout legacy path).
- Workbooks with a `circuit_reference_file`: unchanged (override path; the feature just built).
- The thermal grid / failure studies: unchanged.
- Adding electrical tags to a grid is additive; grids without them still work thermally and simply
  cannot derive an electrical circuit (fall back to override/legacy).

## 14. Migration

Existing separate layouts can be reconciled by tagging the thermal grid's cells with the electrical
`string`/`section` ids implied by the current `sections` sheet, then dropping the separate
electrical layout for that array. The free-form circuit JSON remains available for studies that are
intentionally abstract.
