# Environmental Power Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-m² environmental power budget (incident solar, electrical extracted at ~30% cell efficiency, albedo, planetary IR — with the calculation shown) to both the thermal and Monte-Carlo reports, with albedo/IR derived from the mission orbit and fed into the actual thermal solve.

**Architecture:** Load the existing `mission_orbit` sheet into `ReportMetadata` (new `MissionOrbit` schema + loader). A new pure `analysis/power_budget.py` computes the four W/m² terms and the worked-calculation lines from a `MissionOrbit`, using a new geometric `view_factor_to_planet(altitude_km)` (GEO → F≈0.023). Both report data layers compute the budget, feed its albedo/IR into `solve_thermal`/`solve_panel`, and pass the `PowerBudget` to the templates, which render a budget table + a "Calculation" block.

**Tech Stack:** Python 3.13, numpy, pandas, openpyxl, Jinja2 (custom `<<% %>>` / `<< >>` delimiters, `tex`/`num` filters), pdflatex (MiKTeX), pytest.

---

## File Structure

- `src/powerpy/model/orbit.py` — **modify**: add `view_factor_to_planet`.
- `src/powerpy/schemas/mission.py` — **modify**: add `MissionOrbit` dataclass.
- `src/powerpy/schemas/__init__.py` — **modify**: export `MissionOrbit`.
- `src/powerpy/schemas/report.py` — **modify**: add `mission_orbit` field.
- `src/powerpy/loader/mission.py` — **modify**: add `load_mission_orbit`.
- `src/powerpy/loader/report.py` — **modify**: wire `load_mission_orbit` in.
- `src/powerpy/analysis/power_budget.py` — **create**: `PowerBudget`, `CalcLine`, `compute_power_budget`, `DEFAULT_ORBIT`.
- `src/powerpy/analysis/thermal_report.py` — **modify**: feed albedo/IR into solve; expose `power_budget`.
- `src/powerpy/analysis/montecarlo_report.py` — **modify**: feed albedo/IR into solve; expose `power_budget`.
- `src/powerpy/render/thermal_report.py` — **modify**: pass `power_budget` to template.
- `src/powerpy/render/montecarlo_report.py` — **modify**: pass `power_budget` to template.
- `src/powerpy/render/templates/thermal_report.tex.jinja` — **modify**: add budget section.
- `src/powerpy/render/templates/montecarlo_report.tex.jinja` — **modify**: add budget section.
- `scripts/set_mission_orbit.py` — **modify**: add the 3 albedo/IR rows to `_CHANGES`.
- `scripts/build_params.py` — **modify**: add the 3 rows to the `mission_orbit` block.
- `params.xlsx` — **modify** (via the scripts): gains 3 rows.
- `tests/test_power_budget.py` — **create**: view factor + budget + loader tests.

---

## Task 1: Geometric view factor from altitude

**Files:**
- Modify: `src/powerpy/model/orbit.py` (add function after `view`-free helpers, e.g. near `orbital_period`)
- Test: `tests/test_power_budget.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_power_budget.py`:

```python
"""Environmental power budget: view factor, budget math, orbit loader."""
import numpy as np
import pytest

from powerpy.model.orbit import view_factor_to_planet


def test_view_factor_geo():
    # GEO 35786 km: F = (R/(R+h))^2 with R = 6378.137 km
    assert view_factor_to_planet(35786.0) == pytest.approx(0.02288, abs=1e-4)


def test_view_factor_leo():
    # 500 km LEO nadir upper bound ~ 0.86
    assert view_factor_to_planet(500.0) == pytest.approx(0.860, abs=1e-3)


def test_view_factor_surface_is_one():
    assert view_factor_to_planet(0.0) == pytest.approx(1.0, abs=1e-9)


def test_view_factor_decreases_with_altitude():
    assert view_factor_to_planet(500.0) > view_factor_to_planet(35786.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_power_budget.py -v`
Expected: FAIL with `ImportError: cannot import name 'view_factor_to_planet'`

- [ ] **Step 3: Add the function**

In `src/powerpy/model/orbit.py`, after `orbital_period` (around line 63), add:

```python
def view_factor_to_planet(altitude_km: float,
                          body_radius_km: float = R_EARTH_M / 1e3) -> float:
    """Geometric nadir view factor of a flat plate to the planet sphere.

    ``F = (R / (R + h))**2`` -- the fraction of a downward-facing plate's
    hemisphere filled by the planet disc.  This is the upper bound (face
    looking straight at the planet); it falls with altitude, so GEO sees a
    much smaller albedo/IR load than LEO.
    """
    if altitude_km < 0:
        raise ValueError("altitude_km must be >= 0")
    return float((body_radius_km / (body_radius_km + altitude_km)) ** 2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_power_budget.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/powerpy/model/orbit.py tests/test_power_budget.py
git commit -m "feat(orbit): add view_factor_to_planet(altitude_km)"
```

