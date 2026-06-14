# What's New — Customized Circuit + Vectorized Electro-Thermal + Monte-Carlo

**Date:** 2026-06-08
**Applies to:** this working copy (`C:\Users\Nitrox\Downloads\powerpy\powerpy`).
**Implements:** `docs/superpowers/specs/2026-06-07-customized-circuit-thermal-design.md`
and Chapter 2 of the study notes.

All additions are **new files** (nothing existing was modified), so the "diff" is
the file list below. The pure-numpy core is implemented **and tested** (19 tests
passing); the parts that need ngspice or `hapsira` against the OCR-damaged legacy
`cell.py` are written and structured but marked **integration-pending**.

## New files

| File | Lines | Purpose | Status |
|---|---:|---|---|
| `src/powerpy/data/substrates/msro_case2.json` | 9 | Seed substrate (the folder did not exist here) | data |
| `src/powerpy/substrate.py` | 102 | `Substrate` dataclass + loader; derives `c_cond = conductivity/thickness` | **tested** |
| `src/powerpy/thermal_vectorized.py` | 164 | Vectorized 2-node Newton solver (all cells at once) | **tested** |
| `src/powerpy/circuit.py` | 212 | Parametric `Circuit`: recursive tree, per-cell ids, fault injection, netlist build | **tested** (stub cell) |
| `src/powerpy/breakdown.py` | 47 | Temperature **and** reverse-power breakdown criteria (OR) | **tested** |
| `src/powerpy/electrothermal.py` | 99 | Damped fixed-point circuit⇄thermal coupling loop | loop **tested** (injected power_fn) |
| `src/powerpy/montecarlo.py` | 93 | 3-mode failure sweep (position/count/random), ranking, run-count math | **tested** |
| `src/powerpy/environment_orbit.py` | 87 | Orbit fluxes — inverse-square sun, eclipse, albedo, IR, tilt; hapsira seam | flux math **tested** |
| `src/powerpy/results.py` | 88 | Long-format (Parquet/HDF5) store + summaries + Excel export | **tested** (pandas) |
| `tests/test_thermal_vectorized.py` | 86 | 4 tests — solver vs hand-worked oracle | ✓ |
| `tests/test_circuit.py` | 104 | 6 tests — topology/registry/faults/netlist | ✓ |
| `tests/test_pipeline.py` | 138 | 9 tests — breakdown/coupling/MC/flux/results | ✓ |

## What is verified (run from the repo root)

```
python tests/test_thermal_vectorized.py    # 4/4
python tests/test_circuit.py               # 6/6
python tests/test_pipeline.py              # 9/9
```

Key proven results (the physics, from the tests):
- Substrate `msro_case2` loads; `c_cond = 10/0.01 = 1000 W/m²K`.
- Single sunlit cell converges to **65.26 °C front / 64.60 °C rear** — matches the
  hand-worked 2-node balance (the oracle).
- One **vectorized** solve over a 4-cell array gives healthy **38.89 °C**, idle
  **65.26 °C**, and the reverse-biased dissipating cell **187.48 °C** — the
  quantified hot-spot.
- The coupling loop reproduces those temperatures from an injected power function.
- Breakdown flags the 187 °C / 9.6 W-reverse cell as destroyed on **both** criteria.

## Design notes

- **No legacy imports.** The new modules do **not** import the OCR-damaged
  `cell.py`/`string.py`. Cells are duck-typed (`buildModel`, `setSeason`), so the
  topology and netlist assembly are testable with a stub cell now, and will work
  with the real `cell` once its syntax is repaired.
- **Reuses what exists.** `datamgmt.getSubstrateData` already had the substrate
  schema; `simulation/environment.Environment` already carries albedo/season/angles.
- **Series/parallel is a parameter at every level** in `Circuit` (`from_prototype`
  takes `line/module/block/circuit_combine`), so a different reading of the wiring
  is a one-value change.

## Integration-pending (needs the legacy base repaired first)

1. Repair the OCR syntax defects in `cell.py` (e.g. the duplicated-`self`
   signature, unbalanced parens) so `cell.buildModel` is callable.
2. Rename `string.py` (stdlib shadowing) and/or make the package installable, so
   imports stop depending on the working directory.
3. Wire `electrothermal.couple`'s `power_fn` to the real ngspice solve and the
   per-cell V,I read-back (validate on a 2×2 circuit first — the main risk).
4. Fill `environment_orbit.propagate_fluxes` with a concrete mission orbit.

See `docs/superpowers/specs/2026-06-07-customized-circuit-thermal-design.md` §13
for the open inputs (breakdown thresholds, orbit, scale, cell/diode types).
