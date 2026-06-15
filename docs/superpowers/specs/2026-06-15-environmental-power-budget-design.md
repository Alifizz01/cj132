# Environmental Power Budget in Reports

**Date:** 2026-06-15
**Status:** Approved design

## Goal

Add an **Environmental Power Budget** to both the thermal report and the
Monte-Carlo report. It shows, per unit area (W/m²), the power the array
*withdraws* from the Sun as electricity at the space-grade cell efficiency
(~30 %), and the **albedo** and **planetary infrared (IR)** loads — with the
calculation worked out and printed (formula → substituted numbers → result).

The albedo/IR inputs come from the mission **orbit/environment config**
(the `mission_orbit` sheet), and the same albedo/IR fluxes are fed into the
actual thermal solve so reported temperatures are consistent with the reported
loads (Approach B).

## Background — what exists today

- **Physics primitives** already exist in `model/environment.py`:
  - `solar_irradiance(distance_au, eclipsed)` → AM0/d²
  - `albedo_flux(bond_albedo, solar_at_planet, view_factor)` → `a·S·F`
  - `planetary_ir_flux(planet_temp_k, emissivity, view_factor)` → `ε·σ·T⁴·F`
  - constants `AM0 = 1367`, `SIGMA = 5.670367e-8`
- **Orbit toolkit** `model/orbit.py` already propagates a Keplerian orbit and
  has `orbit_flux_timeline(...)`. There is **no** `view_factor_to_planet`
  helper yet (view factor is a hardcoded `0.3` default — a LEO value).
- **`mission_orbit` sheet** already exists in `params.xlsx` as a key-value
  sheet (`param | name | value | unit | type | source`) and holds:
  `orbit_type=GEO`, `altitude_km=35786`, `inclination_deg=0`,
  `sun_intensity_bol=1367`, `sun_intensity_eol_min=1322`, `temp_max_K`,
  `temp_min_K`, `bus_voltage`, `max_string_current`, `max_beta_angle_deg`,
  plus mission dates/durations.
  It is **NOT loaded** into `ReportMetadata` — `loader/report.py` only loads
  `mission_param` (the long-format operating-points sheet). The key-value sheet
  has **no** `bond_albedo`, `planet_temp_k`, or `ir_emissivity`.
- **Reports today** hardcode `p_albedo=0.0, p_ir=0.0`:
  - `analysis/thermal_report.py` (`equilibrium_point`, `hotspot_case`)
  - `analysis/montecarlo_report.py` (`solve_kwargs`)
- `scripts/set_mission_orbit.py` is an idempotent key-value editor for the
  `mission_orbit` sheet; `scripts/build_params.py` rebuilds the whole workbook.

## Key physical fact

The mission orbit is **GEO** (35,786 km), not the LEO of the `orbit.py` demo.
At GEO the Earth view factor is small, so albedo and IR are small but nonzero.
Therefore the view factor **must be computed from altitude**, not taken as the
LEO `0.3` default:

```
F = (R_earth / (R_earth + altitude))²
  ≈ (6378 / 42164)²  ≈ 0.023   (GEO)
  ≈ (6378 / 6878)²   ≈ 0.86    (500 km LEO, nadir upper bound)
```

This is the geometric nadir view factor of a flat plate to a sphere — the
upper bound when the face looks straight at the planet.

## Quantities reported (per m²)

With `S` = solar irradiance, `F` = view factor from altitude, `η` = 0.30,
`a` = bond albedo, `T_p` = planet temperature, `ε` = IR emissivity, `tilt` =
pointing cosine:

| Term                 | Formula                       |
|----------------------|-------------------------------|
| Incident solar       | `S` (from sheet, EOL min)     |
| Electrical extracted | `P_elec = η · S · tilt`       |
| Albedo               | `P_alb  = a · S · F`          |
| Planetary IR         | `P_IR   = ε · σ · T_p⁴ · F`   |
| View factor          | `F = (R_e / (R_e + alt))²`    |

## Architecture — components (each isolated, single-purpose)

### 1. `model/orbit.py` — `view_factor_to_planet`
```python
def view_factor_to_planet(altitude_km: float,
                          body_radius_km: float = R_EARTH_M / 1e3) -> float:
    """Geometric nadir view factor of a flat plate to the planet sphere.
    F = (R / (R + h))^2.  Upper bound (face looking straight down)."""
```
Pure, no new deps. Reused by the budget. Unit tested against the GEO/LEO
numbers above.

### 2. `schemas/mission.py` — `MissionOrbit`
A frozen dataclass over the key-value `mission_orbit` sheet.

- Store the full key→value map (`params: dict[str, float | str]`) so nothing
  is lost.
- Typed properties for the values the budget needs, each with a default when
  the row is absent:
  - `altitude_km` (required)
  - `sun_intensity_eol_min` (default `AM0 = 1367`)
  - `sun_intensity_bol` (default `1367`)
  - `bond_albedo` (default `0.30`)
  - `planet_temp_k` (default `255.0`)
  - `ir_emissivity` (default `1.0`)
- A generic `get(param, default)` for everything else.

### 3. `loader/mission.py` — `load_mission_orbit`
```python
def load_mission_orbit(params_file: Path) -> MissionOrbit:
```
- Read sheet `mission_orbit` (key-value: `param | name | value | unit | type`).
- Coerce each `value` by its `type` column (`float`/`string`/`date`).
- Tolerate the sheet missing required albedo/IR rows (defaults fill in).
- Wire into `loader/report.py` and add `mission_orbit: MissionOrbit` to
  `ReportMetadata` (`schemas/report.py`).