---

## Task 2: MissionOrbit schema

**Files:**
- Modify: `src/powerpy/schemas/mission.py` (append new dataclass)
- Modify: `src/powerpy/schemas/__init__.py` (export)
- Test: `tests/test_power_budget.py` (add)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_power_budget.py`:

```python
from powerpy.schemas.mission import MissionOrbit


def _orbit():
    return MissionOrbit(params={
        "altitude_km": 35786.0,
        "sun_intensity_eol_min": 1322.0,
        "sun_intensity_bol": 1367.0,
        "bond_albedo": 0.30,
        "planet_temp_k": 255.0,
        "ir_emissivity": 1.0,
    })


def test_mission_orbit_typed_accessors():
    o = _orbit()
    assert o.altitude_km == 35786.0
    assert o.sun_intensity_eol_min == 1322.0
    assert o.bond_albedo == 0.30
    assert o.planet_temp_k == 255.0
    assert o.ir_emissivity == 1.0


def test_mission_orbit_defaults_when_missing():
    o = MissionOrbit(params={"altitude_km": 500.0})
    assert o.bond_albedo == 0.30        # default
    assert o.planet_temp_k == 255.0     # default
    assert o.ir_emissivity == 1.0       # default
    assert o.sun_intensity_eol_min == 1367.0  # default AM0


def test_mission_orbit_altitude_required():
    with pytest.raises(KeyError):
        _ = MissionOrbit(params={}).altitude_km
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_power_budget.py -k mission_orbit -v`
Expected: FAIL with `ImportError: cannot import name 'MissionOrbit'`

- [ ] **Step 3: Add the dataclass**

Append to `src/powerpy/schemas/mission.py`:

```python
@dataclass(frozen=True)
class MissionOrbit:
    """Key-value ``mission_orbit`` sheet: orbit + environment parameters.

    Holds the raw param->value map (nothing is dropped) and exposes typed
    accessors for the values the power budget and thermal solve need.  Optical
    environment params absent from the workbook fall back to documented LEO/Earth
    defaults.
    """
    params: dict

    def get(self, key: str, default=None):
        return self.params.get(key, default)

    @property
    def altitude_km(self) -> float:
        if "altitude_km" not in self.params:
            raise KeyError("mission_orbit: 'altitude_km' is required")
        return float(self.params["altitude_km"])

    @property
    def sun_intensity_eol_min(self) -> float:
        return float(self.params.get("sun_intensity_eol_min", 1367.0))

    @property
    def sun_intensity_bol(self) -> float:
        return float(self.params.get("sun_intensity_bol", 1367.0))

    @property
    def bond_albedo(self) -> float:
        return float(self.params.get("bond_albedo", 0.30))

    @property
    def planet_temp_k(self) -> float:
        return float(self.params.get("planet_temp_k", 255.0))

    @property
    def ir_emissivity(self) -> float:
        return float(self.params.get("ir_emissivity", 1.0))
```

- [ ] **Step 4: Export it**

In `src/powerpy/schemas/__init__.py`, change the mission import line:

```python
from powerpy.schemas.mission import MissionParameters, MissionOrbit
```

and add `"MissionOrbit",` to the `__all__` list (right after `"MissionParameters",`).

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_power_budget.py -k mission_orbit -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add src/powerpy/schemas/mission.py src/powerpy/schemas/__init__.py tests/test_power_budget.py
git commit -m "feat(schema): add MissionOrbit key-value orbit/environment schema"
```

---

## Task 3: Load mission_orbit into ReportMetadata

**Files:**
- Modify: `src/powerpy/loader/mission.py` (add loader)
- Modify: `src/powerpy/schemas/report.py` (add field)
- Modify: `src/powerpy/loader/report.py` (wire in)
- Test: `tests/test_power_budget.py` (add)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_power_budget.py`:

```python
from pathlib import Path
from powerpy.loader.report import load_report_data

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"

needs_params = pytest.mark.skipif(
    not PARAMS.exists(), reason="params.xlsx not present")


