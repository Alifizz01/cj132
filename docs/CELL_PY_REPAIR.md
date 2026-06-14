# Repairing `cell.py` to close the electrical↔thermal loop

**Goal:** make `powerpy.cell.Cell.buildModel(...)` importable & callable so the new electrical solve
(`powerpy.solve.electrical`) can run the real circuit netlist through ngspice and feed per-cell `P_elec` into
the electro-thermal coupling loop. The wiring is **already built and tested** with a mock SPICE runner
(`tests/test_electrical.py`, 4/4); this file lists exactly what in the OCR-damaged `cell.py` blocks the real
runner, and how to switch over.

## The defects (in the working copy `src/powerpy/cell.py`)

| Line | Kind | Current (broken) | Fix |
|---|---|---|---|
| **156** | **parse blocker** | `def setTemperature(self, self, temperature):` | `def setTemperature(self, temperature):` — drop the duplicated `self` |
| **436** | **parse blocker** | `def currentAtVoltage(self, self, voltage, unrestricted=False):` | `def currentAtVoltage(self, voltage, unrestricted=False):` — drop the duplicated `self` |
| **665–667** | **missing source** | `imp_dt = (config["isc_dt"] * \` then `# === MISSING: lines 666-667 not photographed ===` | restore the continuation of the `imp_dt` expression for the `temperature <= 0` branch from the **authoritative repo** (`C:\Users\BIMU152\...`); not recoverable from the scan |
| **274** | logic (OCR-obscured) | `# self.config["isc"] = self.config["isc"] * size_coeff  # OCR_UNCLEAR` | almost certainly uncomment & restore to mirror `imp` on line 275: `self.config["isc"] = self.config["isc"] * size_coeff` — confirm against the authoritative repo |

The two **duplicated-`self`** lines are the actual import blockers — fix those two and the module parses. The
**665–667** gap is the only part that needs the original source (a multi-line formula was cut off); everything
else is mechanical.

## Also (already tracked, not in cell.py)
- **Rename `string.py`** — it shadows the stdlib `string` when the cwd is inside the package. Rename (e.g.
  `pv_string.py`) and update its importers.
- These are listed in the code-book legacy table (`PowerPy_Code_Listing.pdf`).

## What the circuit/electrical layer needs from a cell (the contract)
`build_probed_netlist` emits, per cell: `X<id> <pos> <neg> <subckt_name>`. So a cell must provide:
- `buildModel(name=...) -> (subckt_string, subckt_name)` where the **subckt declares exactly two ports in
  (positive, negative) order** matching that instance line. ✅ verify the legacy `modelToArguments` port order.
- `setSeason(value)` — used by `Circuit.fail(...)`. ✅ present.
- `setTemperature(value)` — used by the coupling temperature hook (after the L156 fix). ✅ present once fixed.

## Going live (the one-arg switch)
The coupling is built so swapping mock → real ngspice is a single change:

```python
from powerpy.solve import make_power_fn, ngspice_runner, couple

run = ngspice_runner()                       # was: a mock run(netlist)->Solution in tests

def set_temps(circuit, T):                    # push current temps into the cell IV models
    for cid, t in zip(circuit.cell_ids, T):
        circuit.cells[cid].setTemperature(float(t))

power_fn = make_power_fn(circuit, v_bus=V_op, run=run, set_temps=set_temps)
result = couple(power_fn=power_fn, area=..., alpha_front=..., ..., c_cond=..., p_sun=...)
```

## Validation ladder (do in this order)
1. Fix L156 + L436 → confirm `import powerpy.cell` succeeds.
2. Restore L665–667 (+ L274) from the authoritative repo → confirm `Cell.buildModel()` returns a 2-port subckt.
3. On a **2×2** circuit, compare `per_cell_vi(circuit, v_bus, ngspice_runner())` against the cell's own
   `currentAtVoltage(...)` at the same operating point — they must agree.
4. Run `couple(power_fn=make_power_fn(...), ...)` and confirm convergence + that a shaded/failed cell shows the
   reverse-bias hot-spot. The mock-based `tests/test_electrical.py` already proves the wiring; this confirms the
   physics with the real solver.