### 4. `params.xlsx` + `build_params.py`
- Add three rows to `mission_orbit` (idempotently, via extending
  `scripts/set_mission_orbit.py._CHANGES`):
  - `bond_albedo   = 0.30` (`-`, float)
  - `planet_temp_k = 255`  (`K`, float)
  - `ir_emissivity = 1.0`  (`-`, float)
- Add the same three rows to the `mission_orbit` block in
  `scripts/build_params.py` so a full rebuild reproduces them.

### 5. `analysis/power_budget.py` (new)
```python
@dataclass(frozen=True)
class CalcLine:
    label: str        # "Albedo load"
    formula: str      # "P_alb = a · S · F"
    substitution: str # "= 0.30 × 1322 × 0.023"
    value_w_m2: float # 9.1

@dataclass(frozen=True)
class PowerBudget:
    incident_solar_w_m2: float
    electrical_w_m2: float
    albedo_w_m2: float
    ir_w_m2: float
    efficiency: float
    view_factor: float
    tilt: float
    lines: tuple[CalcLine, ...]   # the worked "show calculation"

def compute_power_budget(orbit: MissionOrbit, *, season: float = 1.0,
                         tilt: float = 1.0, efficiency: float = 0.30
                         ) -> PowerBudget:
```
- `S = orbit.sun_intensity_eol_min * season`
- `F = view_factor_to_planet(orbit.altitude_km)`
- `electrical = efficiency * S * tilt`
- `albedo     = albedo_flux(orbit.bond_albedo, S, F)`
- `ir         = planetary_ir_flux(orbit.planet_temp_k, orbit.ir_emissivity, F)`
- Build one `CalcLine` per term (formula + substituted numbers + result).
- No I/O, no rendering. Unit tested with known values.

### 6. Wire into both data layers (Approach B)
- `analysis/thermal_report.py`:
  - `ThermalReportData` gains `power_budget: PowerBudget`.
  - `run_thermal_report(...)` accepts `efficiency: float = 0.30`, computes the
    budget from `md.mission_orbit`, and passes `p_albedo=budget.albedo_w_m2`,
    `p_ir=budget.ir_w_m2` into `equilibrium_point`'s `solve_thermal` and
    `hotspot_case`'s `solve_panel` (replacing the hardcoded `0.0`).
- `analysis/montecarlo_report.py`:
  - `MCReportData` gains `power_budget: PowerBudget`.
  - `solve_kwargs` get `p_albedo`/`p_ir` from the budget instead of `0.0`.
- Electrical term: the budget displays the requested flat `η·S`. The thermal
  solve keeps using the model's actual MPP power (`imp·vmp`) for temperatures.
  Both are printed and labelled so they are not confused.

### 7. Templates
Add an **"Environmental Power Budget"** section to:
- `render/templates/thermal_report.tex.jinja`
- `render/templates/montecarlo_report.tex.jinja`

Each section has:
- a table of the four terms in W/m² (incident solar, electrical @ η,
  albedo, IR) + the view factor and orbit altitude;
- a **Calculation** block rendering each `CalcLine`
  (`label`, `formula = substitution = value`);
- a one-line note: budget electrical = `η·S` (space-grade ~30 %); solve uses
  the model's computed MPP power.

The render data layers (`render/thermal_report.py`, `render/montecarlo_report.py`)
pass `power_budget` into the Jinja context.

## Data flow

```
params.xlsx[mission_orbit]
   -> load_mission_orbit() -> MissionOrbit  (in ReportMetadata)
        -> compute_power_budget(orbit, season, tilt, eff) -> PowerBudget
             |-> p_albedo, p_ir --> solve_thermal / solve_panel  (temperatures)
             |-> PowerBudget ------> Jinja context --> .tex --> PDF (budget table + calc)
```

## Error handling

- Missing `mission_orbit` sheet → loader raises a clear error (it exists today;
  this guards regressions).
- Missing optional rows (`bond_albedo`, `planet_temp_k`, `ir_emissivity`) →
  `MissionOrbit` properties return documented defaults (0.30 / 255 K / 1.0).
- `altitude_km` absent or ≤ 0 → loader raises (required for view factor).
- Non-numeric value where a float is expected → coercion error naming the
  param and sheet.

## Testing

- `tests` for `view_factor_to_planet` — GEO ≈ 0.023, LEO 500 km ≈ 0.86,
  altitude 0 → 1.0, monotonic decreasing in altitude.
- `tests` for `compute_power_budget` — known inputs produce known W/m² and the
  `CalcLine` substitution strings contain the right numbers.
- `tests` for `load_mission_orbit` — reads the sheet, applies defaults for
  missing albedo/IR rows, coerces types.
- Render smoke tests — both reports build a `.tex` containing the budget
  section and (where pdflatex is available) compile to PDF.

## Out of scope (YAGNI)

- Orbit-averaged / time-resolved albedo & IR (eclipse-weighted). The budget is
  the sunlit-arc steady value at the chosen `season`/`tilt`.
- RAAN / day-of-year inputs (not needed for the budget's view-factor model).
- Changing the electrical model to a flat 30 % in the solve — the solve keeps
  real MPP power; 30 % is a reporting figure only.