@needs_params
def test_report_loads_mission_orbit():
    md = load_report_data(PARAMS, DATA)
    assert md.mission_orbit is not None
    assert md.mission_orbit.altitude_km == 35786.0          # GEO
    assert md.mission_orbit.sun_intensity_eol_min == 1322.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_power_budget.py -k mission_orbit -v`
Expected: FAIL with `AttributeError: 'ReportMetadata' object has no attribute 'mission_orbit'`

- [ ] **Step 3: Add the loader**

In `src/powerpy/loader/mission.py`, add the import and function. Change the import block to include the key-value helper and the new schema:

```python
from powerpy.loader._common import (
    clean_optional,
    filter_included,
    load_keyvalue_sheet,
    require_float,
    require_str,
    validate_required_columns,
    validate_unique,
)
from powerpy.schemas.mission import (
    MissionOperatingPoint,
    MissionOrbit,
    MissionParameters,
)
```

Then append:

```python
def load_mission_orbit(params_file: Path, data_dir: Path) -> MissionOrbit:
    """Load the key-value ``mission_orbit`` sheet (orbit + environment params)."""
    values = load_keyvalue_sheet(params_file, "mission_orbit", data_dir)
    if "altitude_km" not in values:
        raise ValueError("mission_orbit: required key 'altitude_km' is missing")
    if float(values["altitude_km"]) <= 0:
        raise ValueError("mission_orbit: 'altitude_km' must be > 0")
    return MissionOrbit(params=values)
```

- [ ] **Step 4: Add the field to ReportMetadata**

In `src/powerpy/schemas/report.py`, add the import and the field (default `None` so any direct construction stays valid):

```python
from powerpy.schemas.mission import MissionParameters, MissionOrbit
```

Inside the `ReportMetadata` dataclass body, after the `structure` field, add:

```python
    mission_orbit: MissionOrbit | None = None
```

- [ ] **Step 5: Wire it into the report loader**

In `src/powerpy/loader/report.py`, change the mission import and the constructor:

```python
from powerpy.loader.mission import load_mission_parameters, load_mission_orbit
```

and in the `ReportMetadata(...)` call add the argument (after `mission=...`):

```python
        mission_orbit=load_mission_orbit(params_file, data_dir),
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_power_budget.py -k mission_orbit -v`
Expected: PASS

- [ ] **Step 7: Regression-check the full loader still imports/loads**

Run: `python -m pytest tests/test_thermal_report.py tests/test_loader_validation.py -v`
Expected: PASS (no breakage from the new field)

- [ ] **Step 8: Commit**

```bash
git add src/powerpy/loader/mission.py src/powerpy/loader/report.py src/powerpy/schemas/report.py tests/test_power_budget.py
git commit -m "feat(loader): load mission_orbit sheet into ReportMetadata"
```

---

## Task 4: Add albedo/IR rows to the workbook

**Files:**
- Modify: `scripts/set_mission_orbit.py` (`_CHANGES`)
- Modify: `scripts/build_params.py` (`mission_orbit` block)
- Modify: `params.xlsx` (produced by running the script)

- [ ] **Step 1: Extend the idempotent editor**

In `scripts/set_mission_orbit.py`, replace the `_CHANGES` dict with:

```python
# param -> (value, name, unit, type)   (name/unit/type only used when CREATING)
_CHANGES = {
    "bus_voltage":        (101.5, "Bus Voltage", "V", "float"),
    "max_beta_angle_deg": (23.5,  "Max Beta Angle", "deg", "float"),
    "bond_albedo":        (0.30,  "Bond Albedo", "-", "float"),
    "planet_temp_k":      (255.0, "Planet Temperature", "K", "float"),
    "ir_emissivity":      (1.0,   "Planet IR Emissivity", "-", "float"),
}
```

- [ ] **Step 2: Run the editor against the workbook**

Run: `python scripts/set_mission_orbit.py`
Expected output includes:
```
added   bond_albedo          = 0.3 -
added   planet_temp_k        = 255.0 K
added   ir_emissivity        = 1.0 -
saved -> ...params.xlsx
```

- [ ] **Step 3: Add the same rows to the rebuild script**

In `scripts/build_params.py`, in the `('mission_orbit', [...])` block, after the `max_beta_angle_deg` row (line ~167), add:

```python
        ['bond_albedo', 'Bond Albedo', 0.30, '-', 'float', None],
        ['planet_temp_k', 'Planet Temperature', 255, 'K', 'float', None],
        ['ir_emissivity', 'Planet IR Emissivity', 1.0, '-', 'float', None],
```

and update the block comment `# --- mission_orbit (15 data rows) ---` to `# --- mission_orbit (18 data rows) ---`.

- [ ] **Step 4: Verify the loader now sees the new params**

Run:
```bash
python -c "from pathlib import Path; from powerpy.loader.report import load_report_data; md=load_report_data(Path('params.xlsx'), Path('src/powerpy/data')); o=md.mission_orbit; print(o.bond_albedo, o.planet_temp_k, o.ir_emissivity)"
```
Expected: `0.3 255.0 1.0`

