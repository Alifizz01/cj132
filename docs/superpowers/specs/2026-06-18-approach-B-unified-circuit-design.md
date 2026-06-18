# Approach B — Unified Position-Mapped Series-Parallel Circuit (design proposal, for review)

I now have complete grounding. Key findings that reshape the final document:

1. **Angle is dead in analytic path** — confirmed (grep: `angle_*` only in environment.py + pipeline.py, never in `operating_points`).
2. **`failed_open` via `season=0` produces a degenerate 1-point curve** — confirmed (`single_diode_iv` returns `([0.0],[0.0])` when `iph<=0`; `combine_series` with `isc_min=0` collapses the whole string).
3. **`voc` is NOT zeroed by `season`** — confirmed (line 220, `voc *= voltage_loss` only). A `season=0` cell still reports positive Voc.
4. **No per-cell correspondence survives `combine_series`/`combine_parallel`** — confirmed; per-cell power needs real back-propagation, not a "reader".
5. **`single_diode_iv` spans only `[0, Voc]`, clips `I>=0`** — confirmed; no reverse-bias branch exists, so dissipation power is unrecoverable without an engine extension.
6. **There is no separate position-blind `CircuitLayout`/`CircuitString` schema** — the draft invented it. The "circuit JSON" is actually the grid JSON `circuit` block (parsed into `PanelLayout.circuit_params`) plus the ngspice `model/circuit.py`. The `adapt_circuit` adapter in the draft has no real input to adapt.
7. **`tilt` is scalar-threaded through `coupling.py`/`transient.py`/`orbit.py`** — confirmed; per-cell tilt would not reach the coupled loop.
8. **`tilt` multiplies both `qF` and `qR`** — confirmed (lines 130-131); applying deflection to the albedo/IR rear term is physically wrong.

I have everything needed. Here is the final design document.

---

# powerpy Approach "B" — Unified Position-Mapped Series-Parallel Circuit (FINAL)

## 0. The problem this solves (grounded, verified against source)

There are today **two disjoint assembly paths**, each knowing only half of what a unified per-cell study needs:

- **GRID path** (`simulation/grid_build.py::build_array_from_grid` + `config/layout.py::PanelLayout`): knows tile **positions** (flat row-major index `k = r*n_cols + c`; 4-neighbour adjacency in `PanelLayout.neighbours()`, layout.py:86-96; per-tile optics in `prop_arrays()`, layout.py:98-108) and electrical **tags** (`TileType.string`, `TileType.block`). But it collapses each string to a **count**: `StringModel.from_single_cell(prototype, len(idxs), ...)` deep-copies one prototype `CellModel` `len(idxs)` times (string_level.py:51-55, called from grid_build.py:44). The built `CellModel` objects carry **no link back to their tile index `k`** and no per-tile condition.

- **REPORT/SECTIONS path** (`simulation/array_level.py::build_from_report`): knows per-section/per-string **counts and harness params** (`n_sca_series_per_string`, `n_strings_parallel`, `resistance_ohm`) but is **position-blind** — it likewise clones one prototype with `from_single_cell` (array_level.py:81) and `from_single_string`.

- **CIRCUIT / ngspice path** (`model/circuit.py` + `solve/electrical.py`): the recursive netlist for the SPICE escape hatch. It *does* recover true per-cell `(V,I)` via `per_cell_power` (electrical.py:124-131) but only by running ngspice on a probed netlist — it is position-blind for thermal and SPICE-only.

- The **analytic engine** (`combine_series`/`combine_parallel` over `CellModel.iv_curve()`, combine.py) is what actually produces array IV/power **without ngspice** — the mandatory path under the hard constraints.

- The **thermal solver** (`solve/thermal.py::solve_thermal` / `solve_panel`) already accepts **full per-cell arrays** for `area`, `alpha_*`, `epsilon_*`, `p_elec` (it calls `_as_array` on each, thermal.py:122-127); `solve_panel` already zeroes non-cell power via the `generates_power` mask (thermal.py:271). `tilt` is currently the one **scalar** input (thermal.py:104, 130-131).

- The **per-cell condition never reaches the analytic electrical tree**: `apply(env)` broadcasts **one identical frozen `Environment`** to every leaf (`cell_level.py:160-163` stores it verbatim; `string_level.py:62-64` and `array_level.py:39-41` forward the same object down). And the thermal `p_elec` used by the failure study is a **fabricated uniform/override scalar** (`analysis/study.py::make_pe`, study.py:34-44: healthy `+1.1 W`, failed `−9.6 W` via `np.where`), **never derived from a real heterogeneous per-cell IV solve**.

**Approach B = make the tile index `k` the single shared key** through which (a) the analytic electrical tree is built from *distinct* per-tile cells carrying per-tile conditions, and (b) the thermal solver receives per-tile `p_elec` / solar-incidence / optics — so a shaded / failed / aged / deflected tile changes BOTH results, indexed identically, with no arbitrary netlist (that stays in the `model/circuit.py` + ngspice escape hatch).

**The single most important correction the critique forced (and it is correct):** the headline phrase "per-cell deflection flows consistently into BOTH electrical and thermal" was **false** for the analytic engine. `operating_points()` (cell_level.py:165-222) reads only `temperature_c`, `dose_i`, `dose_v`, `season`, `current_loss`, `voltage_loss`, `reference_temperature_c`. It **never** reads `env.angle_alpha_deg` / `env.angle_beta_deg` / `env.albedo_w_m2`. A `dataclasses.replace` that bumps `angle_*` changes **nothing** in the analytic IV. This document removes that false claim and re-routes deflection onto the **current axis** (the only analytic lever), which is the fix the critique recommended. See §3.1 and the "Rejected/Amended critique" log.

---

## 1. DATA MODEL — the unified representation

### 1.1 Principle

One **master grid per panel** (`PanelLayout`, retained verbatim) owns geometry, optics, and string/block tags. On top of it B layers two new things: a **per-cell condition map** and a **position-mapped circuit** in which strings are **ordered lists of flat tile indices `k`**. This single object has BOTH what the grid path had (positions) AND what the report path had (per-string/section electrical params).

### 1.2 Concrete schema (new dataclasses)

New module `schemas/panel_circuit.py` (frozen dataclasses, validated in `__post_init__`, style consistent with `config/layout.py::TileType`). Fields (prose, not code):

