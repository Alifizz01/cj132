# Panel Layout Convention & Lateral-Thermal Analysis — Specification

**Status:** proposed for sign-off · **Date:** 2026-06-14 · **Applies to:** PowerPy solar-array thermal framework
**Implements:** a configurable solar-cell layout convention, in-plane (lateral) heat conduction, and a
report format (HTML heat-map + JSON source of truth).

---

## 1. Purpose & scope

We must analyse the temperature of a satellite solar panel cell-by-cell, for **arbitrary, possibly
asymmetric layouts** that include **bare (no-cell) regions**. A bare region absorbs sunlight but produces no
electrical power, so all absorbed energy stays as heat — making it hotter than a cell region, and (through
lateral conduction) able to heat its neighbours. This spec defines:

1. a **convention** for describing where cells, diodes and bare substrate sit on a panel;
2. the **lateral heat-conduction** model that lets heat spread sideways between tiles;
3. the **report** format for presenting and archiving results.

Design goals: human-readable & supervisor-reviewable; version-controllable as text; asymmetry-trivial;
directly yields the conduction adjacency; a strict superset of the existing independent-cell solver.

---

## 2. Layout convention — grid-map + palette

A panel is a 2-D **grid** of single-character **tiles**. Each distinct character is defined once in a
**palette** carrying that tile's full properties. The grid is the picture; the palette is the legend.

### 2.1 Schema (JSON)

```json
{
  "name": "Example asymmetric panel",
  "pitch_mm": 55,
  "palette": {
    "A": {"name": "Cell type A", "is_cell": true, "cell_type": "GaAs-3J", "string": "S1",
          "alpha_front": 0.97, "alpha_rear": 0.93, "epsilon_front": 0.90, "epsilon_rear": 0.89},
    ".": {"name": "Bare substrate", "is_cell": false,
          "alpha_front": 0.88, "alpha_rear": 0.85, "epsilon_front": 0.85, "epsilon_rear": 0.85},
    "D": {"name": "Bypass diode", "is_cell": false, "is_diode": true,
          "alpha_front": 0.90, "alpha_rear": 0.88, "epsilon_front": 0.88, "epsilon_rear": 0.88}
  },
  "layout": [
    "A A A A A A . .",
    "A A A A A A . .",
    "A A . . A A A A",
    "A A . . A A A A",
    "D A A A A A A D",
    ". . A A A A . ."
  ]
}
```

### 2.2 Tile (palette-entry) fields

| Field | Meaning | Default |
|---|---|---|
| `is_cell` | true ⇒ converts absorbed sun to electricity (heat leaves) | false |
| `is_diode` | marks a bypass/blocking diode position | false |
| `alpha_front`, `alpha_rear` | absorptivity (0–1), front/rear | 0.90 |
| `epsilon_front`, `epsilon_rear` | emissivity (0–1), front/rear | 0.90 |
| `string` | electrical group id (for the circuit / reverse-bias side); `null` for bare/diode | null |
| `cell_type`, `name` | descriptive labels | "" |

### 2.3 Grid rules
- Rows are space-separated keys (e.g. `"A A . ."`) or a dense string (e.g. `"AA.."`); all rows the same length.
- `pitch_mm` is the tile centre-to-centre spacing; tile area defaults to `pitch²`.
- Row-major flat index `i = r·n_cols + c` orders the per-tile arrays and the solver unknowns.

### 2.4 Why bare regions are first-class
A bare tile has `is_cell:false` ⇒ `generates_power == False` ⇒ its extracted power is **forced to 0** in the
solve, regardless of any value passed. With its own (typically different) optical properties, it balances at a
**higher** temperature than a power-extracting cell under the same sun. This is the effect under study.

---

## 3. Lateral (in-plane) heat conduction

### 3.1 Model — nodal resistor network
Each tile has two nodes (front `T₁`, rear `T₂`). In addition to the vertical front↔rear conduction `C·A`,
neighbouring tiles are linked by a **lateral conductance** `g_lat` (W/K) — front-to-front and rear-to-rear.
The 4-neighbour adjacency comes directly from the grid. Per tile *i* with neighbours *j* (kelvin):