- [ ] **Step 5: Commit**

```bash
git add scripts/set_mission_orbit.py scripts/build_params.py params.xlsx
git commit -m "feat(params): add bond_albedo/planet_temp_k/ir_emissivity to mission_orbit"
```

---

## Task 5: The power-budget calculator

**Files:**
- Create: `src/powerpy/analysis/power_budget.py`
- Test: `tests/test_power_budget.py` (add)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_power_budget.py`:

```python
from powerpy.analysis.power_budget import compute_power_budget, PowerBudget


def test_power_budget_values_geo():
    b = compute_power_budget(_orbit(), season=1.0, tilt=1.0, efficiency=0.30)
    assert isinstance(b, PowerBudget)
    assert b.view_factor == pytest.approx(0.02288, abs=1e-4)
    assert b.incident_solar_w_m2 == pytest.approx(1322.0, abs=0.1)
    assert b.electrical_w_m2 == pytest.approx(396.6, abs=0.2)   # 0.30 * 1322
    assert b.albedo_w_m2 == pytest.approx(9.08, abs=0.05)        # 0.30*1322*F
    assert b.ir_w_m2 == pytest.approx(5.49, abs=0.05)            # sigma*255^4*F


def test_power_budget_lines_show_calculation():
    b = compute_power_budget(_orbit(), season=1.0, tilt=1.0, efficiency=0.30)
    labels = [ln.label for ln in b.lines]
    assert "Electrical extracted" in labels
    assert "Albedo load" in labels
    assert "Planetary IR load" in labels
    elec = next(ln for ln in b.lines if ln.label == "Electrical extracted")
    assert "0.30" in elec.substitution and "1322" in elec.substitution
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_power_budget.py -k power_budget -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'powerpy.analysis.power_budget'`

- [ ] **Step 3: Create the module**

Create `src/powerpy/analysis/power_budget.py`:

```python
"""Environmental power budget (per m^2) for the reports.

Pure calculation: given the mission orbit/environment, it returns the four
power-density terms a report shows -- incident solar, electrical extracted at
the cell efficiency, albedo, and planetary IR -- plus the worked-calculation
lines (formula + substituted numbers + result) used to print the derivation.

Albedo/IR use the geometric view factor from altitude, so GEO automatically
sees a much smaller planetary load than LEO.  No I/O, no rendering.
"""
from __future__ import annotations

from dataclasses import dataclass

from powerpy.model.environment import SIGMA, albedo_flux, planetary_ir_flux
from powerpy.model.orbit import view_factor_to_planet
from powerpy.schemas.mission import MissionOrbit

# A GEO fallback used only when ReportMetadata carries no mission_orbit
# (e.g. hand-built metadata in a test); the loader always supplies a real one.
DEFAULT_ORBIT = MissionOrbit(params={
    "altitude_km": 35786.0, "sun_intensity_eol_min": 1322.0,
})


@dataclass(frozen=True)
class CalcLine:
    """One worked line of the budget derivation."""
    label: str          # "Albedo load"
    formula: str        # LaTeX math, e.g. r"P_{\mathrm{alb}} = a \cdot S \cdot F"
    substitution: str   # LaTeX math, e.g. r"0.30 \times 1322 \times 0.0229"
    value_w_m2: float


@dataclass(frozen=True)
class PowerBudget:
    incident_solar_w_m2: float
    electrical_w_m2: float
    albedo_w_m2: float
    ir_w_m2: float
    efficiency: float
    view_factor: float
    tilt: float
    altitude_km: float
    lines: tuple