- **`CellCondition`** (one entry per generating tile `k`):
  - `state`: one of `"active" | "failed_open" | "failed_short"`. **`"absent"` is removed** — see the bijection decision in §2.3; an unpopulated socket is expressed in the grid/palette (`is_cell=False`), not as a condition.
  - `shade`: irradiance multiplier in `[0,1]`, `1.0` = full sun. **Dual-axis** (electrical current loss AND thermal solar-heat loss — §3).
  - `life`: remaining-fraction knob in `[0,1]`, `1.0` = begin-of-life.
  - `incidence`: a **single per-cell solar-incidence factor in `[0,1]`** (the cosine projection of the cell's local deflection onto the Sun line), `1.0` = normal incidence. This **replaces** the two raw `angle_alpha_deg` / `angle_beta_deg` knobs (see §3.1 and the YAGNI critique adjudication). Authoring may still be in degrees; `setup_sim.py` resolves degrees → `incidence` once, deterministically, so the model carries one scalar.
  - `cell_type`: optional override of the tile's `cell_type`.
  - **`bypass_eligible` is REMOVED** from `CellCondition` (critique was right: it had no engine path; the operative switch lives only on the string — §7).

- **`StringSpec`** (one series string): `id`; `members` = ordered tuple of flat tile indices `k` (series order, canonical row-major); `series_resistance_ohm` (default 0.0); `block_diode_v_drop` (default 0.6); `n_block_diodes` (default 1); `string_shunt_diode` (default True — the bypass diode lives here, not per cell).

- **`SectionSpec`** (strings in parallel = a block): `id`; `strings` = tuple of `StringSpec`; `resistance_ohm` (default 0.0).

- **`PanelSpec`**: `id`; `layout` (a `PanelLayout`); `sections` = tuple of `SectionSpec`; `conditions` = mapping `k → CellCondition` (absent key ⇒ `CellCondition()` default).

- **`ArraySpec`**: `name`; `panels` = tuple of `PanelSpec` (panels in parallel).

### 1.3 Why this supersedes the existing builders

`StringSpec.members` is the ordered `k` list the grid path lost (it kept only `len(idxs)`); the per-string/per-section harness fields are exactly what the report path carried. `n_series = len(members)`, so heterogeneous string lengths fall out for free. The `PanelLayout` is untouched — `neighbours()`, `prop_arrays()`, `cell_strings()`, `pitch_mm` all keep working; the spec layers a circuit + conditions **on top of** the grid.

**Scope correction (over-rebuild critique, partially accepted):** the draft promised three adapters including an `adapt_circuit` for a "circuit JSON" with `CircuitLayout`/`CircuitString` dataclasses. **No such schema exists in the codebase** (verified: the only circuit module is the ngspice `model/circuit.py`; the "circuit JSON" the draft imagined is actually the grid-JSON `"circuit"` block parsed into `PanelLayout.circuit_params`, layout.py:60/173, demonstrated by `grid_circuit_demo.json`). Therefore **`adapt_circuit` is dropped** — it had no real input to adapt. Only two adapters are real: `adapt_grid` (grid JSON / `PanelLayout`) and `adapt_sections` (the report sections sheet). See §6.

---

## 2. THE BIJECTION — "one tile = one cell = one string membership"

### 2.1 The invariant

Let `G = { k : layout's tile is_cell == True }` be the set of **electrically-live** tiles (derived from `prop_arrays()["generates_power"]`, which equals `is_cell`, layout.py:45-47/107). Let `M` be the multiset of all `k` across every `StringSpec.members`. The bijection requires:

1. **Total**: every `k ∈ G` appears in exactly one `members` list.
2. **Injective**: no `k` in two strings, none repeated within a string.
3. **Type-correct**: every `k ∈ members` has `is_cell == True`.
4. **Block consistency**: structurally guaranteed for **natively authored** `ArraySpec` (a string is one `StringSpec` owned by one `SectionSpec`; the section IS the block).

### 2.2 Validator

`validate_bijection(panel: PanelSpec) -> None` computes `G` from `prop_arrays()["generates_power"]`, flattens all `members`, and raises with the offending `k` and its `(r,c)` on: a live tile uncovered (`UncoveredCellError`); a `k` duplicated across/within strings (`DuplicateMembershipError`); a `k` whose tile `is_cell == False` (`NonCellInStringError`); a `k` out of `[0, n_tiles)` (`IndexError`).

### 2.3 Bare / diode / failed / unpopulated tiles (corrected)

- **Bare tiles** (`is_cell == False`): never in any `members`; they exist in the grid, absorb sun, conduct heat, and the solver zeroes their power via the `generates_power` mask (thermal.py:271). Correct, unchanged.
- **Diode tiles** (`is_diode == True`, `is_cell == False`): same as bare for the thermal grid. The bypass/blocking diode is modelled **electrically at the string level** (`StringModel.shunt_diode_v_forward` clamp + block-diode drop, string_level.py:69-80), NOT as a grid tile. A diode tile carries no string membership.
- **Unpopulated socket (the former `"absent"`)** — **critique accepted; the contradiction is resolved by deletion.** The draft said absent tiles "remain in members" yet "drop from `G`", which is self-contradictory and would inflate `n_series` and (because of the dead-cell collapse below) kill the whole string. **Resolution:** an unpopulated socket is expressed as a non-cell palette tile (`is_cell=False`) — it is then a bare thermal tile, never in `G`, never in `members`, exactly like any bare tile. `validate_bijection` additionally asserts **no `members` entry has `is_cell==False`** (invariant #3 already covers it). There is no `"absent"` state.
- **`failed_open` / `failed_short`**: these tiles ARE present, keep their position and adjacency, stay in `G` and in `members`, and are built as well-formed degraded cells (§3.1). They are covered by the bijection.

---

## 3. PER-CELL FLOW — the shared index `k` couples electrical and thermal

### 3.1 Resolve a per-cell condition (corrected physics)

One pure resolver, reused by both sides:

`resolve_cell_env(base_env, cond) -> Environment` returns `dataclasses.replace(base_env, ...)` applying **only levers the analytic engine actually honours**:

- **Shade and incidence both ride the current axis (`season`)**, because `operating_points()` multiplies `isc`/`imp` by `current_loss * season` (cell_level.py:218-219) and `season` is the only illumination lever it reads:
  `season' = base_env.season * cond.shade * cond.incidence`.
  This is the corrected realization of deflection. **The draft's claim that `env.angle_*` makes a cell "off-pointed electrically" is false and is deleted** — verified that `operating_points()` never reads any angle field. Per-cell deflection is realized purely as the cosine `incidence` factor folded into `season`. (Adding a genuine analytic angle term to `operating_points()` would be an engine change the hard constraints forbid; routing it through `season` needs no engine change because `season` is already consumed.)
- **Life on the current axis:** `current_loss' = base_env.current_loss * cond.life` (default). Optionally `life` may instead drive `dose_i`/`dose_v` for a radiation-correct interpretation — configurable, default the simple multiplicative knob.
- **`failed_open` (corrected):** **NOT `season=0`.** The critique is correct that `season=0` yields `isc=imp=0 → single_diode_iv` returns the degenerate single point `([0.0],[0.0])` (cell_level.py:73-74), which makes `combine_series` set `isc_min=0` and collapse the **entire string** to `I≡0` (combine.py:36-37), and can corrupt `voc_min` in `combine_parallel`. Also `season` does not zero `voc` (only `voltage_loss` touches voc, cell_level.py:220), so a `season=0` cell still reports positive Voc — not a clean open. **Resolution:** realize `failed_open` as a **well-formed near-dead cell**: a tiny but positive photocurrent over a full-width Voc sweep, i.e. `season' = ε` (a small positive epsilon, e.g. 1e-6) **and** force the cell's Voc to a small positive value. Because `season` cannot zero Voc, this needs an explicit Voc override (next bullet's mechanism). The result is a monotone curve whose Isc ≈ 0 so the string's forward current collapses to ≈0 (the physically correct "this string is bypassed at the array operating point"), while the curve stays well-formed for `combine_series`/`combine_parallel` and the string's bypass-diode clamp (string_level.py:79) engages on the genuine negative tail.
- **`failed_short` (corrected — needs an explicit mechanism, not an Environment tweak):** the critique is correct that there is **no Environment knob** producing a "near-zero-voltage, current-passing" cell — `voltage_loss` scales both `voc` and `vmp` and re-fits the diode unpredictably. **Resolution (decision required from user, see Open Questions):** the recommended default is to **drop `failed_short` from the analytic Phase-1 scope** (real GaAs cell shorts are rare and are better served by the ngspice escape hatch). If the user needs it analytically, add an explicit `voc_override` field that `CellModel.operating_points()` honours by clamping `(vmp, voc)` to a small value while leaving `isc/imp` intact — this is a small, documented engine change and must NOT be hidden behind a "marked on the CellModel" hand-wave.

`resolve_cell_env` **must be pure and idempotent**, composing `cond` against the **incoming `base_env` argument, never against `self._env`** (critique accepted — see §3.2). The same `cond.shade` and `cond.incidence` are reused on the thermal side (§3.3) so the two solves cannot diverge.

### 3.2 (a) Electrical tree — distinct CellModel per tile, per-cell condition

The builder constructs a **distinct `CellModel` per `k`** (not deep-copied clones) using `StringModel.from_cells([...])` (string_level.py:57-59, already exists, no change). Each cell stores its immutable `_condition` and its `_k`.

`CellModel.apply(env)` changes from `self._env = env` to:
> `self._env = resolve_cell_env(env, self._condition) if self._condition is not None else env`

**Idempotency invariant (critique accepted, made explicit):** the coupling loop and pipeline re-call `array.apply(env)` every outer iteration (coupling.py:77 path; pipeline). `apply` MUST compose `_condition` against the **freshly-passed `env`**, never against the already-resolved `self._env`, or conditions would compound (shade applied twice, thrice…). The stored `_condition` is immutable and `resolve_cell_env` is pure, so repeated `apply(env)` yields identical `operating_points()`. This is a required test (§ implementation steps).

`operating_points()` is **unchanged** — it already reads `season`/`current_loss`/etc. off `self._env`, so the per-cell condition flows in transparently. `combine_series` then sees the **real heterogeneous curves** of a string whose cells differ in shade/life/incidence/state.

**Known limiter, now documented (critique accepted):** `combine_series` caps the shared current grid at `isc_min` (combine.py:36-37) and `combine_parallel` caps the voltage grid at `voc_min` (combine.py:57-58). With heterogeneous conditions this is the intended current-mismatch / voltage-mismatch limiting, but two consequences must be stated: (i) cells with `Isc > isc_min` are only sampled on `[0, isc_min]`, so their curve above `isc_min` is discarded — fine for the forward string curve, but it means a high-Isc cell has **no stored curve data** at currents above `isc_min`, which directly constrains the per-cell power reader (§3.3a / §4); (ii) a weak string's low `voc_min` truncates the parallel combine's voltage axis, which can distort section/panel MPP. A regression test (one weak + several healthy strings vs a fine reference) is required, and `combine_parallel` must only ever receive **strictly-non-decreasing V** over the used region — the new bypass-clamp branch (string_level.py:79) can return repeated `v = -vf` points, so the spec requires the string curve handed upward to be restricted to its `v ≥ 0` portion (or de-duplicated/sorted) before `np.interp`, plus an assertion that each input `v` is non-decreasing.

### 3.3 (b) Thermal solve — per-cell arrays keyed by the same `k`

Indexed by the **same `k`**, B supplies the thermal solver:

- **`p_elec[k]`** — the per-cell extracted/dissipated power, from the back-propagation solver of §3.3a/§4 (NOT a trivial reader). Live-but-failed cells come out negative (reverse-biased dissipation), matching the sign convention `solve/electrical.py` documents (electrical.py:12-14) and the legacy `make_pe` faked.
- **Per-cell solar-incidence factor** — the corrected tilt handling (critique accepted, this is NOT a one-line promotion):
  - Today `tilt` is a single scalar applied to **both** `qF` (front solar) and `qR` (rear albedo+IR), thermal.py:130-131. Multiplying the **rear albedo/IR** term by a per-cell **solar deflection** cosine is **physically wrong** — albedo and planetary IR arrive from the planet, not along the Sun line, so a cell tilted toward the Sun should not change its albedo/IR intake by the same cosine.
  - **Resolution:** introduce a **per-cell solar factor** `s_solar[k] = cond.shade * cond.incidence` that multiplies **only the front solar term** `qF`. Keep the existing scalar `tilt` (global array pointing) where it is, OR — cleaner, recommended — move ALL pointing/deflection into `s_solar` and keep `p_sun` as the raw `AM0 * season` flux to avoid double-counting the global pointing. The rear `qR` term keeps its own (scalar or separately-specified) geometry and is **not** scaled by `s_solar`. This requires splitting the single `tilt` multiply in `solve_thermal` into a front-only per-cell factor and a rear-only factor — several lines and a physics decision, explicitly **not** a backward-compatible one-liner.
  - **Consistency win:** the same `cond.shade * cond.incidence` drives both the electrical `season'` (§3.1) and the thermal front-solar factor — so a shaded/deflected cell **both** loses photocurrent **and** absorbs less front sun (runs cooler), which is the unification B promises. (Critique accepted: the draft listed shade under electrical only and never wired it into thermal solar intake; that gap is now closed.)
- **`area[k]`, `alpha_*[k]`, `epsilon_*[k]`** — already produced per-tile by `prop_arrays()`; a `CellCondition` may optionally post-multiply optics at index `k` (e.g. contamination).

**Coupled-loop threading (critique accepted):** `tilt` is currently passed as a **scalar** through `coupling.py:81/95`, `transient.py:105-106`, and `orbit.py:171`. A per-cell solar factor that varies by `cond` would **not** propagate through these paths unless threaded explicitly. **Resolution / decision:** for Phase 2, scope per-cell solar factor to the **standalone `solve_panel`** path and document that the coupled/transient/orbit loops use a uniform factor for now; OR thread the per-cell factor through all five callers. A back-compat test is required that **scalar `tilt` still broadcasts byte-identically** so the existing single-cell 65.26 °C calibration (thermal.py:9) is unchanged.

### 3.3a Why `k` is the consistency guarantee

The electrical builder iterates `members` (a list of `k`); the thermal solver iterates the flat grid (also `k`); the bijection forces 1:1 correspondence. So the per-cell power vector and the thermal input vectors are the same length and order. The failure study's `make_pe` "centre cell" override (study.py) is replaced by "set `conditions[k].state`", which propagates to BOTH solves. **But** recovering `p_elec[k]` from the analytic tree is non-trivial (next section).

### 3.4 Per-cell power is a back-propagation solver, NOT a reader (critique accepted — this is the biggest feasibility correction)

The draft called `p_elec_by_tile` a "thin reader" that "walks the tree and evaluates `V_cell*I_cell` at the string current." **This is wrong and is corrected.** Verified: `combine_series` resamples children onto a shared `i_grid` and **sums voltages**, returning only the aggregate curve (combine.py:39-45); `combine_parallel` resamples onto a `v_grid` and **sums currents** (combine.py:60-64). **No per-cell correspondence survives.** Worse, `StringModel.iv_curve` applies a block-diode drop, an `I*Rseries` drop, and a clamp/mask **after** combination (string_level.py:69-80), so the string terminal voltage at a given current is **not** the raw series-sum.

Therefore the per-cell power requires a real **recursive operating-point back-propagation** (`simulation/percell_power.py`), specified precisely:

1. Solve the array IV; pick the operating bus voltage `V*` (e.g. at array MPP).
2. **Array → panel:** panels are in parallel, so each panel sees `V*`.
3. **Panel → section:** sections are in parallel within a panel → each section node sees the panel voltage; undo any panel/section series resistance to get the section node voltage.
4. **Section → string:** strings in a section are in parallel → each string operates at the section node voltage `V_sec`. Invert each string's (shifted) curve to get its operating current `I_s` at `V_sec`.
5. **Un-shift the string:** recover the internal raw series-stack voltage `V_raw = V_sec + n_block_diodes*block_diode_v_drop + I_s*series_resistance_ohm` (reversing string_level.py:69-71); handle the clamp branch.
6. **String → cell:** at current `I_s`, invert **each member cell's own cached `iv_curve`** to read `V_cell(I_s)`; write `V_cell * I_s` into `p_elec[k]`.

**The reverse-bias gap (critique accepted, hardest part):** `single_diode_iv` spans only `[0, Voc]` and clips `I ≥ 0` (cell_level.py:77/90). A cell forced **below its own Isc-limited point or into reverse bias** (the very dissipating cell whose negative `p_elec` we need for the hotspot) has **no curve data there**. Reading `V_cell(I_s)` off a forward-only curve for `I_s` outside `[0, Isc_cell]` is undefined. **Two options (decision required, see Open Questions):**
   - (a) **Extend `single_diode_iv` with a modeled reverse-bias branch** (e.g. a linear reverse slope from `Rsh`, or an explicit breakdown/avalanche stub) so per-cell reverse dissipation is recoverable. This is a deliberate, documented engine extension.
   - (b) **Keep the legacy `make_pe` fast path** for the failure study and treat condition-driven physical `p_elec` as opt-in only where forward operation holds; do NOT claim to delete `make_pe` until (a) reproduces the legacy −9.6 W hotspot within tolerance.

**Required gate (energy balance):** the per-cell powers must **sum to the node `calc_mp` power at `V*`** (within tolerance). Without this gate the thermal coupling silently receives wrong `p_elec`. Cleanest implementation: add a small `solve_operating_point(node, v_terminal) -> per-child (v,i)` method to each `SimNode` level (5 small methods: Cell inverts its own curve; String inverts its shift/clamp then shares `I_s`; Section/Panel/Array split V down and sum I up) — **new recursive machinery**, not a reader over existing data. The §4 preamble's "no change needed beyond a reader" is therefore corrected: `combine.py` itself need not change, but a **new** per-level back-propagation method set is required.

---

## 4. BUILDER / ENGINE CHANGES — precise, minimal, corrected

**No change** to `SectionModel`/`PanelModel`/`ArrayModel.iv_curve`, the `Environment` field set, the thermal Newton kernel, or `combine.py`'s combination math.

1. **New `simulation/spec_build.py::build_array_from_spec(spec, cell_params, *, iv_engine="analytic", string_shunt_vf=None)`** — the single builder:
   - per `PanelSpec` → per `SectionSpec` → per `StringSpec`: build `cells = [make_cell(k) for k in string.members]`, where `make_cell(k)` constructs `CellModel(params_for(k), iv_engine=...)` and attaches `_condition = conditions.get(k, CellCondition())` and `_k = k`.
   - `StringModel.from_cells(cells, block_diode_v_drop=..., n_block_diodes=..., series_resistance_ohm=..., shunt_diode_v_forward=(string_shunt_vf if string.string_shunt_diode else None), name=string.id)` — **`from_cells`, not `from_single_cell`** (the one philosophical change vs grid_build.py:44).
   - `SectionModel.from_strings(...)`, `PanelModel.from_sections(...)`, `ArrayModel.from_panels(...)` unchanged.
   - **Deterministic ordering (critique accepted):** iterate sections, strings, and condition keys in a **stable sorted order (by id / by `k`)** so association order is identical across runs and across adapters, and snapshot JSON diffs are stable (§5.3, §7).

2. **`CellModel`** (cell_level.py): add `self._condition = None` and `self._k = None`; change `apply` to the composition in §3.2 (idempotent, composes against the incoming `env`). `operating_points()` unchanged, **except** the optional `voc_override` mechanism IF `failed_short` is kept analytically (§3.1).

3. **`StringModel`** — no change; `from_cells` exists, the bypass clamp already keys off `shunt_diode_v_forward`. (Per-cell `bypass_eligible` removed; the switch is `StringSpec.string_shunt_diode`.)

4. **New `simulation/percell_power.py`** — the recursive back-propagation solver of §3.4 (NOT a reader), plus the `solve_operating_point` methods per `SimNode` level, plus the energy-balance gate. This feeds `solve_panel(p_elec=...)` and the coupling loop's `power_fn`, and is the analytic analogue of the ngspice `solve/electrical.per_cell_power`.

5. **`single_diode_iv` reverse-bias extension** (cell_level.py) — IF option (a) of §3.4 is chosen: add a modeled `V < 0` branch so reverse dissipation is recoverable. Documented engine change + regression test against the legacy −9.6 W hotspot.

6. **`solve_thermal` solar-factor split** (thermal.py) — split the single `tilt` multiply (lines 130-131) into a **per-cell front-solar factor** (`qF *= s_solar`) and a **rear factor** for `qR` (NOT scaled by the solar deflection). Backward compatible only in the sense that a uniform `s_solar = tilt` reproduces today's numbers; the rear/front split is a deliberate physics change (§3.3). `solve_panel` builds `s_solar` from `conditions[k].shade * conditions[k].incidence`.

7. **Deprecate, don't delete:** `build_array_from_grid` and `build_from_report` become thin adapters (`adapt_grid` / `adapt_sections`) that produce an `ArraySpec` and call `build_array_from_spec` (§6).

---

## 5. CONFIG SURFACE — spatial Excel layers + setup_sim.py (design only)

### 5.1 Layer convention

One **master grid** (the existing `PanelLayout` grid + palette) defines geometry, `is_cell`/optics, and string/block tags. On top, **one sheet per attribute**, same `n_rows × n_cols`, cells addressed by `(r,c) → k`:
`layer_state` (active/failed_open[/failed_short]), `layer_shade` (0..1), `layer_life` (0..1), `layer_incidence` (degrees or 0..1; resolved to the single `incidence` factor). A **blank cell = the schema default** (§7).

**`layer_bypass` is removed** (no per-cell engine path). **The optional explicit `ordering` layer is removed** (critique accepted): `combine_series` is order-independent even with heterogeneous cells (voltages add), so an ordering layer is a confusing no-op knob; `members` is always canonical row-major. (We retain `members` as an ordered tuple purely for stable, diffable snapshots — order is diagnostics-only and never load-bearing for power.)

### 5.2 Ownership split (topology vs per-cell values)

- **Topology / circuit ownership (master grid + `"circuit"` block, already parsed into `circuit_params`, layout.py:173):** which tiles are cells; their `string`/`block` tags; `members` (row-major scan of the string tag, the existing `cell_strings()` algorithm); per-string `series_resistance_ohm`/`block_diode_v_drop`/`n_block_diodes`/`string_shunt_diode`; per-section `resistance_ohm`. Authored once per design.
- **Per-cell value ownership (condition layers):** shade / life / incidence / state — **scenario** data that varies per run. Populates `PanelSpec.conditions[k]`.

### 5.3 setup_sim.py responsibilities

`setup_sim.py` reads the master grid + layers, then: (1) normalises every layer to the master shape (reject mismatched shapes); (2) builds `StringSpec.members` via the `cell_strings()` row-major scan, attaching per-string/section params from the `"circuit"` block; (3) assembles `conditions[k]` from the value layers with blank-layer defaults, resolving `layer_incidence` degrees → the single `incidence` cosine factor once; (4) runs `validate_bijection` and fails loudly; (5) emits a **per-run snapshot folder** with the resolved `ArraySpec` serialised to JSON (deterministically sorted `members` and condition keys, per §4) plus a copy of the layers. The simulator consumes the resolved JSON, never the live Excel.

---

## 6. BACKWARD COMPATIBILITY + MIGRATION (corrected: TWO adapters, not three)

### 6.1 Adapters

- **Grid JSON → ArraySpec** (`adapt_grid(layout) -> ArraySpec`): use `layout.cell_strings()` to get `{sid: [k...]}` + `string_block`; one `StringSpec(id=sid, members=tuple(idxs), **circuit_params.get(sid,{}))` per string; group by block into `SectionSpec`; one `PanelSpec` (one grid = one panel); empty `conditions`. **Caveat (critique accepted):** `adapt_grid` calls `cell_strings()`, which still runs the "string spans conflicting blocks" check (layout.py:132-136). So invariant #4's structural guarantee holds **only for natively authored `ArraySpec`**; grid-derived specs inherit `cell_strings()`'s validation (a stricter superset — fine, but we do **not** claim the conflict "cannot occur" globally).
- **Sections sheet → ArraySpec** (`adapt_sections(report) -> ArraySpec`): each `physical_section` → `SectionSpec` (`resistance_ohm = phys.resistance_ohm`); its `n_strings_parallel` strings of `n_sca_series_per_string` cells → `StringSpec`s with **synthesised row-major `members`**; `panel_id` groups sections into `PanelSpec`s; `string_shunt_vf` from `report.cell.string_diode.v_forward` (array_level.py:74).
- **`adapt_circuit` is DROPPED** — there is no position-blind circuit-JSON schema in the codebase to adapt (§1.3).

**Synthetic-grid thermal warning (critique accepted):** `adapt_sections` fabricates row-major positions that did not physically exist. `PanelLayout.neighbours()` would then derive **fictitious adjacency**, so any **lateral-conduction (`g_lat > 0`)** thermal result on a synthetic grid is physically wrong (electrically-unrelated cells treated as thermal neighbours; real adjacencies lost). **Resolution:** `adapt_sections` must produce a grid valid **only** for electrical IV and **independent (`g_lat = 0`)** thermal; the adapter docstring and §6 must state this, and any laterally-coupled study **requires a real grid-JSON `PanelLayout`**. We do **not** repeat the draft's misleading "gives the circuit path a valid thermal grid it never had."

### 6.2 Phased path (regression gate corrected; riskiest step relabelled)

- **Phase 0 (no behaviour change):** add `ArraySpec` + `build_array_from_spec` + `adapt_grid` + `adapt_sections`. Reimplement `build_array_from_grid` / `build_from_report` as adapter → `build_array_from_spec`. **Regression gate corrected (critique accepted):** NOT "byte-for-byte." The bar is `np.allclose(rtol=0, atol<1e-9)` on the resampled array IV and exact-to-`<1e-6` on Isc/Voc/Pmp/Vmp. Scope the gate to **`iv_engine="analytic"`** (the mandatory path); ngspice equality is explicitly **out of scope** (the escape hatch may differ; `from_single_cell`'s deepcopy may carry lazily-built `_legacy` state, cell_level.py:158, that a fresh construct lacks). Pin section/string iteration order (sorted by id) so parallel-sum association order is stable across the adapters. Only `adapt_grid` is expected to match `build_array_from_grid` numerically; `adapt_sections` matches the legacy report builder, not the grid builder, and its synthetic grid has **no thermal baseline** (note this).
- **Phase 1 (per-cell electrical):** add `CellCondition`, `resolve_cell_env`, the idempotent `CellModel.apply` composition, and the `percell_power.py` back-propagation + energy-balance gate. Default conditions = no-op, so Phase 0 results are unchanged. Tests: (i) one shaded cell in a 10-cell string measurably lowers that string's IV; (ii) `apply(env)` twice → identical `operating_points()` (idempotency); (iii) one `failed_open` cell in a 10-cell string within a 3-string section collapses **only** that string's contribution and leaves the other two strings' power intact (guards `voc_min`/`isc_min` cross-contamination); (iv) per-cell powers sum to node `p_mp` at `V*`.
- **Phase 2 (per-cell thermal) — RELABELLED AS THE RISKIEST MIGRATION STEP (critique accepted):** today `study.py` is entirely thermal — `make_pe` fabricates `p_elec` with one cheap `np.where` and never builds an electrical tree. Routing the failure study through condition-driven `build_array_from_spec` + `percell_power` means **every** `O(max_failures × n_cells)` iteration of `worst_case_search` (study.py:99-135) now also builds distinct `CellModel`s and runs the analytic IV solve + back-propagation — a correctness change (the −9.6 W must be reproduced from physics) **and** the largest performance regression in the design. **Resolution:** keep `make_pe`'s fast direct-`p_elec` path as the **default**; make physics-derived `p_elec` **opt-in behind an explicit flag**; require a test that the condition-driven failed cell reproduces the legacy `reverse_w = −9.6` hotspot within tolerance **before** the old path is ever removed. Also split the thermal solar factor (front-only) per §3.3/§4.6 and add the scalar-`tilt`-broadcast back-compat test (65.26 °C unchanged).
- **Phase 3 (config tooling):** `setup_sim.py` + Excel layer reader + snapshot folders. The simulator already consumes resolved `ArraySpec` JSON, so this is purely an authoring front-end.

**Monte-Carlo performance mitigation (critique accepted):** distinct (non-cloned) cells add `N` analytic `single_diode_iv` solves per pattern (each up to 80 Newton iterations, cell_level.py:80) versus one reused deepcopy. For the common MC case where only a handful of cells deviate, **memoize the resolved-environment → IV curve**: cells whose resolved `Environment` is identical share one cached curve (key on the resolved-env tuple); only cells with a non-default `CellCondition` get a unique solve. This preserves Phase-0 numerical equality AND keeps MC cost ≈ unchanged. Add a micro-benchmark gate (e.g. `worst_case_search` on the `grid_3x2x12` layout) to Phase 1/2.

---

## 7. RESOLVED DECISIONS

- **Bypass granularity = per-string, not per-cell.** Modelled where it sits — across a string (`StringModel.shunt_diode_v_forward` clamp) + the block-diode drop. **`CellCondition.bypass_eligible` is removed** (no engine path); the operative switch is `StringSpec.string_shunt_diode` (default `True`, matching `grid_circuit_demo.json`). Per-cell sub-string bypass remains the ngspice escape hatch (§8).
- **One cell = one string membership** — enforced by `validate_bijection` (total + injective + type-correct + structurally one-block for native specs). No `"absent"` state; unpopulated sockets are `is_cell=False` bare tiles.
- **Deflection rides the current axis** — realized as a single `incidence` cosine factor folded into `season` (electrical) and into the front-only thermal solar factor (thermal). Raw `angle_alpha_deg`/`angle_beta_deg` are **not** carried per-cell (the analytic engine ignores them); authoring may be in degrees but `setup_sim.py` resolves to one `incidence` scalar.
- **Shade is dual-axis** — `cond.shade` reduces both photocurrent (`season'`) and front solar heating (`s_solar`), so a shaded cell loses power **and** runs cooler.
- **Blank-layer defaults** — unspecified condition ⇒ `CellCondition(state="active", shade=1.0, life=1.0, incidence=1.0)`; blank circuit block ⇒ existing defaults (`series_resistance_ohm=0.0, block_diode_v_drop=0.6, n_block_diodes=1, string_shunt_diode=True, section resistance=0.0`), matching grid_build.py:46-48. An all-blank set reproduces today's nominal run (analytic) exactly within the §6.2 tolerance.
- **Series order** — canonical row-major; diagnostics/snapshot-stability only, never load-bearing for power. No ordering layer.

---

## 8. NON-GOALS

- **Arbitrary netlist topology stays in the ngspice escape hatch** (`model/circuit.py` + `solve/electrical.py` + `solve/coupling.py`). B keeps fixed wiring rules; it does not flip junctions series↔parallel, nest custom levels, or do per-cell sub-string bypass. B's per-cell `k` deliberately mirrors that path's per-cell ids so the same `CellCondition` map and a per-cell `p_elec` vector can drive either engine, but the analytic engine is never required to build a general graph.
- **`Environment` stays a frozen scalar dataclass.** Per-cell variation is achieved by `dataclasses.replace` at the leaf via `resolve_cell_env`, preserving "build once, evaluate many environments."
- **B does not build the Excel tooling** — only the layer convention + `setup_sim.py` contract.
- **`failed_short` is out of analytic scope by default** (ngspice escape hatch), unless the user opts into the explicit `voc_override` engine change.

---

## Adjudication of critique points (where accepted / where rejected)

**Accepted and folded in (the substantive ones):**
- Angle dead in analytic path → deflection re-routed onto `season` via a single `incidence` factor; false "electrical off-pointing" claim deleted. (Two critique entries said this; both correct — verified by grep.)
- `failed_open` via `season=0` collapses the whole string and leaves Voc positive → realized instead as a well-formed near-dead cell with `season=ε` + explicit Voc override; string-bypass narrative corrected to "the string's forward current collapses (it is bypassed at the array operating point)."
- `failed_short` had no mechanism → dropped from analytic default scope; explicit `voc_override` offered as opt-in.
- `p_elec_by_tile` is not a reader → re-specified as recursive back-propagation with per-level `solve_operating_point` + energy-balance gate; reverse-bias data gap surfaced with two explicit options.
- Reverse-bias branch missing in `single_diode_iv` → flagged as a required engine extension if physical reverse dissipation is wanted; otherwise keep `make_pe`.
- `voc_min`/`isc_min` truncation + non-monotone clamped tail into `combine_parallel` → documented limiter + required monotonic-input assertion + restrict-to-`v≥0` handling.
- Per-cell tilt is not a one-line promotion → split into front-only solar factor vs rear albedo/IR; double-counting of global pointing addressed.
- Shade not wired to thermal → made dual-axis.
- Coupled-loop tilt threading → flagged; scoped or threaded with a back-compat 65.26 °C test.
- "Byte-for-byte" gate → relaxed to `allclose` tolerances, scoped to analytic engine only, ngspice out of scope.
- `"absent"` contradiction → deleted the state; unpopulated = `is_cell=False`.
- `adapt_circuit` over-rebuild → dropped (no such input schema exists); only `adapt_grid` + `adapt_sections` remain.
- Synthetic-grid lateral-thermal hazard → adapters scoped to `g_lat=0`; real grid required for lateral studies.
- Phase-0 vs Phase-2 risk mislabel → Phase 2 (failure-study `make_pe` replacement) relabelled the riskiest step.
- MC performance under distinct cells → resolved-env curve memoization + benchmark gate.
- `bypass_eligible` and the ordering layer YAGNI → both removed.
- `apply` idempotency footgun → made an explicit invariant + test.
- `cell_strings` conflicting-block check still runs at adapt time → caveat added.

**Rejected / amended (with reasons):**
- The critique repeatedly demanded code-level reproduction tests "before declaring success." Accepted as **gates in the phased plan**, but this remains a design/spec doc — no code is written here; the tests are listed as required deliverables, not executed.
- The critique's suggestion to consider an ultra-light Phase 0 (just flip grid_build.py:44 `from_single_cell → from_cells` + thread a `conditions` map, skipping the full `ArraySpec`) is **noted but not adopted as the primary design**, because the stated goal explicitly wants the **unified** representation that also serves the sections path and produces diffable per-run snapshots. We do, however, adopt its spirit: Phase 0 changes **no behaviour**, and the `ArraySpec`/adapter layer is additive and reversible. If the user only ever needs the grid path, the lighter route is the cheaper alternative — flagged as an Open Question.
- The "tilt promotion is exactly one line" low-severity note was itself flagged by another critique entry as wrong (rear/front split needed). We side with the **rear/front-split** position: it is **not** one line. (The two critique entries conflicted; we took the physically-correct one.)
- The critique's claim that `season=0` "still" lets the bypass clamp do something useful was already self-corrected within the critique; we adopt the corrected version (clamp does nothing on an all-zero curve), hence the well-formed near-dead-cell fix.

---

## (a) Concrete implementation steps (high level, for a later plan)

1. Add `schemas/panel_circuit.py`: `CellCondition` (state, shade, life, incidence, cell_type — no bypass/angle), `StringSpec`, `SectionSpec`, `PanelSpec`, `ArraySpec`; validation in `__post_init__`.
2. Add `validate_bijection(panel)` (total / injective / type-correct; reject `is_cell=False` in members; no `absent` state).
3. Add `simulation/spec_build.py::build_array_from_spec` using `StringModel.from_cells`, attaching `_condition`/`_k`, with deterministic sorted iteration.
4. Add `resolve_cell_env` (pure, idempotent; shade·incidence → `season`, life → `current_loss`, `failed_open` → ε-season + Voc override; `failed_short` out of scope by default).
5. Edit `CellModel`: `_condition`/`_k` fields + idempotent composing `apply`; optional `voc_override` honoured by `operating_points` only if `failed_short`/`failed_open` need it.
6. Add `simulation/percell_power.py`: recursive `solve_operating_point` per `SimNode` level + array-MPP `V*` driver + energy-balance gate. Decide reverse-bias handling (extend `single_diode_iv` OR keep `make_pe`).
7. Edit `solve/thermal.py`: split the `tilt` multiply into a per-cell front-solar factor (shade·incidence) and a separate rear factor; `solve_panel` builds the front factor from conditions; keep scalar broadcast back-compat.
8. Write `adapt_grid` and `adapt_sections`; reimplement `build_array_from_grid`/`build_from_report` on top of them; pin sorted ordering.
9. Phase-0 regression: analytic-only `allclose` IV + exact Isc/Voc/Pmp on `simple_3block`, `grid_circuit_demo`, `grid_3x2x12`, and a sections-sheet report.
10. Phase-1 tests: shaded-cell IV drop; `apply` idempotency; `failed_open` isolates one string; per-cell power sums to `p_mp`.
11. Phase-2 (riskiest): opt-in condition-driven `p_elec` for `study.py` behind a flag; reproduce −9.6 W hotspot; front/rear thermal split test; 65.26 °C scalar-tilt back-compat; MC memoization + benchmark gate.
12. Phase-3: `setup_sim.py` Excel-layer reader + per-run snapshot folder emitting resolved, deterministically-sorted `ArraySpec` JSON.

## (b) Open questions needing the user's decision

1. **`failed_short`:** drop from the analytic engine entirely (route to ngspice), or add the explicit `voc_override` engine change? (Recommended: drop by default.)
2. **Reverse-bias power:** extend `single_diode_iv` with a modeled reverse branch (enables physical per-cell dissipation, replaces `make_pe`) — and if so, what reverse model (linear `Rsh` slope vs breakdown/avalanche stub)? Or keep `make_pe` as the default for hotspot studies?
3. **Per-cell thermal solar factor scope:** standalone `solve_panel` only (simplest), or thread it through `coupling.py` / `transient.py` / `orbit.py` too (full electro-thermal consistency, more surface)?
4. **`life` semantics:** simple multiplicative `current_loss` knob (default) vs routing through `dose_i`/`dose_v` for a radiation-correct curve?
5. **Global pointing vs per-cell incidence:** keep the existing scalar `tilt` for global pointing and add `incidence` on top (risk of double-count), or move ALL pointing into the per-cell solar factor and make `p_sun` the raw flux? (Recommended: the latter.)
6. **Scope ambition:** build the full unified `ArraySpec` + both adapters now (serves grid + sections + snapshots), or take the lighter grid-only route (flip `from_single_cell → from_cells` + a `conditions` map) and defer the rest until the sections path actually needs position-mapped thermal?
7. **Rear `qR` geometry:** when the front solar factor is split out, should the rear albedo/IR term keep the old scalar `tilt`, get its own per-cell factor, or be left at 1.0?

Key files (all absolute): new `C:\Users\Nitrox\Downloads\powerpy\powerpy\src\powerpy\schemas\panel_circuit.py`, `...\simulation\spec_build.py`, `...\simulation\percell_power.py`; edits to `...\simulation\cell_level.py` (apply/condition + optional voc_override), `...\solve\thermal.py` (front/rear solar split), `...\simulation\grid_build.py` and `...\simulation\array_level.py` (deprecate-in-place adapters); reuse `...\simulation\string_level.py::from_cells` unchanged; escape hatch untouched: `...\model\circuit.py` + `...\solve\electrical.py` + `...\solve\coupling.py`.


# COMMENT from USER
1.  first thing is the is_cell is not needed because i already refer this concept with engineer. there is no as such consideration as bare plate without a cell. so we need to drop off this concept. 
2.  also for lateral conduction. we dont need to consider that because we dont need to consider on this thing . for now actually. so we know temperature for each cell. its already good enough. 
3.  the incidence angle for each cell is necessary because the cell is glued to paper like blanket and its actually produced from carbon fiber. so based on observation. the cell and paper expand on different rate because of that when it expand on different rate. after extreme different rate of expansion. the blanket form bowl like on the long edge. because of that. cell at the middle do have the optimum incidence angle but the cell that locates at the side  . deflected away a little bit from the incidence angle of sun. we need to consider that
4.  Life factor is actually factor that we consider when during any event one of the cell has been chipped during launch of during settling period. therefore the life span factor need to be take into account. therefore this life span factor will effect the current that will be generated by the photovoltai cell
   
# Additional thing 
1.  supplier has come with a variance and standard deviation of pmax and imp of cell. not every cell performs similar to each other. there is variation of that. we need to consider that. so we need to actually define this standard deviation and also the variance and implement it accordingly so every cell can actually mimic actually thing. for now imp have std.dev of 0.0007 and variance of 0.0012 and for pmax have 0.025 std.dev and variance of 0.0034
2.  can you actually figure out what could be much more better excel templates to be used and much more effective and good way to be used as database for this simulation

---

# REFINEMENTS (user-confirmed 2026-06-18 — these SUPERSEDE conflicting earlier sections)

1. **No bare-plate / `is_cell` concept** — every tile IS a cell. Drop bare/diode-tile handling and the `absent` state; the bijection is total over all tiles; the `generates_power` mask is effectively all-true. (Supersedes §2.3.)
2. **No lateral conduction for now** — thermal solve is independent per-cell (`g_lat = 0`); the §6 synthetic-grid lateral hazard is moot. Worst-case neighbour reinforcement is consciously deferred.
3. **Per-cell incidence is required and position-structured** — cells are glued to a carbon-fibre blanket; CTE-mismatch bows the blanket (bowl along the long edge) → centre cells point optimally, edge cells deflect off-Sun. `setup_sim` COMPUTES incidence from a bow profile (edge deflection / radius of curvature), per-cell-overridable. Realized on the current axis (cosine into `season`) + the front-solar thermal term. (Confirms §3.1; Open-Q5 → fold global pointing into the per-cell factor, `p_sun` = raw flux.)
4. **`life` = mechanical chipping** (launch/settling), derating the cell's generated CURRENT. (Resolves Open-Q4 = `current_loss` knob, not radiation dose.)
5. **Manufacturing variance** — build the per-cell Imp & Pmax sampling mechanism (deterministic per seed) but PARAMETERIZE the spread; **σ defaults to 0 (no-op)** until supplier values are confirmed. (Source slide's std-dev/variance table is internally inconsistent — values TBD with supervisor; histogram cross-check suggests σ_Pmax≈0.026 W, σ_Imp≈0.035 A, i.e. CV≈2.4%/1.8%, for a *Si CIC* of different size than the GaAs 3G30 — apply as relative CV, confirm actual-cell data.)
6. **Remaining opens resolved:** Q1 `failed_short` → out of analytic scope (ngspice hatch); Q2 reverse-bias → keep `make_pe` heuristic as default for failure-study dissipation, real per-cell FORWARD power for electrical/budget, defer the reverse-branch engine extension; Q3 per-cell thermal solar factor → standalone `solve_panel` only (don't thread coupling/transient/orbit yet); Q6 scope → build the unified `ArraySpec` but strictly PHASED (Phase 0 additive/no-behaviour-change → Phase 1 per-cell electrical → Phase 2 per-cell thermal opt-in → Phase 3 config tooling); Q7 rear `qR` → keep rear albedo/IR scalar, NOT scaled by incidence.

**Implementation note:** the actual current location of the grid builder must be verified first — on `feature/power-budget` there is a stale `grid_build.cpython-313.pyc` but the `grid_build.py` source may have moved/been removed; the plan's first task is to map the real current builders (`build_array_from_grid` / `build_from_report` / `build_array_from_circuit`).