```
f1_i = αF_i·A·P_sun·tilt − εF_i·A·σ·(T1_i⁴ − Tsp⁴) − P_elec_i + C·A·(T2_i − T1_i)
       + Σ_j g_lat·(T1_j − T1_i)
f2_i = (αR_i·P_alb + εR_i·P_ir)·A·tilt − εR_i·A·σ·(T2_i⁴ − Tsp⁴) − C·A·(T2_i − T1_i)
       + Σ_j g_lat·(T2_j − T2_i)
```

`g_lat` is derived from the facesheet: `g_lat ≈ k_facesheet · t_facesheet · (edge_width / pitch)`.
A single panel-wide value is the default; a per-link value is a future extension.

### 3.2 Solution — vectorised sparse Newton
The cells are now coupled, so we assemble one **(2N × 2N) sparse Jacobian** (each tile linked to its
neighbours) and take Newton steps, solving the sparse linear system each step (`scipy.sparse.linalg.spsolve`;
dense fallback for small panels). Converges in a handful of steps.

### 3.3 Strict superset (validation)
With **`g_lat = 0`** the off-diagonal links vanish, the system becomes block-diagonal, and each tile reproduces
the existing independent solver **exactly**. This is enforced by a parity test: a single cell returns the
65.26 °C / 64.60 °C oracle. So nothing is lost — turning on `g_lat` only *adds* realistic spreading (peak
temperature drops, neighbours warm), conserving the overall in/out energy balance.

---

## 4. Report format — HTML heat-map + JSON source

- **`report.html`** (human-facing, prints to PDF): a colour-coded **panel temperature map** (each tile shaded
  cold→hot, tiles over the melt limit outlined in red), a summary table (peak/mean T, margin to limit, tiles
  over limit, PASS/FAIL verdict), and the layout key. This is the supervisor deliverable.
- **`results.json`** (reproducible source of truth): the full per-tile temperature grids, per-tile records
  (key, is_cell, T_front, T_rear, over_limit), and the summary block — re-readable and diffable without
  re-simulating.
- An optional plain-text/Markdown summary may ride along for quick logs/diffs.

### 4.1 JSON schema (abridged)
```json
{
  "summary": {"name", "grid":[rows,cols], "pitch_mm", "g_lat", "t_limit_c",
              "peak_t_c", "peak_tile":[r,c], "mean_t_c", "margin_to_limit_c",
              "n_over_limit", "n_tiles", "n_cells", "verdict", "converged"},
  "tiles":   [{"row","col","key","name","is_cell","t_front_c","t_rear_c","over_limit"}, ...],
  "t_front_c": [[...],[...]], "t_rear_c": [[...],[...]]
}
```

---

## 5. Flexibility & how far the analysis can go
- **Any layout:** asymmetric shapes, gaps/notches, mixed cell types, diodes — just edit the grid.
- **Per-region properties:** different optical/thermal values per tile via the palette.
- **Failure analysis:** mark a tile failed (e.g. a `x` palette key or a per-tile `P_elec`); inject reverse-bias
  dissipation and read the resulting hot-spot.
- **Monte-Carlo over the grid:** sweep which tiles fail / how many / random sampling, ranking layouts by peak T.
- **Spreading metrics:** with lateral conduction, report hot-spot **peak, spread radius, and which neighbours
  are driven over the limit** — not just a single cell temperature.
- **Time-varying environment:** feed orbit fluxes (sun/eclipse/albedo/IR, tilt) per step.

---

## 6. Modules & validation
| File | Role |
|---|---|
| `layout.py` | `PanelLayout`, `TileType`, `from_dict`, `load_layout`, adjacency & property arrays |
| `thermal_panel.py` | `solve_panel_thermal(...)` — sparse Newton with lateral conduction; `g_lat=0` = baseline |
| `report.py` | `panel_report(...)` — HTML heat-map + JSON source |
| `data/layouts/example_panel.json` | the worked example layout above |
| `tests/test_panel_thermal.py` | parses; **G=0 parity vs oracle**; bare-hotter; lateral-spread; report I/O (6 tests) |

All modules are standalone (numpy + scipy + stdlib), duck-typed, and tested in isolation without the legacy
cell model. Open question for sign-off: the numeric `g_lat` (and melt limit) for the actual flight substrate.