def compute_power_budget(orbit: MissionOrbit, *, season: float = 1.0,
                         tilt: float = 1.0,
                         efficiency: float = 0.30) -> PowerBudget:
    """Per-m^2 environmental power budget for one operating point.

    ``efficiency`` is the space-grade cell conversion efficiency (~0.30) used
    for the *displayed* electrical term; the thermal solve still uses the
    model's computed MPP power.
    """
    s = orbit.sun_intensity_eol_min * season       # incident solar [W/m^2]
    f = view_factor_to_planet(orbit.altitude_km)    # geometric view factor
    a = orbit.bond_albedo
    tp = orbit.planet_temp_k
    eps = orbit.ir_emissivity

    electrical = efficiency * s * tilt
    albedo = albedo_flux(a, s, f)
    ir = planetary_ir_flux(tp, eps, f)

    lines = (
        CalcLine(
            "Incident solar", r"S = S_{\mathrm{EOL}} \cdot \mathrm{season}",
            r"%.0f \times %.3f" % (orbit.sun_intensity_eol_min, season), s),
        CalcLine(
            "Electrical extracted",
            r"P_{\mathrm{elec}} = \eta \cdot S \cdot \cos\theta",
            r"%.2f \times %.0f \times %.3f" % (efficiency, s, tilt), electrical),
        CalcLine(
            "Albedo load", r"P_{\mathrm{alb}} = a \cdot S \cdot F",
            r"%.2f \times %.0f \times %.4f" % (a, s, f), albedo),
        CalcLine(
            "Planetary IR load",
            r"P_{\mathrm{IR}} = \varepsilon\,\sigma\,T_p^4\,F",
            r"%.2f \times %.3g \times %.0f^4 \times %.4f" % (eps, SIGMA, tp, f),
            ir),
    )
    return PowerBudget(
        incident_solar_w_m2=s, electrical_w_m2=electrical,
        albedo_w_m2=albedo, ir_w_m2=ir, efficiency=efficiency,
        view_factor=f, tilt=tilt, altitude_km=orbit.altitude_km, lines=lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_power_budget.py -k power_budget -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/powerpy/analysis/power_budget.py tests/test_power_budget.py
git commit -m "feat(analysis): add compute_power_budget (per-m^2 solar/elec/albedo/IR)"
```

---

## Task 6: Feed albedo/IR into the thermal report + expose the budget

**Files:**
- Modify: `src/powerpy/analysis/thermal_report.py`
- Test: `tests/test_power_budget.py` (add)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_power_budget.py`:

```python
from powerpy.analysis.thermal_report import run_thermal_report, ThermalCase
from powerpy.schemas._common import Phase
from powerpy.schemas.fluxes import LaunchConfig


@needs_params
def test_thermal_report_has_power_budget():
    md = load_report_data(PARAMS, DATA)
    cases = [ThermalCase("EOL", Phase.END_OF_LIFE, LaunchConfig.SINGLE,
                          season=0.967)]
    d = run_thermal_report(md, cases)
    assert d.power_budget is not None
    assert d.power_budget.electrical_w_m2 > 0
    # GEO -> small but non-zero planetary loads
    assert 0 < d.power_budget.albedo_w_m2 < 50
    assert 0 < d.power_budget.ir_w_m2 < 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_power_budget.py -k thermal_report_has -v`
Expected: FAIL with `AttributeError: 'ThermalReportData' object has no attribute 'power_budget'`

- [ ] **Step 3: Wire the budget into the analysis**

In `src/powerpy/analysis/thermal_report.py`:

(a) Add the import near the top (after the existing `from powerpy.solve.thermal import ...`):

```python
from powerpy.analysis.power_budget import (
    DEFAULT_ORBIT, PowerBudget, compute_power_budget,
)
from powerpy.schemas.mission import MissionOrbit
```

(b) Add a `power_budget` field to `ThermalReportData` (after `layout`):

```python
    power_budget: PowerBudget | None = None
```

(c) Give `equilibrium_point` an `orbit`/`efficiency` and feed albedo/IR into the solve. Replace the current signature and the `solve_thermal(...)` call:

```python
def equilibrium_point(md: ReportMetadata, sub: Substrate,
                      case: ThermalCase, *,
                      orbit: MissionOrbit = DEFAULT_ORBIT,
                      efficiency: float = 0.30) -> ThermalPoint:
    """Steady-state temperature of one representative cell for ``case``."""
    env = environment_for_phase(
        md, phase=case.phase, launch_config=case.launch_config,
        season=case.season)
    alpha_f, eps_f, area = _cell_optics(md)
    p_sun = AM0 * case.season
    p_elec = _p_elec_per_cell(md, env)
    budget = compute_power_budget(orbit, season=case.season,
                                  efficiency=efficiency)

    res = solve_thermal(
        area=area,
        alpha_front=alpha_f, alpha_rear=sub.alpha_rear,
        epsilon_front=eps_f, epsilon_rear=sub.epsilon_rear,
        c_cond=sub.c_cond,
        p_sun=p_sun, p_albedo=budget.albedo_w_m2, p_ir=budget.ir_w_m2,
        p_elec=p_elec,
    )
    return ThermalPoint(
        case=case, p_sun=p_sun, p_elec_w=p_elec,
        t_front_c=float(np.ravel(res.t_front_c)[0]),
        t_rear_c=float(np.ravel(res.t_rear_c)[0]),
    )
```

(d) Give `hotspot_case` the same and feed albedo/IR into `solve_panel`. Change its signature to add `orbit`/`efficiency` keywords and replace the `solve_panel(...)` call's flux args:

In the signature (the `def hotspot_case(...)` keyword list), add after `g_lat: float = 0.02`:

```python
                 orbit: MissionOrbit = DEFAULT_ORBIT,
                 efficiency: float = 0.30,
```

Right before the `res = solve_panel(...)` call, add:

```python
    budget = compute_power_budget(orbit, season=case.season,
                                  efficiency=efficiency)
```

and change the `solve_panel(...)` call's `p_albedo=0.0, p_ir=0.0` to:

```python
        p_albedo=budget.albedo_w_m2, p_ir=budget.ir_w_m2,
```

(e) In `run_thermal_report`, add an `efficiency` keyword, resolve the orbit, thread it into the calls, and store the budget. Change the signature to add (after `t_limit_c: float = 150.0`):

```python
                       efficiency: float = 0.30) -> ThermalReportData:
```

(remove the old closing `) -> ThermalReportData:` so the new keyword is inside the arg list). After `sub = (...)` resolution near the top of the body, add:

```python
    orbit = md.mission_orbit if md.mission_orbit is not None else DEFAULT_ORBIT
```

Change the points/hotspot calls to pass the orbit:

```python
    points = [equilibrium_point(md, sub, c, orbit=orbit, efficiency=efficiency)
              for c in cases]
```

```python
    hot, grid = hotspot_case(md, sub, ref, layout=layout, area=area,
                             t_limit_c=t_limit_c, orbit=orbit,
                             efficiency=efficiency)
```

Compute the report-level budget at the reference case season and add it to the return:

```python
    power_budget = compute_power_budget(orbit, season=ref.season,
                                        efficiency=efficiency)
```

and add `power_budget=power_budget,` to the `ThermalReportData(...)` constructor.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_power_budget.py -k thermal_report_has -v`
Expected: PASS

- [ ] **Step 5: Regression-check the existing thermal-report test**

Run: `python -m pytest tests/test_thermal_report.py -v`
Expected: PASS (temperatures shift slightly upward at GEO; the existing assertions check physical sanity ranges, not exact values — if any exact-value assertion now fails, that is the expected consistency change and the test bound should be widened in the same commit).

- [ ] **Step 6: Commit**

```bash
git add src/powerpy/analysis/thermal_report.py tests/test_power_budget.py
git commit -m "feat(thermal-report): feed orbit albedo/IR into solve + expose power budget"
```

---

## Task 7: Feed albedo/IR into the Monte-Carlo report + expose the budget

**Files:**
- Modify: `src/powerpy/analysis/montecarlo_report.py`
- Test: `tests/test_power_budget.py` (add)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_power_budget.py`:

```python
from powerpy.analysis.montecarlo_report import run_mc_study


@needs_params
def test_mc_report_has_power_budget():
    md = load_report_data(PARAMS, DATA)
    d = run_mc_study(md, n_rows=4, n_cols=4, max_runs=10, target_se=99.0,
                     season=0.967, workers=1, seed=0)
    assert d.power_budget is not None
    assert d.power_budget.electrical_w_m2 > 0
    assert 0 < d.power_budget.albedo_w_m2 < 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_power_budget.py -k mc_report_has -v`
Expected: FAIL with `AttributeError: 'MCReportData' object has no attribute 'power_budget'`

- [ ] **Step 3: Wire the budget into the analysis**

In `src/powerpy/analysis/montecarlo_report.py`:

(a) Add imports (after the existing `from powerpy.simulation.pipeline import environment_for_phase`):

```python
from powerpy.analysis.power_budget import DEFAULT_ORBIT, compute_power_budget
from powerpy.schemas.mission import MissionOrbit
```

(b) Add a `power_budget` field to `MCReportData` (after `worst_grid`):

```python
    power_budget: object = None
```

(c) Add an `efficiency` keyword to `run_mc_study` (after `workers: int = 4`):

```python
                 efficiency: float = 0.30) -> MCReportData:
```

(remove the old closing `) -> MCReportData:`).

(d) Right before `solve_kwargs = dict(...)`, compute the budget and replace the hardcoded fluxes:

```python
    orbit = md.mission_orbit if md.mission_orbit is not None else DEFAULT_ORBIT
    budget = compute_power_budget(orbit, season=season, efficiency=efficiency)

    solve_kwargs = dict(p_sun=AM0 * season,
                        p_albedo=budget.albedo_w_m2, p_ir=budget.ir_w_m2,
                        c_cond=sub.c_cond, g_lat=g_lat, area=area)
```

(e) Add `power_budget=budget,` to the `MCReportData(...)` constructor at the end.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_power_budget.py -k mc_report_has -v`
Expected: PASS

- [ ] **Step 5: Regression-check the panel-study test**

Run: `python -m pytest tests/test_panel_study.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/powerpy/analysis/montecarlo_report.py tests/test_power_budget.py
git commit -m "feat(mc-report): feed orbit albedo/IR into solve + expose power budget"
```

---

## Task 8: Thermal report template — budget section

**Files:**
- Modify: `src/powerpy/render/thermal_report.py` (template context)
- Modify: `src/powerpy/render/templates/thermal_report.tex.jinja`
- Test: manual render smoke (commands below)

- [ ] **Step 1: Pass the budget into the template context**

In `src/powerpy/render/thermal_report.py`, in `render(...)`, add to the `tmpl.render(...)` keyword args (after `layout_figure=layout_figure,`):

```python
            power_budget=self.data.power_budget,
```

- [ ] **Step 2: Add the section to the template**

In `src/powerpy/render/templates/thermal_report.tex.jinja`, insert this block immediately after the Thermal Inputs table (after line 56, the `\end{table}` that closes section 1, before the `% 1b. layout` comment):

```latex
% ---------------------------------------------------------------- 1a. power budget
<<% if power_budget %>>
\clearpage
\section{Environmental Power Budget}
\noindent Per unit area, at view factor \(F=<< power_budget.view_factor | num(".4f") >>\)
(altitude << power_budget.altitude_km | num(".0f") >>~km).  The electrical term is
the power withdrawn from the Sun at the space-grade cell efficiency
\(\eta=<< power_budget.efficiency | num(".2f") >>\); the thermal solve uses the
model's computed MPP power for temperatures.

\begin{table}[H]
  \centering
  \rowcolors{2}{white}{tablerowgrey}
  \begin{tabular}{|>{\raggedright\arraybackslash}p{0.52\linewidth}|r|l|}
    \hline
    \reporthead{\textbf{Term} & \textbf{Value} & \textbf{Unit}}\\ \hline
    Incident solar \(S\)                 & << power_budget.incident_solar_w_m2 | num(".1f") >> & \si{\watt\per\square\metre}\\ \hline
    Electrical extracted \(\eta S\)      & << power_budget.electrical_w_m2 | num(".1f") >> & \si{\watt\per\square\metre}\\ \hline
    Albedo load                          & << power_budget.albedo_w_m2 | num(".2f") >> & \si{\watt\per\square\metre}\\ \hline
    Planetary IR load                    & << power_budget.ir_w_m2 | num(".2f") >> & \si{\watt\per\square\metre}\\ \hline
  \end{tabular}
\end{table}

\subsection*{Calculation}
\begin{itemize}
<<% for line in power_budget.lines %>>
  \item \textbf{<< line.label | tex >>:}\quad\(<< line.formula >>\;=\;<< line.substitution >>\;=\;<< line.value_w_m2 | num(".2f") >>~\si{\watt\per\square\metre}\)
<<% endfor %>>
\end{itemize}
<<% endif %>>
```

- [ ] **Step 3: Render + compile the thermal report**

Run:
```bash
python -c "
from pathlib import Path
from powerpy.loader.report import load_report_data
from powerpy.render.thermal_report import ThermalReport
from powerpy.analysis.thermal_report import ThermalCase
from powerpy.schemas._common import Phase
from powerpy.schemas.fluxes import LaunchConfig
md = load_report_data(Path('params.xlsx'), Path('src/powerpy/data'))
cases = [ThermalCase('EOL', Phase.END_OF_LIFE, LaunchConfig.SINGLE, season=0.967)]
ThermalReport.from_metadata(md, cases).render('build_thermal').compile_pdf('reports/Thermal_Report.pdf')
print('OK')
"
```
Expected: prints `OK`, no `CompileError`. Verify the budget text is in the `.tex`:
```bash
grep -c "Environmental Power Budget" build_thermal/thermal_report.tex
```
Expected: `1`

- [ ] **Step 4: Commit**

```bash
git add src/powerpy/render/thermal_report.py src/powerpy/render/templates/thermal_report.tex.jinja
git commit -m "feat(thermal-report): render Environmental Power Budget section"
```

---

## Task 9: Monte-Carlo template — budget section

**Files:**
- Modify: `src/powerpy/render/montecarlo_report.py` (template context)
- Modify: `src/powerpy/render/templates/montecarlo_report.tex.jinja`
- Test: manual render smoke (commands below)

- [ ] **Step 1: Pass the budget into the template context**

In `src/powerpy/render/montecarlo_report.py`, in `render(...)`, add to the `tmpl.render(...)` keyword args (after `worst_figure=worst_figure,`):

```python
            power_budget=self.data.power_budget,
```

- [ ] **Step 2: Add the section to the template**

In `src/powerpy/render/templates/montecarlo_report.tex.jinja`, insert this block immediately after the Study Setup table (after line 52, the `\end{table}` that closes the setup section, before the `% 2. results` comment):

```latex
% ---------------------------------------------------------------- 1a. power budget
<<% if power_budget %>>
\clearpage
\section{Environmental Power Budget}
\noindent Per unit area, at view factor \(F=<< power_budget.view_factor | num(".4f") >>\)
(altitude << power_budget.altitude_km | num(".0f") >>~km).  The electrical term is
the power withdrawn from the Sun at the space-grade cell efficiency
\(\eta=<< power_budget.efficiency | num(".2f") >>\); the thermal solve uses the
model's computed MPP power for temperatures.

\begin{table}[H]
  \centering
  \rowcolors{2}{white}{tablerowgrey}
  \begin{tabularx}{\linewidth}{|L|r|l|}
    \hline
    \reporthead{\textbf{Term} & \textbf{Value} & \textbf{Unit}}\\ \hline
    Incident solar \(S\)                 & << power_budget.incident_solar_w_m2 | num(".1f") >> & \si{\watt\per\square\metre}\\ \hline
    Electrical extracted \(\eta S\)      & << power_budget.electrical_w_m2 | num(".1f") >> & \si{\watt\per\square\metre}\\ \hline
    Albedo load                          & << power_budget.albedo_w_m2 | num(".2f") >> & \si{\watt\per\square\metre}\\ \hline
    Planetary IR load                    & << power_budget.ir_w_m2 | num(".2f") >> & \si{\watt\per\square\metre}\\ \hline
  \end{tabularx}
\end{table}

\subsection*{Calculation}
\begin{itemize}
<<% for line in power_budget.lines %>>
  \item \textbf{<< line.label | tex >>:}\quad\(<< line.formula >>\;=\;<< line.substitution >>\;=\;<< line.value_w_m2 | num(".2f") >>~\si{\watt\per\square\metre}\)
<<% endfor %>>
\end{itemize}
<<% endif %>>
```

- [ ] **Step 3: Render + compile the Monte-Carlo report**

Run:
```bash
python examples/run_montecarlo.py
```
Expected: prints the study numbers and `PDF: ...reports\MonteCarlo_Report.pdf` with no `CompileError`. Verify the section landed:
```bash
grep -c "Environmental Power Budget" build_montecarlo/montecarlo_report.tex
```
Expected: `1`

- [ ] **Step 4: Commit**

```bash
git add src/powerpy/render/montecarlo_report.py src/powerpy/render/templates/montecarlo_report.tex.jinja
git commit -m "feat(mc-report): render Environmental Power Budget section"
```

---

## Task 10: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the whole test suite**

Run: `python -m pytest -q`
Expected: all pass (or only pre-existing unrelated skips).

- [ ] **Step 2: Confirm both PDFs exist and are fresh**

Run:
```bash
ls -la reports/Thermal_Report.pdf reports/MonteCarlo_Report.pdf
```
Expected: both present with current timestamps.

- [ ] **Step 3: Final commit (if any cleanup was needed)**

```bash
git add -A
git commit -m "test: full power-budget feature verification" || echo "nothing to commit"
```

---

## Self-Review notes

- **Spec coverage:** view factor (Task 1), `MissionOrbit` schema (Task 2), loader + `ReportMetadata` wiring (Task 3), workbook rows + `build_params` (Task 4), `power_budget.py` with shown calculation (Task 5), Approach B feeding the solve in both reports (Tasks 6–7), templates for both reports (Tasks 8–9), tests throughout + full-suite check (Task 10). All spec sections map to a task.
- **Consistency:** `compute_power_budget` / `PowerBudget` / `CalcLine` / `view_factor_to_planet` / `MissionOrbit` / `DEFAULT_ORBIT` names are identical across definition (Tasks 1, 2, 5) and use (Tasks 6–9). Template field names (`incident_solar_w_m2`, `electrical_w_m2`, `albedo_w_m2`, `ir_w_m2`, `view_factor`, `efficiency`, `altitude_km`, `lines`, and `CalcLine.label/formula/substitution/value_w_m2`) match the dataclass in Task 5.
- **CalcLine strings are trusted LaTeX math** (rendered inside `\(...\)` without the `tex` filter); only `label` is escaped. This is deliberate — `formula`/`substitution` contain `\cdot`, `\times`, superscripts.
- **Non-breaking:** new dataclass fields (`mission_orbit`, `power_budget`) all have defaults; new function keywords (`orbit`, `efficiency`) all have defaults, so existing callers are unaffected.
