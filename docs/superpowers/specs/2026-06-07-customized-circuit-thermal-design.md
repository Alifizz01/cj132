# Customized Solar Array Circuit + Vectorized Electro-Thermal Analysis

**Date:** 2026-06-07
**Status:** Design — awaiting user review
**Author:** brainstorming session (Claude + user)

---

## 1. Goal

Build a **parametric, customizable circuit class** for a satellite solar array, on top of the
existing `cell` model, plus a **vectorized electro-thermal solver** and a **Monte-Carlo failure
sweep**. The headline question we must answer:

> When one (or several) solar cell(s) fail, the surrounding healthy cells drive the failed cell
> into **reverse bias** (back-voltage, down to ~−20 V). Reverse voltage × current is dissipated
> as **heat instead of electrical power**, producing a local **hotspot** that can break down the
> cell and, in the worst case, **melt the aluminium honeycomb substrate**. We want to predict
> *which* failures cause this, *how bad* it gets, and *which array layouts* are most robust.

## 2. Scope (what we build) and non-goals

**In scope**

1. A `Circuit` class: declarative, nestable topology built from `cell` objects, with every cell
   individually addressable for fault injection.
2. A substrate model + loader (`data/substrates/*.json`).
3. A vectorized 2-node thermal solver (replaces the per-cell `scipy.fsolve` loop in `thermal.py`).
4. An electro-thermal coupling loop (circuit ⇄ thermal until temperature converges).
5. Orbit-driven environment fluxes via **hapsira** (sun + eclipse, albedo, IR).
6. Breakdown detection (temperature threshold **and** reverse-power threshold).
7. Monte-Carlo failure sweep (three modes: position, count, random sampling).
8. Result storage + reporting (Parquet/HDF5 source of truth, Excel + plots on top).

**Non-goals (for this iteration)**

- Lateral cell-to-cell heat conduction through the honeycomb (the reference sketch is a 2-node
  front/rear model with **no** lateral term — each cell is thermally independent). Leave a hook
  for it but do not implement.
- Transient/time-constant thermal (we solve **steady state** at each orbit step).
- Rebuilding the OCR-damaged `string.py` / `section.py` class bodies.

## 3. Foundation we reuse (already in the repo)

| Piece | File | Use |
|---|---|---|
| `cell` | `cell.py` | Leaf element; already has forward path **and** reverse path (`DD_Shunt`, `r_cell_shunt`). Temperature shifts isc/imp/vmp/voc via regressors. |
| `shuntdiode` | `shuntdiode.py` | Bypass-diode-only element (a `cell` subclass) for the reverse path. |
| `cellBuilder`, `ng_sim`, `RSeriesModel`/`RShuntModel`, `IVPlot` | `electric.py` | Netlist primitives + ngspice runner. |
| Node-naming + blocking-diode netlist pattern | `string.py`, `section.py` | Copy the *pattern* (not the broken class bodies). |
| Thermal constants `sigma`, `T_0=-273.15`, `T_Space=2.7`, `B_0=1367` | `definitions.py` | Thermal solve. |
| `Environment` dataclass (`albedo_w_m2`, `season`, angles, temperature) | `simulation/environment.py` | Per-operating-point environment; hapsira fills a time series of these. |
| Orbit/eclipse scaffolding | `eclipse.py` | Reference only — **broken** here (`poliastro`/`astropy` not importable, `albedoIntensity` flagged erroneous). Replace with hapsira. |

## 4. Topology model — the `Circuit` class

### 4.1 Levels (bottom → top)

```
cell                         leaf (existing cell object)
└─ line      = cells_per_line cells in SERIES
   └─ module = lines_parallel (1 or 2 or even more) lines in PARALLEL      ← the "two parallel circuits"
      └─ block = modules_per_block modules                    (combination configurable)
         └─ circuit = n_blocks blocks (+ one blocking diode per block)
```

### 4.2 Parameters (from Picture 2 + voltage cross-check)

| Parameter | Symbol in sketch | Value / range | Combination at this level |
|---|---|---|---|
| `cells_per_line` | `L = 10` | 10 | series |
| `lines_parallel` | `L parallel` | 1 or 2 | parallel |
| `modules_per_block` | (from 70 V / ~23 V/line ≈ 3) | ~3 | **series** (to reach the 70 V bus) |
| `n_blocks` | `B = 20 (15…25)` | 20 | **parallel** (current / redundancy), one blocking diode each |
| `bus_voltage` | `a) 70 V` | ~70 V | operating point |

> **Assumption flagged for review:** "modules in series, blocks in parallel" is my reading of the
> picture, supported by the arithmetic (2.3–2.7 V/cell × 10 × 3 ≈ 70 V; 20 parallel blocks for
> current). To de-risk a misread, the **series/parallel rule is a parameter at every level**
> (`combine="series"|"parallel"`), so any junction can be flipped with one value, no rewrite.

### 4.3 Internal representation

A recursive tree node (one small dataclass):

```python
Group(combine="series"|"parallel", children=[Group | CellRef], id="B3.M2.L1")
```

- Leaves hold a reference (or deep copy) to a `cell` and a stable hierarchical id `B{b}.M{m}.L{l}.C{c}`.
- A flat registry `circuit.cells: dict[str, cell]` maps every id → cell for O(1) fault injection
  and per-cell result extraction.
- Classmethods mirror the existing style:
  `Circuit.fromPrototype(cell, cells_per_line, lines_parallel, modules_per_block, n_blocks, …)`.

### 4.4 Netlist generation

A fresh **recursive netlist builder** that walks the tree and assigns ngspice nodes:

- Series group: chain children head-to-tail, sharing intermediate nodes.
- Parallel group: tie all children between the same two rail nodes.
- Each cell → `cell.buildModel(name=<id>)` subckt instance (reuses proven code).
- Blocking diode per block → reuse the `.model DBlock` + diode snippet from `string.py`.
- Top terminals `out` / `gnd`; drive with `Vtest` at `bus_voltage` (or sweep for IV curve).

This keeps **per-cell addressability** (needed for Monte-Carlo) while standing on the proven
electrical primitives, and avoids the damaged class bodies.

### 4.5 Fault injection

`circuit.fail(cell_id, mode)` where `mode ∈ {open, short, dead, crack(frac)}`:

- `dead`/`open`: `cell.setSeason(0)` (no photocurrent) — the default "failed cell".
- `short`: replace with near-zero resistance.
- `crack`: scale area / isc (uses existing `resizeCell` / `crack` attribute).

## 5. Vectorized electro-thermal coupling

### 5.1 Per-cell steady-state 2-node balance (matches `thermal.py` + Picture 3)

For each cell *i*, in Kelvin, with area `A`, substrate `α_F, α_R, ε_F, ε_R`, conduction
`C = conductivity / thickness` [W/m²·K], `σ` Stefan-Boltzmann, `tilt = cos(incidence)`:

```
Front (T1):  α_F·A·P_Sun·tilt   − ε_F·A·σ·(T1⁴ − T_sp⁴) − P_el + C·A·(T2 − T1) = 0
Rear  (T2):  A·(α_R·P_Albedo + ε_R·P_IR)·tilt − ε_R·A·σ·(T2⁴ − T_sp⁴) − C·A·(T2 − T1) = 0
```

`P_el` = electrical power extracted at that cell = `V_i · I_i` from the circuit solve. In reverse
bias `P_el < 0`, so `−P_el > 0` injects heat — this is the hotspot term.

### 5.2 Vectorization (the win)

Today: `scipy.fsolve` is called **once per cell** in a Python loop. Because cells are thermally
independent (no lateral term), stack `T1, T2` as length-N arrays and solve **all cells at once**
with **vectorized Newton–Raphson**:

- Residual `F(T1, T2)` = the two equations above, evaluated on arrays.
- Analytic block-diagonal 2×2 Jacobian per cell:
  ```
  J = [[ -4 ε_F A σ T1³ − C A ,        C A          ],
       [        C A          , -4 ε_R A σ T2³ − C A ]]
  ```
- Invert the 2×2 in closed form over the whole array each iteration (no per-cell call).
- ~5–8 iterations to convergence; everything is numpy.

### 5.3 Coupling loop (circuit ⇄ thermal)

```
T ← initial guess (e.g. 28 °C everywhere)
repeat:
    rebuild cell models at temperature T           # T shifts isc/imp/vmp/voc via regressors
    solve circuit at bus_voltage in ngspice        # savecurrents already enabled
    extract per-cell (V_i, I_i)  → P_el vector      # V across each XCell, its branch current
    T_new ← vectorized_thermal(P_el, substrate, fluxes)   # §5.2
    if max|T_new − T| < tol: break
    T ← relax(T, T_new)                            # damped update for stability
```

**Known tricky bit:** robustly extracting per-cell `V_i` and `I_i` from the ngspice raw output for
a large netlist. `savecurrents` plus disciplined node naming (each cell id in node names) makes
this tractable; we will validate it on a tiny 2×2 circuit first.

## 6. Substrate model

Schema (from `data/substrates/msro_case2.json`):

```json
{ "name": "SRP MSRO Case 2",
  "alpha_front": 0.970, "alpha_rear": 0.930,
  "epsilon_front": 0.9, "epsilon_rear": 0.89,
  "conductivity": 10, "thickness": 0.01 }
```

- New loader `loadSubstrate(name)` → dataclass `Substrate`.
- Derives `C_cond = conductivity / thickness` [W/m²·K] for the conduction term.
- `data/substrates/` does not yet exist in this working copy → created, seeded with `msro_case2`.

## 7. Environment & orbit-driven fluxes (hapsira)

Replace the broken `eclipse.py` flux path with **hapsira 0.18.0**:

1. Define the orbit (`hapsira.twobody.Orbit`) around the central body (e.g. Mars for MSRO).
2. Propagate over one+ orbit at a chosen step → satellite position/velocity time series.
3. Per step compute:
   - **`P_Sun`**: solar constant scaled by sun distance, **0 during eclipse** (umbra/penumbra via
     hapsira's shadow geometry or the existing cross-product test in `eclipse.py`).
   - **`P_Albedo`**: planet-reflected irradiance at the array (bond albedo × incident solar ×
     view factor from sat altitude/geometry). Replaces the erroneous `albedoIntensity`.
   - **`P_IR`**: planetary thermal IR onto the array (Stefan-Boltzmann of planet × view factor).
   - **`tilt`**: cos of incidence from array normal vs. sun line.
4. Emit a time series of `Environment` objects (reusing `simulation/environment.py`) → feed the
   electro-thermal loop at each step → **time-resolved** temperature, power, and hotspot flags
   over the orbit (worst case identified across the orbit, including eclipse exit transients in a
   later transient iteration).

> hapsira bundles astropy; the bare `import astropy` test failed but hapsira imports fine (lazy).
> Confirm astropy availability inside hapsira's namespace during implementation.

## 8. Breakdown / melt criteria (both, per user)

After the coupled solve converges, per cell flag a destructive event if **either**:

- **Temperature:** `T_front_i ≥ T_threshold` (e.g. aluminium honeycomb softening point —
  *value to be supplied*), or
- **Reverse power:** reverse dissipation `|V_i · I_i|` (when `V_i < 0`) `≥ P_reverse_threshold`
  (*value to be supplied*).

Report per cell: `T_front`, `T_rear`, `P_el`, reverse flag, and which criterion tripped.

## 9. Monte-Carlo failure sweep (all three modes)

A `MonteCarlo` driver over a configured `Circuit`, selectable mode:

- **Position sweep:** fail each cell (or each line) one at a time → rank locations by damage
  (max T, # hotspots, total power loss). Finds the worst/least-damaging position.
- **Count sweep:** fail *k* random cells for k = 1…K, repeated → degradation vs. failure count.
- **Random sampling:** sample N random failure patterns → statistical distribution of total
  power loss / max temperature / # hotspots.

Each run is independent → embarrassingly parallel (joblib later if needed).

## 10. Data representation (Excel question, answered)

- **Source of truth:** tidy **long-format** table, one row per (run, cell):
  `run_id, mode, failed_ids, cell_id, V, I, P_el, T_front, T_rear, reverse_flag, hotspot_flag`
  → **Parquet** (or HDF5) — compact, fast, easy to aggregate.
- **Aggregates / human view:** failure-position **heatmaps** (position → max T), **histograms**
  of power loss / max T / # hotspots across runs, "most vs. least damaging" ranking tables.
- **Excel:** generated *on top* as a readable summary workbook (one sheet per sweep + a ranking
  sheet) — an export, not the primary store. (A per-cell × per-run tensor is the wrong shape for
  Excel as a database.)

## 11. New files / modules (proposed)

```
src/powerpy/circuit.py              # Circuit class + recursive netlist builder + fault injection
src/powerpy/substrate.py            # Substrate dataclass + loadSubstrate()
src/powerpy/thermal_vectorized.py   # vectorized 2-node Newton solver
src/powerpy/electrothermal.py       # circuit ⇄ thermal coupling loop
src/powerpy/environment_orbit.py    # hapsira orbit → fluxes → Environment time series
src/powerpy/montecarlo.py           # 3-mode failure sweep driver
src/powerpy/results.py              # long-format store + Excel/plot export
data/substrates/msro_case2.json     # seed substrate file
tests/                              # 2x2 validation, thermal-vs-fsolve parity, netlist sanity
```

## 12. Validation strategy

1. **Thermal parity:** vectorized solver vs. legacy `thermal()` `fsolve` on the same single cell
   → agree to tolerance.
2. **Netlist sanity:** tiny 2-cells-in-series-×-2-parallel circuit → hand-check nodes, IV curve,
   per-cell V/I extraction.
3. **Reverse-bias sanity:** kill one cell in a 2-parallel line → confirm it goes negative V and
   dissipates (P_el < 0) and heats up.
4. **End-to-end:** small array, one failure, full coupled solve → plausible hotspot.

## 13. Open items needing user input

1. **Topology junctions** — confirm "modules series, blocks parallel" (§4.2) or correct it.
2. **Breakdown thresholds** — numeric `T_threshold` (aluminium) and `P_reverse_threshold`.
3. **Orbit definition** — central body + orbital elements (or a TLE / state vector) for hapsira.
4. **Scale** — typical N cells and N Monte-Carlo runs (drives Parquet vs. HDF5 and parallelism).
5. **Cell + diode types** — which `data/cells/*` and `data/diodes/*` to use as the prototype.
```
