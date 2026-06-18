# Per-Cell Position-Mapped Circuit (Approach B, Phase 0+1) Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: superpowers:subagent-driven-development — execute each numbered Task as its own TDD micro-cycle (write failing test → run → minimal code → run → commit). Do not batch tasks; do not write implementation before its failing test.

**Goal**
Add a position-mapped, per-cell circuit description ("approach B") to powerpy in two additive phases. Phase 0 introduces frozen spec dataclasses (`ArraySpec`/`PanelSpec`/`SectionSpec`/`StringSpec` whose members are ordered tile-index lists), a `validate_bijection` over all tiles, a `build_array_from_spec` that wires `StringModel.from_cells` (one distinct `CellModel` per tile, never `from_single_cell`), and adapters from the two existing inputs (`PanelLayout` grid and the report `ArrayLayout` sections) — the section/circuit adapters reproducing today's analytic array IV bit-for-bit within tolerance against the *live* builders, the grid adapter proven by a structural-equivalence gate (no live electrical grid builder exists to regress against). Phase 1 adds a per-cell `CellCondition` (state/shade/life/incidence/cell_type + manufacturing-variance `imp_factor`/`pmax_factor`), a pure idempotent `resolve_cell_env` mapping condition→`Environment` that *consumes every condition field* (so no field is wired-but-inert), a per-cell `CellModel` that carries its own condition with an idempotent `apply`, and a seeded, default-off manufacturing-variance sampler. Tests prove a shaded/chipped/failed_open/manufacturing-variant cell changes the array IV correctly and that `apply()` is idempotent.

**Architecture**
The existing composition tree is `CellModel` (leaf) → `StringModel` (series) → `SectionModel` (parallel) → `PanelModel` (parallel) → `ArrayModel` (parallel), combined by `combine_series`/`combine_parallel`, driven by a frozen `Environment` via `apply(env)` then `iv_curve()`. Approach B sits *beside* the existing two builders (`build_from_report` in `array_level.py`, `build_array_from_circuit` in `circuit_build.py`): a new module `simulation/spec_build.py` consumes a new spec schema `schemas/panel_circuit.py`. The spec is purely structural — ordered tile indices grouped string→section→panel→array — plus per-string electrical knobs mirroring `CircuitString`. `build_array_from_spec` instantiates one `CellModel` per tile index and assembles them with `StringModel.from_cells` / `SectionModel.from_strings` / `PanelModel.from_sections` / `ArrayModel.from_panels`. Adapters (`adapt_grid`, `adapt_sections`, `adapt_circuit`) translate the existing `PanelLayout`, the report `ArrayLayout`, and a free-form `CircuitLayout` into a spec. The **section/circuit adapters** are no-behaviour-change refactors verified by an `np.allclose` IV regression gate against the *live* builders (`build_from_report`, `build_array_from_circuit`). The **grid adapter** has NO pre-existing electrical builder to regress against — the `PanelLayout` grid feeds the thermal solver, not an `ArrayModel` — so its Phase-0 gate is a *structural-equivalence* check (the spec-built tree equals a hand-built `from_cells` tree of the same shape), not a behaviour-preservation check. Phase 1 attaches a per-cell `CellCondition`; `resolve_cell_env` folds shade·incidence·life·`imp_factor`·`pmax_factor` onto the current axis (`current_loss`, the only current knob the analytic `operating_points` reads) and `pmax_factor` additionally onto the voltage axis (`voltage_loss`), and realises `failed_open` as a near-dead-but-well-formed cell (tiny positive `current_loss` epsilon, which is the load-bearing analytic knob, plus the matching `season` epsilon for the ngspice path) so it does not collapse a series string in `combine_series` (which caps at the smallest child `Isc`).

**Tech Stack**
Python 3.13, numpy only (analytic single-diode path is dependency-free; ngspice stays optional with automatic fallback). `@dataclass(frozen=True)` for all schemas. pytest for tests (no pip install — run from source). Existing modules reused verbatim: `powerpy.simulation.{cell_level,string_level,section_level,panel_level,array_level,combine,environment}`, `powerpy.config.layout.PanelLayout`, `powerpy.schemas.{cell,circuit,layout}`, `powerpy.loader.{circuit,report}`.

## Global Constraints
- **Python 3.13.** Use `from __future__ import annotations` in every new module (matches the codebase).
- **Analytic engine stays dependency-free.** No new mandatory imports beyond numpy; never require ngspice. Default `iv_engine="analytic"` everywhere.
- **Phase 0 reproduces today's analytic array IV for the section/circuit adapters.** The regression gate is: the spec-built array IV vs the *live-builder* array IV must satisfy `np.allclose(v_spec, v_ref, rtol=0, atol=1e-9)` and `np.allclose(i_spec, i_ref, rtol=0, atol=1e-9)`. (Achievable bit-for-bit because spec-built and live-built trees produce the *same* per-curve grids fed to the same `combine_*`.) The **grid adapter** gate is structural-equivalence (spec tree == hand-built `from_cells` tree), since no live electrical grid builder exists.
- **Every new dataclass field has a default** so additions are non-breaking. Required structural fields that cannot default (e.g. the tile-index members) are introduced on brand-new classes only, never added without a default to an existing class.
- **No behaviour change to existing builders in Phase 0.** Adapters are additive. The legacy builders are NOT re-pointed onto the spec in this plan.
- **No produced-but-unconsumed fields.** Every `CellCondition` field must be read by `resolve_cell_env` or `CellModel.operating_points` and exercised by a test that proves a non-default value changes an IV/operating-point result. `imp_factor`/`pmax_factor` are consumed by `resolve_cell_env` (Task 6) and that effect is asserted (Tasks 6 and 8). `voc_override` is **dropped from this plan** (the `failed_open` epsilon path already isolates the string without it; see Task 6/7).
- **Run tests with `python -m pytest`** from the repo root with the src layout on the path: `PYTHONPATH=src python -m pytest`. Package-import-style tests need `PYTHONPATH=src`; the file-path-loading tests do not. There is no `conftest.py` and no registered markers; the only pytest plumbing is the per-module `pytestmark = pytest.mark.skipif(not PARAMS.exists(), ...)` guard used by params-dependent tests.
- **Idempotency contract:** `node.apply(env)` then `node.apply(env)` then `iv_curve()` must equal a single `apply(env)` + `iv_curve()`. This is a property of the whole-tree apply chain: each parent (`StringModel`/`SectionModel`/`PanelModel`/`ArrayModel`) passes the SAME base `Environment` down every solve, and `CellModel.apply` resolves through `resolve_cell_env(self.condition, env)` reading that base env (never the already-resolved `self._env`). `resolve_cell_env(cond, base_env)` must be a pure function (no mutation of `cond` or `base_env`; calling it twice yields equal `Environment`s).
- **failed_short and reverse-bias dissipation are out of scope** (ngspice hatch / Phase 2). `failed_open` is realised analytically only, via a tiny positive `current_loss` epsilon (the analytic-relevant axis) and a matching `season` epsilon (for ngspice).

---

## Task 1 — Phase 0 spec schemas: `StringSpec`, `SectionSpec`, `PanelSpec`, `ArraySpec`

**Files:**
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/src/powerpy/schemas/panel_circuit.py`
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/tests/test_panel_circuit_schema.py`
- Modify: `C:/Users/Nitrox/Downloads/powerpy/powerpy/src/powerpy/schemas/__init__.py` — after the existing `from powerpy.schemas.circuit import ...` line (line 26) add the `panel_circuit` import; append the four names to `__all__` immediately before the closing `]` (line 54).

**Interfaces:**
- Consumes: nothing (pure structural dataclasses).
- Produces:
  - `StringSpec(id: str, members: tuple[int, ...], series_resistance_ohm: float = 0.0, block_diode_v_drop: float = 0.6, n_block_diodes: int = 1, string_shunt_diode: bool = True)` — `members` are the ordered flat tile indices wired in series. Mirrors `CircuitString` knobs (`schemas/circuit.py:13-37`) but replaces the scalar `n_series` with the explicit `members` list. `__post_init__` raises `ValueError` on: empty `id`, empty `members`, duplicate indices within `members`, negative `series_resistance_ohm`, negative `block_diode_v_drop`, negative `n_block_diodes`.
  - `SectionSpec(id: str, strings: tuple[StringSpec, ...], panel: str = "panel_1", resistance_ohm: float = 0.0)` — mirrors `CircuitSection` (`schemas/circuit.py:40-57`). `__post_init__` raises on empty `id`, empty `strings`, duplicate string ids, negative `resistance_ohm`.
  - `PanelSpec(id: str, sections: tuple[SectionSpec, ...])` — `__post_init__` raises on empty `id`, empty `sections`, duplicate section ids.
  - `ArraySpec(name: str, panels: tuple[PanelSpec, ...])` — `__post_init__` raises on empty `name`, empty `panels`, duplicate panel ids. Adds `all_members() -> list[int]` returning the concatenation of every string's `members` in panel→section→string order.

TDD steps:

- [ ] Write failing test `tests/test_panel_circuit_schema.py`:
```python
import pytest
from powerpy.schemas.panel_circuit import (
    StringSpec, SectionSpec, PanelSpec, ArraySpec,
)


def _string(string_id="s1", members=(0, 1, 2), **kw):
    return StringSpec(id=string_id, members=tuple(members), **kw)


def test_stringspec_defaults_and_validation():
    s = _string()
    assert s.members == (0, 1, 2)
    assert s.block_diode_v_drop == 0.6
    assert s.string_shunt_diode is True
    with pytest.raises(ValueError):
        _string(members=())                       # needs >= 1 member
    with pytest.raises(ValueError):
        _string(members=(0, 0, 1))                # duplicate tile index
    with pytest.raises(ValueError):
        StringSpec(id="", members=(0,))           # id required
    with pytest.raises(ValueError):
        _string(series_resistance_ohm=-0.1)
    with pytest.raises(ValueError):
        _string(block_diode_v_drop=-0.1)          # promised branch, now tested
    with pytest.raises(ValueError):
        _string(n_block_diodes=-1)                # promised branch, now tested


def test_sectionspec_requires_strings_and_unique_ids():
    sec = SectionSpec(id="sec_a", strings=(_string("s1", (0, 1)), _string("s2", (2, 3))))
    assert sec.panel == "panel_1"
    with pytest.raises(ValueError):
        SectionSpec(id="sec_a", strings=())
    with pytest.raises(ValueError):
        SectionSpec(id="sec_a", strings=(_string("s1"), _string("s1")))


def test_panelspec_and_arrayspec_validation_and_all_members():
    pan = PanelSpec(id="panel_1", sections=(
        SectionSpec(id="a", strings=(_string("s1", (0, 1)),)),
        SectionSpec(id="b", strings=(_string("s2", (2, 3)),)),
    ))
    arr = ArraySpec(name="spec", panels=(pan,))
    assert arr.all_members() == [0, 1, 2, 3]
    with pytest.raises(ValueError):
        ArraySpec(name="", panels=(pan,))
    with pytest.raises(ValueError):
        ArraySpec(name="spec", panels=())
    with pytest.raises(ValueError):
        PanelSpec(id="panel_1", sections=(
            SectionSpec(id="a", strings=(_string("s1", (0,)),)),
            SectionSpec(id="a", strings=(_string("s2", (1,)),)),
        ))
```
- [ ] Run it (expect FAIL — module does not exist):
  `PYTHONPATH=src python -m pytest tests/test_panel_circuit_schema.py -v`
  Expected: `ModuleNotFoundError: No module named 'powerpy.schemas.panel_circuit'`.
- [ ] Minimal implementation — create `src/powerpy/schemas/panel_circuit.py`:
```python
"""Position-mapped circuit spec (approach B): tile-index members per string.

Structural twin of :mod:`powerpy.schemas.circuit`, but a string lists the
ORDERED flat tile indices it wires in series (``members``) instead of a scalar
``n_series``.  This makes the cell <-> physical-position mapping explicit so a
per-cell condition (shade/life/failure) can be attached downstream.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StringSpec:
    """One string: ``members`` cells in series, plus per-string options."""
    id: str
    members: tuple[int, ...]
    series_resistance_ohm: float = 0.0
    block_diode_v_drop: float = 0.6
    n_block_diodes: int = 1
    string_shunt_diode: bool = True

    def __post_init__(self):
        if not self.id:
            raise ValueError("StringSpec.id must be non-empty")
        if not self.members:
            raise ValueError("StringSpec %r: needs >= 1 member" % self.id)
        if len(set(self.members)) != len(self.members):
            raise ValueError("StringSpec %r: duplicate tile indices %s"
                             % (self.id, self.members))
        if self.series_resistance_ohm < 0:
            raise ValueError("StringSpec %r: series_resistance_ohm must be >= 0"
                             % self.id)
        if self.block_diode_v_drop < 0:
            raise ValueError("StringSpec %r: block_diode_v_drop must be >= 0"
                             % self.id)
        if self.n_block_diodes < 0:
            raise ValueError("StringSpec %r: n_block_diodes must be >= 0" % self.id)


@dataclass(frozen=True)
class SectionSpec:
    """A parallel group of strings on one panel."""
    id: str
    strings: tuple[StringSpec, ...]
    panel: str = "panel_1"
    resistance_ohm: float = 0.0

    def __post_init__(self):
        if not self.id:
            raise ValueError("SectionSpec.id must be non-empty")
        if not self.strings:
            raise ValueError("SectionSpec %r: needs >= 1 string" % self.id)
        if self.resistance_ohm < 0:
            raise ValueError("SectionSpec %r: resistance_ohm must be >= 0" % self.id)
        ids = [s.id for s in self.strings]
        if len(set(ids)) != len(ids):
            raise ValueError("SectionSpec %r: duplicate string ids %s" % (self.id, ids))


@dataclass(frozen=True)
class PanelSpec:
    """Sections in parallel on one substrate."""
    id: str
    sections: tuple[SectionSpec, ...]

    def __post_init__(self):
        if not self.id:
            raise ValueError("PanelSpec.id must be non-empty")
        if not self.sections:
            raise ValueError("PanelSpec %r: needs >= 1 section" % self.id)
        ids = [s.id for s in self.sections]
        if len(set(ids)) != len(ids):
            raise ValueError("PanelSpec %r: duplicate section ids %s" % (self.id, ids))


@dataclass(frozen=True)
class ArraySpec:
    """The whole array: panels in parallel."""
    name: str
    panels: tuple[PanelSpec, ...]

    def __post_init__(self):
        if not self.name:
            raise ValueError("ArraySpec.name must be non-empty")
        if not self.panels:
            raise ValueError("ArraySpec: needs >= 1 panel")
        ids = [p.id for p in self.panels]
        if len(set(ids)) != len(ids):
            raise ValueError("ArraySpec: duplicate panel ids %s" % ids)

    def all_members(self) -> list[int]:
        """Every string's members concatenated, panel->section->string order."""
        out: list[int] = []
        for p in self.panels:
            for sec in p.sections:
                for st in sec.strings:
                    out.extend(st.members)
        return out
```
  Then extend `src/powerpy/schemas/__init__.py`: after the existing `from powerpy.schemas.circuit import CircuitString, CircuitSection, CircuitLayout` line (line 26) add `from powerpy.schemas.panel_circuit import StringSpec, SectionSpec, PanelSpec, ArraySpec`, and append `"StringSpec", "SectionSpec", "PanelSpec", "ArraySpec",` to `__all__` immediately before the closing `]` (line 54, after the `"CircuitLayout",` entry on line 53).
- [ ] Run it (expect PASS):
  `PYTHONPATH=src python -m pytest tests/test_panel_circuit_schema.py -v`
- [ ] Commit:
  `git checkout -b approach-b-phase0-1 && git add src/powerpy/schemas/panel_circuit.py src/powerpy/schemas/__init__.py tests/test_panel_circuit_schema.py && git commit -m "feat(spec): add position-mapped ArraySpec/PanelSpec/SectionSpec/StringSpec (approach B Phase 0)"`

---

## Task 2 — `validate_bijection`: total, injective, type-correct over all tiles

**Files:**
- Modify: `C:/Users/Nitrox/Downloads/powerpy/powerpy/src/powerpy/schemas/panel_circuit.py` (append module-level function after `ArraySpec`)
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/tests/test_validate_bijection.py`

**Interfaces:**
- Consumes: `ArraySpec` (Task 1); `n_tiles: int` (the total tile count the spec must cover bijectively — e.g. `PanelLayout.n_tiles`, layout.py:70-72).
- Produces: `validate_bijection(spec: ArraySpec, n_tiles: int) -> None` — raises `ValueError` unless the multiset `spec.all_members()` is a permutation of `range(n_tiles)` (per the user decision: every tile IS a cell, bijection total over all tiles). Raises on: any index `< 0` or `>= n_tiles` (type/range-correct), any duplicate across strings (injective), or any missing index in `range(n_tiles)` (total). Returns `None` on success.

TDD steps:

- [ ] Write failing test `tests/test_validate_bijection.py`:
```python
import pytest
from powerpy.schemas.panel_circuit import (
    StringSpec, SectionSpec, PanelSpec, ArraySpec, validate_bijection,
)


def _spec(members_per_string):
    strings = tuple(
        StringSpec(id="s%d" % k, members=tuple(m))
        for k, m in enumerate(members_per_string)
    )
    sec = SectionSpec(id="sec", strings=strings)
    return ArraySpec(name="x", panels=(PanelSpec(id="panel_1", sections=(sec,)),))


def test_bijection_ok_for_full_cover():
    validate_bijection(_spec([[0, 1], [2, 3]]), n_tiles=4)  # no raise


def test_bijection_rejects_missing_tile():
    with pytest.raises(ValueError):
        validate_bijection(_spec([[0, 1], [2]]), n_tiles=4)   # 3 missing


def test_bijection_rejects_out_of_range():
    with pytest.raises(ValueError):
        validate_bijection(_spec([[0, 1], [2, 9]]), n_tiles=4)  # 9 >= 4


def test_bijection_rejects_duplicate_across_strings():
    with pytest.raises(ValueError):
        validate_bijection(_spec([[0, 1], [1, 2, 3]]), n_tiles=4)  # 1 twice
```
- [ ] Run it (expect FAIL — `validate_bijection` not defined):
  `PYTHONPATH=src python -m pytest tests/test_validate_bijection.py -v`
  Expected: `ImportError: cannot import name 'validate_bijection'`.
- [ ] Minimal implementation — append to `src/powerpy/schemas/panel_circuit.py`:
```python
def validate_bijection(spec: ArraySpec, n_tiles: int) -> None:
    """Assert the spec's tile members are a bijection onto ``range(n_tiles)``.

    Every tile is a cell and must be wired exactly once: the concatenation of
    all strings' ``members`` must be a permutation of ``0..n_tiles-1``.
    """
    members = spec.all_members()
    # injective + range-correct
    seen: set[int] = set()
    for idx in members:
        if not isinstance(idx, int):
            raise ValueError("validate_bijection: non-int tile index %r" % (idx,))
        if idx < 0 or idx >= n_tiles:
            raise ValueError(
                "validate_bijection: tile index %d out of range [0, %d)"
                % (idx, n_tiles))
        if idx in seen:
            raise ValueError("validate_bijection: tile index %d wired twice" % idx)
        seen.add(idx)
    # total
    missing = set(range(n_tiles)) - seen
    if missing:
        raise ValueError(
            "validate_bijection: tiles not wired to any string: %s"
            % sorted(missing))
```
- [ ] Run it (expect PASS):
  `PYTHONPATH=src python -m pytest tests/test_validate_bijection.py -v`
- [ ] Run the schema suite to confirm the append did not break Task 1 (expect PASS):
  `PYTHONPATH=src python -m pytest tests/test_panel_circuit_schema.py tests/test_validate_bijection.py -q`
- [ ] Run the full suite to confirm no regressions (expect PASS):
  `PYTHONPATH=src python -m pytest -q`
- [ ] Commit:
  `git add src/powerpy/schemas/panel_circuit.py tests/test_validate_bijection.py && git commit -m "feat(spec): validate_bijection (total/injective/range-correct over all tiles)"`

---

## Task 3 — `build_array_from_spec` using `StringModel.from_cells`

**Files:**
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/src/powerpy/simulation/spec_build.py`
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/tests/test_spec_build.py`

**Interfaces:**
- Consumes: `CellParameters` (`schemas/cell.py:69`), `ArraySpec` (Task 1); `CellModel(params, iv_engine=...)` (`cell_level.py:130`), `StringModel.from_cells(cells, **kwargs)` (`string_level.py:57-59`), `SectionModel.from_strings(strings, **kwargs)` (`section_level.py:41-44`), `PanelModel.from_sections(sections, name=...)` (`panel_level.py:31-35`), `ArrayModel.from_panels(panels, name=...)` (`array_level.py:34-37`).
- Produces: `build_array_from_spec(cell_params: CellParameters, spec: ArraySpec, *, iv_engine: str = "analytic", string_shunt_vf: float | None = None) -> ArrayModel`. For each `StringSpec`, builds **one distinct `CellModel(cell_params, iv_engine=iv_engine)` per index in `members`** (NOT `from_single_cell`), passing the same per-string knobs as `build_array_from_circuit` (`circuit_build.py:36-42`): `block_diode_v_drop`, `n_block_diodes`, `series_resistance_ohm`, `shunt_diode_v_forward = string_shunt_vf if st.string_shunt_diode else None`, `name="<sec.id>.<st.id>"`. Sections via `SectionModel.from_strings(..., section_resistance_ohm=sec.resistance_ohm, name=sec.id)`. Panels via `PanelModel.from_sections(secs, name=panel.id)` per `PanelSpec`. Returns `ArrayModel.from_panels(panel_models, name=spec.name)`.

TDD steps:

- [ ] Write failing test `tests/test_spec_build.py`:
```python
from pathlib import Path

import numpy as np
import pytest

from powerpy.loader.report import load_report_data
from powerpy.schemas.panel_circuit import StringSpec, SectionSpec, PanelSpec, ArraySpec
from powerpy.simulation.spec_build import build_array_from_spec
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def _cell():
    return load_report_data(PARAMS, DATA).cell


def _spec():
    # two parallel strings of 3 cells each -> tiles 0..5
    s1 = StringSpec(id="s1", members=(0, 1, 2))
    s2 = StringSpec(id="s2", members=(3, 4, 5))
    sec = SectionSpec(id="sec_a", strings=(s1, s2))
    return ArraySpec(name="spec", panels=(PanelSpec(id="panel_1", sections=(sec,)),))


def test_spec_build_makes_distinct_cells_per_member():
    arr = build_array_from_spec(_cell(), _spec(), iv_engine="analytic")
    assert len(arr.panels) == 1
    secs = list(arr.iter_sections())
    assert len(secs) == 1
    s1, s2 = secs[0].strings
    assert len(s1.cells) == 3 and len(s2.cells) == 3
    # each member is its OWN CellModel object (no aliasing) -> distinct ids
    objs = [id(c) for c in s1.cells] + [id(c) for c in s2.cells]
    assert len(set(objs)) == 6


def test_spec_build_curve_is_finite_with_positive_peak():
    arr = build_array_from_spec(_cell(), _spec(), iv_engine="analytic")
    arr.apply(Environment(temperature_c=28.0))
    v, i = arr.iv_curve()
    p = v * i
    assert np.all(np.isfinite(v)) and np.all(np.isfinite(i))
    assert float(p.max()) > 0.0
```
- [ ] Run it (expect FAIL — module does not exist):
  `PYTHONPATH=src python -m pytest tests/test_spec_build.py -v`
  Expected: `ModuleNotFoundError: No module named 'powerpy.simulation.spec_build'`.
- [ ] Minimal implementation — create `src/powerpy/simulation/spec_build.py`:
```python
"""Assemble the simulation tree from a position-mapped ArraySpec (approach B).

One distinct :class:`CellModel` is created per tile index in each string's
``members`` (via :meth:`StringModel.from_cells`), so a per-cell condition can be
attached to each leaf without aliasing.  All curve-combination, environment and
shunt-diode logic is the existing tree's, unchanged.
"""
from __future__ import annotations

from powerpy.schemas.cell import CellParameters
from powerpy.schemas.panel_circuit import ArraySpec
from powerpy.simulation.array_level import ArrayModel
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.panel_level import PanelModel
from powerpy.simulation.section_level import SectionModel
from powerpy.simulation.string_level import StringModel


def build_array_from_spec(
    cell_params: CellParameters,
    spec: ArraySpec,
    *,
    iv_engine: str = "analytic",
    string_shunt_vf: float | None = None,
) -> ArrayModel:
    """Build an :class:`ArrayModel` from an :class:`ArraySpec`.

    Each tile index in a string's ``members`` becomes its own ``CellModel``.
    ``string_shunt_vf`` is the forward drop of the string shunt diode; it is
    applied to strings whose ``string_shunt_diode`` flag is True.
    """
    panel_models = []
    for pan in spec.panels:
        sections = []
        for sec in pan.sections:
            strings = []
            for st in sec.strings:
                vf = string_shunt_vf if st.string_shunt_diode else None
                cells = [CellModel(cell_params, iv_engine=iv_engine)
                         for _ in st.members]
                strings.append(StringModel.from_cells(
                    cells,
                    block_diode_v_drop=st.block_diode_v_drop,
                    n_block_diodes=st.n_block_diodes,
                    series_resistance_ohm=st.series_resistance_ohm,
                    shunt_diode_v_forward=vf,
                    name="%s.%s" % (sec.id, st.id)))
            sections.append(SectionModel.from_strings(
                strings, section_resistance_ohm=sec.resistance_ohm, name=sec.id))
        panel_models.append(PanelModel.from_sections(sections, name=pan.id))
    return ArrayModel.from_panels(panel_models, name=spec.name)
```
- [ ] Run it (expect PASS):
  `PYTHONPATH=src python -m pytest tests/test_spec_build.py -v`
- [ ] Commit:
  `git add src/powerpy/simulation/spec_build.py tests/test_spec_build.py && git commit -m "feat(spec): build_array_from_spec via StringModel.from_cells (distinct cell per tile)"`

---

## Task 4 — `adapt_grid` from `PanelLayout` + Phase-0 structural-equivalence check vs a hand-built tree

**Files:**
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/src/powerpy/simulation/spec_adapt.py`
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/tests/test_spec_adapt_grid.py`

**Interfaces:**
- Consumes: `PanelLayout` (`config/layout.py:53`) — uses `flat_keys()` (layout.py:81-82), `n_tiles` (layout.py:70-72), `palette` to read each tile's `TileType.string` (layout.py:44), and `name` (layout.py:59). Per the user decision (every tile IS a cell) the adapter treats all tiles as cells and groups by the `string` tag; tiles sharing a `string` key are wired in series in `flat_keys()` (row-major) order.
- Produces:
  - `adapt_grid(layout: PanelLayout, *, panel_id: str = "panel_1", section_id: str = "sec_grid") -> ArraySpec`. Builds one `StringSpec` per distinct non-`None` `string` tag (members = the row-major flat indices carrying that tag, in encounter order). **Fail-loud on untagged tiles:** if any tile's `TileType.string is None`, raise `ValueError` — under the user decision "every tile IS a cell wired into a string", an untagged cell with no string is a spec error, not something to auto-singletonize. (This avoids silently inventing a parallel-of-singletons topology that may not match physical intent.) All strings go into one `SectionSpec`, one `PanelSpec`, one `ArraySpec(name=layout.name or "grid")`. Result satisfies `validate_bijection(spec, layout.n_tiles)` for a fully-tagged grid.

  NOTE — what the regression proves and what it does NOT: there is NO pre-existing electrical builder that turns a `PanelLayout` grid into an `ArrayModel` (the grid feeds the thermal solver, not the electrical tree). So the Phase-0 gate here is a *structural-equivalence* check: `build_array_from_spec(adapt_grid(layout))` must equal a hand-built `from_cells` tree of the same shape (same strings × cells), bit-for-bit. This proves the adapter+builder produce the intended topology — it is NOT a behaviour-preservation check against a live grid IV (none exists). A `panel_from_topology` layout (layout.py:193) tags every tile `string='B{b}S{s}'`, so `adapt_grid` recovers exactly those series strings.

TDD steps:

- [ ] Write failing test `tests/test_spec_adapt_grid.py` (package import for the spec modules and the layout helper, which are clean):
```python
from pathlib import Path

import numpy as np
import pytest

from powerpy.config.layout import panel_from_topology
from powerpy.loader.report import load_report_data
from powerpy.schemas.panel_circuit import validate_bijection
from powerpy.simulation.spec_adapt import adapt_grid
from powerpy.simulation.spec_build import build_array_from_spec
from powerpy.simulation.string_level import StringModel
from powerpy.simulation.section_level import SectionModel
from powerpy.simulation.panel_level import PanelModel
from powerpy.simulation.array_level import ArrayModel
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def _cell():
    return load_report_data(PARAMS, DATA).cell


def test_adapt_grid_is_a_bijection():
    lay = panel_from_topology(n_blocks=1, n_parallel=2, n_series=3)
    spec = adapt_grid(lay)
    validate_bijection(spec, lay.n_tiles)   # no raise


def test_adapt_grid_matches_hand_built_tree_structurally():
    """Phase-0 STRUCTURAL gate: spec-built grid IV == an explicitly hand-built
    from_cells tree of the SAME shape, bit-for-bit.  (No live electrical grid
    builder exists to regress against; this proves topology, not behaviour
    preservation.)"""
    cell = _cell()
    lay = panel_from_topology(n_blocks=1, n_parallel=2, n_series=3)
    env = Environment(temperature_c=28.0)

    # spec path
    spec = adapt_grid(lay)
    arr_spec = build_array_from_spec(cell, spec, iv_engine="analytic")
    arr_spec.apply(env)
    v_spec, i_spec = arr_spec.iv_curve()

    # reference: SAME shape, built directly with from_cells (2 strings x 3 cells)
    strings = []
    for s in range(2):
        cells = [CellModel(cell, iv_engine="analytic") for _ in range(3)]
        strings.append(StringModel.from_cells(cells, name="ref.s%d" % s))
    sec = SectionModel.from_strings(strings, name="sec_grid")
    pan = PanelModel.from_sections([sec], name="panel_1")
    arr_ref = ArrayModel.from_panels([pan], name="grid")
    arr_ref.apply(env)
    v_ref, i_ref = arr_ref.iv_curve()

    assert np.allclose(v_spec, v_ref, rtol=0, atol=1e-9)
    assert np.allclose(i_spec, i_ref, rtol=0, atol=1e-9)


def test_adapt_grid_raises_on_untagged_tile():
    lay = panel_from_topology(n_blocks=1, n_parallel=2, n_series=3)
    # blank one tile's string tag -> adapter must fail loud (every tile is a
    # cell that MUST belong to a string).
    key = lay.flat_keys()[0]
    import dataclasses
    bad_tile = dataclasses.replace(lay.palette[key], string=None)
    bad_palette = dict(lay.palette)
    bad_palette[key] = bad_tile
    bad_lay = dataclasses.replace(lay, palette=bad_palette)
    with pytest.raises(ValueError):
        adapt_grid(bad_lay)
```
- [ ] Run it (expect FAIL — `spec_adapt` does not exist):
  `PYTHONPATH=src python -m pytest tests/test_spec_adapt_grid.py -v`
  Expected: `ModuleNotFoundError: No module named 'powerpy.simulation.spec_adapt'`.
  (If `PanelLayout`/`TileType` turn out not to be frozen dataclasses, replace the `dataclasses.replace` construction in `test_adapt_grid_raises_on_untagged_tile` with a directly-constructed minimal `PanelLayout` carrying one `string=None` tile — the assertion that `adapt_grid` raises is the load-bearing part.)
- [ ] Minimal implementation — create `src/powerpy/simulation/spec_adapt.py`:
```python
"""Adapters: build an ArraySpec from the existing inputs (grid / report / circuit).

Phase 0 keeps behaviour identical -- the section/circuit adapters re-express
today's inputs as a position-mapped :class:`ArraySpec` so the spec-built tree
reproduces the LIVE builders' analytic IV.  The grid adapter has no live
electrical builder to regress against (the grid feeds the thermal solver), so
its gate is structural-equivalence only.
"""
from __future__ import annotations

from powerpy.config.layout import PanelLayout
from powerpy.schemas.panel_circuit import (
    StringSpec, SectionSpec, PanelSpec, ArraySpec,
)


def adapt_grid(layout: PanelLayout, *, panel_id: str = "panel_1",
               section_id: str = "sec_grid") -> ArraySpec:
    """Express a fully-tagged :class:`PanelLayout` grid as an :class:`ArraySpec`.

    Tiles sharing a ``string`` tag are wired in series in row-major
    (``flat_keys``) order.  Every tile is a cell that MUST belong to a string:
    an untagged tile (``TileType.string is None``) raises ``ValueError`` rather
    than being auto-grouped into a singleton (which could silently invent an
    unintended parallel-of-singletons topology).
    """
    keys = layout.flat_keys()
    palette = layout.palette
    groups: dict[str, list[int]] = {}
    order: list[str] = []
    for idx, key in enumerate(keys):
        tag = palette[key].string
        if tag is None:
            raise ValueError(
                "adapt_grid: tile %d (key %r) has no string tag; every tile "
                "must be wired into a string" % (idx, key))
        if tag not in groups:
            groups[tag] = []
            order.append(tag)
        groups[tag].append(idx)

    strings = tuple(
        StringSpec(id=str(gid), members=tuple(groups[gid])) for gid in order
    )
    section = SectionSpec(id=section_id, strings=strings, panel=panel_id)
    panel = PanelSpec(id=panel_id, sections=(section,))
    return ArraySpec(name=layout.name or "grid", panels=(panel,))
```
- [ ] Run it (expect PASS):
  `PYTHONPATH=src python -m pytest tests/test_spec_adapt_grid.py -v`
- [ ] Commit:
  `git add src/powerpy/simulation/spec_adapt.py tests/test_spec_adapt_grid.py && git commit -m "feat(spec): adapt_grid from PanelLayout (fail-loud on untagged) + structural-equivalence gate"`

---

## Task 5 — `adapt_sections` + `adapt_circuit` + analytic-IV regression vs the LIVE builders `build_from_report`/`build_array_from_circuit`

**Files:**
- Modify: `C:/Users/Nitrox/Downloads/powerpy/powerpy/src/powerpy/simulation/spec_adapt.py` (append `adapt_sections` and `adapt_circuit`)
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/tests/test_spec_adapt_sections.py`

**Interfaces:**
- Consumes:
  - `ArrayLayout` (`schemas/layout.py:63`) via `physical_sections` (layout.py:68) → each `PhysicalSection` (layout.py:48) carries `section_type` (`SectionType`, layout.py:5: `n_strings_parallel`, `n_sca_series_per_string`), `instance_id`, `panel_id`, `resistance_ohm`. This mirrors `build_from_report` (`array_level.py:79-95`).
  - `CircuitLayout` (`schemas/circuit.py:60`) via `sections` → `CircuitSection.strings` → `CircuitString.{id,n_series,...}`. Mirrors `build_array_from_circuit` (`circuit_build.py:32-45`).
- Produces:
  - `adapt_sections(layout: ArrayLayout, *, string_series_resistance_ohm: float = 0.0, section_resistance_ohm: float = 0.0) -> ArraySpec`. Assigns flat tile indices by a running counter in `physical_sections` order; for each physical section emits `n_strings_parallel` `StringSpec`s each of `n_sca_series_per_string` consecutive indices, `series_resistance_ohm=string_series_resistance_ohm`, ids `"<instance_id>.string<k>"`; one `SectionSpec(id=instance_id, ..., panel=panel_id, resistance_ohm=phys.resistance_ohm or section_resistance_ohm)` per physical section, grouped into `PanelSpec` by `panel_id`.
  - `adapt_circuit(circuit: CircuitLayout) -> ArraySpec`. Running counter assigns each `CircuitString`'s `n_series` consecutive indices; carries `series_resistance_ohm`, `block_diode_v_drop`, `n_block_diodes`, `string_shunt_diode` straight across; `SectionSpec.panel = sec.panel`; `ArraySpec.name = circuit.name`.

  Note: `build_from_report` uses `from_single_cell` with `deepcopy`, which produces independent cells whose analytic per-cell curves are identical to fresh `CellModel(params)` instances under the same env — so `build_array_from_spec(adapt_circuit(circuit))` reproduces `build_array_from_circuit`'s IV exactly. (The array *name* differs — the live `build_array_from_circuit` defaults to `"array"` while the spec path passes `name=circuit.name` — but the name does not enter the IV arrays, so the `np.allclose` gate still passes.) The regression gate proves it.

TDD steps:

- [ ] Write failing test `tests/test_spec_adapt_sections.py`:
```python
from pathlib import Path

import numpy as np
import pytest

from powerpy.loader.report import load_report_data
from powerpy.loader.circuit import load_circuit
from powerpy.schemas.panel_circuit import validate_bijection
from powerpy.simulation.spec_adapt import adapt_sections, adapt_circuit
from powerpy.simulation.spec_build import build_array_from_spec
from powerpy.simulation.array_level import build_from_report
from powerpy.simulation.circuit_build import build_array_from_circuit
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
SAMPLE = DATA / "circuits" / "msro_nominal.json"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def _report():
    return load_report_data(PARAMS, DATA)


def test_adapt_sections_is_a_bijection_over_all_scas():
    report = _report()
    spec = adapt_sections(report.array_layout)
    validate_bijection(spec, report.array_layout.n_sca_total)


def test_adapt_sections_reproduces_build_from_report_iv():
    report = _report()
    env = Environment(temperature_c=28.0)

    string_shunt_vf = (report.cell.string_diode.v_forward
                       if getattr(report.cell, "string_diode", None) else None)
    spec = adapt_sections(report.array_layout)
    arr_spec = build_array_from_spec(report.cell, spec, iv_engine="analytic",
                                     string_shunt_vf=string_shunt_vf)
    arr_spec.apply(env)
    v_spec, i_spec = arr_spec.iv_curve()

    arr_ref = build_from_report(report, iv_engine="analytic")
    arr_ref.apply(env)
    v_ref, i_ref = arr_ref.iv_curve()

    assert np.allclose(v_spec, v_ref, rtol=0, atol=1e-9)
    assert np.allclose(i_spec, i_ref, rtol=0, atol=1e-9)


def test_adapt_circuit_reproduces_build_array_from_circuit_iv():
    report = _report()
    circuit = load_circuit(SAMPLE)
    env = Environment(temperature_c=28.0)
    string_shunt_vf = (report.cell.string_diode.v_forward
                       if getattr(report.cell, "string_diode", None) else None)

    spec = adapt_circuit(circuit)
    arr_spec = build_array_from_spec(report.cell, spec, iv_engine="analytic",
                                     string_shunt_vf=string_shunt_vf)
    arr_spec.apply(env)
    v_spec, i_spec = arr_spec.iv_curve()

    arr_ref = build_array_from_circuit(report.cell, circuit, iv_engine="analytic",
                                       string_shunt_vf=string_shunt_vf)
    arr_ref.apply(env)
    v_ref, i_ref = arr_ref.iv_curve()

    assert np.allclose(v_spec, v_ref, rtol=0, atol=1e-9)
    assert np.allclose(i_spec, i_ref, rtol=0, atol=1e-9)
```
- [ ] Run it (expect FAIL — `adapt_sections`/`adapt_circuit` not defined):
  `PYTHONPATH=src python -m pytest tests/test_spec_adapt_sections.py -v`
  Expected: `ImportError: cannot import name 'adapt_sections'`.
- [ ] Minimal implementation — append to `src/powerpy/simulation/spec_adapt.py`:
```python
from powerpy.schemas.layout import ArrayLayout
from powerpy.schemas.circuit import CircuitLayout


def adapt_sections(layout: ArrayLayout, *,
                   string_series_resistance_ohm: float = 0.0,
                   section_resistance_ohm: float = 0.0) -> ArraySpec:
    """Express the report's :class:`ArrayLayout` as an :class:`ArraySpec`.

    Mirrors :func:`powerpy.simulation.array_level.build_from_report`: each
    physical section expands to ``n_strings_parallel`` strings of
    ``n_sca_series_per_string`` consecutive tile indices.
    """
    next_idx = 0
    panels: dict[str, list[SectionSpec]] = {}
    panel_order: list[str] = []
    for phys in layout.physical_sections:
        st = phys.section_type
        strings = []
        for k in range(st.n_strings_parallel):
            members = tuple(range(next_idx, next_idx + st.n_sca_series_per_string))
            next_idx += st.n_sca_series_per_string
            strings.append(StringSpec(
                id="%s.string%d" % (phys.instance_id, k),
                members=members,
                series_resistance_ohm=string_series_resistance_ohm))
        r_sec = phys.resistance_ohm or section_resistance_ohm
        section = SectionSpec(id=phys.instance_id, strings=tuple(strings),
                              panel=phys.panel_id, resistance_ohm=r_sec)
        if phys.panel_id not in panels:
            panels[phys.panel_id] = []
            panel_order.append(phys.panel_id)
        panels[phys.panel_id].append(section)
    panel_specs = tuple(
        PanelSpec(id=pid, sections=tuple(panels[pid])) for pid in panel_order
    )
    return ArraySpec(name="array_layout", panels=panel_specs)


def adapt_circuit(circuit: CircuitLayout) -> ArraySpec:
    """Express a free-form :class:`CircuitLayout` as an :class:`ArraySpec`.

    Mirrors :func:`powerpy.simulation.circuit_build.build_array_from_circuit`:
    each string's ``n_series`` becomes ``n_series`` consecutive tile indices,
    with the per-string electrical knobs carried straight across.
    """
    next_idx = 0
    panels: dict[str, list[SectionSpec]] = {}
    panel_order: list[str] = []
    for sec in circuit.sections:
        strings = []
        for st in sec.strings:
            members = tuple(range(next_idx, next_idx + st.n_series))
            next_idx += st.n_series
            strings.append(StringSpec(
                id=st.id, members=members,
                series_resistance_ohm=st.series_resistance_ohm,
                block_diode_v_drop=st.block_diode_v_drop,
                n_block_diodes=st.n_block_diodes,
                string_shunt_diode=st.string_shunt_diode))
        section = SectionSpec(id=sec.id, strings=tuple(strings),
                              panel=sec.panel, resistance_ohm=sec.resistance_ohm)
        if sec.panel not in panels:
            panels[sec.panel] = []
            panel_order.append(sec.panel)
        panels[sec.panel].append(section)
    panel_specs = tuple(
        PanelSpec(id=pid, sections=tuple(panels[pid])) for pid in panel_order
    )
    return ArraySpec(name=circuit.name, panels=panel_specs)
```
- [ ] Run it (expect PASS):
  `PYTHONPATH=src python -m pytest tests/test_spec_adapt_sections.py -v`
- [ ] Run the full suite to confirm zero behaviour change (expect PASS, no regressions):
  `PYTHONPATH=src python -m pytest -q`
- [ ] Commit:
  `git add src/powerpy/simulation/spec_adapt.py tests/test_spec_adapt_sections.py && git commit -m "feat(spec): adapt_sections + adapt_circuit with analytic-IV regression gate (Phase 0 complete)"`

---

## Task 6 — `CellCondition` + pure idempotent `resolve_cell_env` (consumes EVERY field)

**Files:**
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/src/powerpy/simulation/cell_condition.py`
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/tests/test_cell_condition.py`

**Interfaces:**
- Consumes: `Environment` (`environment.py:14`) — reads `season` (L43), `current_loss` (L47) and `voltage_loss` as the base; `dataclasses.replace` to produce a new frozen instance.
- Produces:
  - `@dataclass(frozen=True) CellCondition` with all-defaulted fields: `state: str = "healthy"` (`"healthy"` | `"failed_open"`), `shade: float = 1.0` (transmittance 0..1, 1.0 = unshaded), `life: float = 1.0` (mechanical-chipping current derate 0..1, 1.0 = full life), `incidence: float = 1.0` (cosine factor from blanket bow 0..1, 1.0 = normal), `cell_type: str | None = None`, `imp_factor: float = 1.0` (per-cell manufacturing current multiplier), `pmax_factor: float = 1.0` (per-cell manufacturing Pmax multiplier, split across current and voltage axes), `failed_open_epsilon: float = 1e-6` (tiny current/season floor for a failed-open cell so its child curve stays well-formed in `combine_series`). `__post_init__` raises `ValueError` on unknown `state`, or `shade`/`incidence`/`life` outside `[0, 1]`, or non-positive `imp_factor`/`pmax_factor`.
  - `resolve_cell_env(cond: CellCondition, base_env: Environment) -> Environment` — **pure**. For a healthy cell:
    - `current_loss = base_env.current_loss * life * shade * incidence * imp_factor * sqrt(pmax_factor)`
    - `voltage_loss = base_env.voltage_loss * sqrt(pmax_factor)`
    - `season = base_env.season * shade * incidence` (carried for the ngspice path; the analytic `operating_points` ignores `season`).

    The `pmax_factor` is split as `sqrt` on each axis so that a manufacturing Pmax multiplier `m` scales the cell's peak power by ≈`m` (current axis × voltage axis = `sqrt(m)·sqrt(m) = m`), while `imp_factor` is a pure current-axis (Isc/Imp) multiplier. **Both factors therefore have a real, asserted effect on `operating_points`/Pmp** — they are not wired-but-inert.

    For `state == "failed_open"` the cell is realised as a near-dead-but-well-formed cell:
    - `current_loss = base_env.current_loss * failed_open_epsilon` — this is the LOAD-BEARING analytic knob: `operating_points` scales `isc/imp` by `gain_i = f_temp_i*f_rad_i*env.current_loss` (`cell_level.py:163-167`) and does NOT read `season`, so the tiny Isc comes from `current_loss`, not `season`.
    - `season = base_env.season * failed_open_epsilon` — set ONLY so the ngspice path (which DOES read `season` at `cell_level.py:200`) also sees the near-dead cell.
    - `voltage_loss` is left untouched, so the cell keeps full Voc and does not collapse the parallel `combine_parallel` (which caps at smallest child Voc).

    Never mutates `cond` or `base_env`.

  Rationale (grounded in `cell_level.py:154-170`): the analytic path scales `isc/imp` by `gain_i = f_temp_i*f_rad_i*env.current_loss` and `voc/vmp` by `gain_v = f_temp_v*f_rad_v*env.voltage_loss` — `env.season` is **not** read by `operating_points`. So every current-axis effect (shade·incidence·life·imp_factor and the current half of pmax_factor) must ride `current_loss`, and the voltage half of pmax_factor must ride `voltage_loss`. `season` is still set so the ngspice path sees shade·incidence (healthy) or the failure floor (failed_open).

TDD steps:

- [ ] Write failing test `tests/test_cell_condition.py`:
```python
import dataclasses
import math

import pytest

from powerpy.simulation.cell_condition import CellCondition, resolve_cell_env
from powerpy.simulation.environment import Environment


def test_condition_defaults_are_a_noop():
    cond = CellCondition()
    base = Environment(temperature_c=28.0, season=1.0, current_loss=1.0)
    out = resolve_cell_env(cond, base)
    assert out.season == 1.0
    assert out.current_loss == 1.0
    assert out.voltage_loss == base.voltage_loss
    assert out.temperature_c == 28.0   # untouched fields preserved


def test_condition_validation():
    with pytest.raises(ValueError):
        CellCondition(state="failed_short")    # not in scope / unknown
    with pytest.raises(ValueError):
        CellCondition(shade=1.5)
    with pytest.raises(ValueError):
        CellCondition(imp_factor=0.0)
    with pytest.raises(ValueError):
        CellCondition(pmax_factor=0.0)


def test_shade_life_incidence_lower_current_loss():
    cond = CellCondition(shade=0.5, life=0.8, incidence=0.9)
    base = Environment(season=1.0, current_loss=1.0)
    out = resolve_cell_env(cond, base)
    assert out.current_loss == pytest.approx(1.0 * 0.8 * 0.5 * 0.9)
    assert out.season == pytest.approx(1.0 * 0.5 * 0.9)


def test_imp_factor_scales_current_axis_only():
    cond = CellCondition(imp_factor=0.95)
    base = Environment(season=1.0, current_loss=1.0, voltage_loss=1.0)
    out = resolve_cell_env(cond, base)
    assert out.current_loss == pytest.approx(0.95)
    assert out.voltage_loss == pytest.approx(1.0)   # imp is current-axis only


def test_pmax_factor_splits_across_both_axes():
    cond = CellCondition(pmax_factor=0.81)
    base = Environment(season=1.0, current_loss=1.0, voltage_loss=1.0)
    out = resolve_cell_env(cond, base)
    assert out.current_loss == pytest.approx(math.sqrt(0.81))   # 0.9
    assert out.voltage_loss == pytest.approx(math.sqrt(0.81))   # 0.9
    # net power scaling ~= 0.9 * 0.9 = 0.81 (the requested Pmax multiplier)


def test_failed_open_uses_tiny_current_loss_and_season_not_zero():
    cond = CellCondition(state="failed_open")
    base = Environment(season=1.0, current_loss=1.0)
    out = resolve_cell_env(cond, base)
    # season floor (for ngspice)
    assert 0.0 < out.season <= cond.failed_open_epsilon
    # LOAD-BEARING analytic axis: current_loss must also be the tiny floor
    assert out.current_loss == pytest.approx(base.current_loss * cond.failed_open_epsilon)


def test_resolve_is_pure_and_idempotent():
    cond = CellCondition(shade=0.5, life=0.7)
    base = Environment(season=1.0, current_loss=1.0)
    base_snapshot = dataclasses.asdict(base)
    cond_snapshot = dataclasses.asdict(cond)
    out1 = resolve_cell_env(cond, base)
    out2 = resolve_cell_env(cond, base)
    assert out1 == out2                                  # deterministic
    assert dataclasses.asdict(base) == base_snapshot     # base untouched
    assert dataclasses.asdict(cond) == cond_snapshot     # cond untouched
```
- [ ] Run it (expect FAIL — module does not exist):
  `PYTHONPATH=src python -m pytest tests/test_cell_condition.py -v`
  Expected: `ModuleNotFoundError: No module named 'powerpy.simulation.cell_condition'`.
- [ ] Minimal implementation — create `src/powerpy/simulation/cell_condition.py`:
```python
"""Per-cell condition (approach B, Phase 1) and its pure env resolver.

A :class:`CellCondition` is a frozen, fully-defaulted description of one cell's
state.  :func:`resolve_cell_env` folds EVERY field onto a base
:class:`Environment` (no field is wired-but-inert):

  * shade x incidence x life x imp_factor x sqrt(pmax_factor) ride the CURRENT
    axis -- the only current knob the analytic ``operating_points`` reads is
    ``current_loss`` (cell_level.py:163, which never reads ``season``).
  * sqrt(pmax_factor) also rides the VOLTAGE axis (``voltage_loss``) so a Pmax
    multiplier ``m`` scales the cell's peak power by ~m (sqrt(m)*sqrt(m)).
  * shade x incidence is ALSO written to ``season`` for the ngspice path.
  * ``failed_open`` is realised as a near-dead but WELL-FORMED cell.  The
    LOAD-BEARING analytic effect is ``current_loss *= failed_open_epsilon``
    (tiny Isc); ``season *= failed_open_epsilon`` is set only for the ngspice
    path; ``voltage_loss`` is untouched so full Voc keeps the parallel
    ``combine_parallel`` (caps at smallest child Voc) from collapsing.  This is
    why it isolates only the affected series string in ``combine_series`` (caps
    at smallest child Isc) instead of killing the section.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

from powerpy.simulation.environment import Environment

_VALID_STATES = ("healthy", "failed_open")


@dataclass(frozen=True)
class CellCondition:
    state: str = "healthy"
    shade: float = 1.0           # transmittance [0,1]; 1.0 = unshaded
    life: float = 1.0            # chipping current derate [0,1]; 1.0 = full
    incidence: float = 1.0       # cosine factor [0,1]; 1.0 = normal
    cell_type: str | None = None
    imp_factor: float = 1.0      # per-cell manufacturing current multiplier
    pmax_factor: float = 1.0     # per-cell manufacturing Pmax multiplier
    failed_open_epsilon: float = 1e-6  # current/season floor for a failed cell

    def __post_init__(self):
        if self.state not in _VALID_STATES:
            raise ValueError("CellCondition.state must be one of %s, got %r"
                             % (_VALID_STATES, self.state))
        for name in ("shade", "life", "incidence"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise ValueError("CellCondition.%s must be in [0, 1], got %r"
                                 % (name, v))
        for name in ("imp_factor", "pmax_factor"):
            if getattr(self, name) <= 0:
                raise ValueError("CellCondition.%s must be > 0, got %r"
                                 % (name, getattr(self, name)))


def resolve_cell_env(cond: CellCondition, base_env: Environment) -> Environment:
    """Pure: fold ``cond`` onto ``base_env`` -> a new Environment (no mutation).

    Consumes EVERY CellCondition field so none is produced-but-unread.
    """
    if cond.state == "failed_open":
        # LOAD-BEARING for the analytic engine: tiny Isc comes from current_loss
        # (operating_points ignores season).  season mirrors it for ngspice.
        season = base_env.season * cond.failed_open_epsilon
        current_loss = base_env.current_loss * cond.failed_open_epsilon
        voltage_loss = base_env.voltage_loss     # keep full Voc -> isolates string
        return dataclasses.replace(
            base_env, season=season,
            current_loss=current_loss, voltage_loss=voltage_loss)

    pmax_axis = math.sqrt(cond.pmax_factor)
    current_loss = (base_env.current_loss
                    * cond.life * cond.shade * cond.incidence
                    * cond.imp_factor * pmax_axis)
    voltage_loss = base_env.voltage_loss * pmax_axis
    season = base_env.season * cond.shade * cond.incidence
    return dataclasses.replace(
        base_env, season=season,
        current_loss=current_loss, voltage_loss=voltage_loss)
```
- [ ] Run it (expect PASS):
  `PYTHONPATH=src python -m pytest tests/test_cell_condition.py -v`
- [ ] Commit:
  `git add src/powerpy/simulation/cell_condition.py tests/test_cell_condition.py && git commit -m "feat(condition): CellCondition + pure idempotent resolve_cell_env consuming every field (Phase 1)"`

---

## Task 7 — Per-cell `CellModel` condition + idempotent `apply`

**Files:**
- Modify: `C:/Users/Nitrox/Downloads/powerpy/powerpy/src/powerpy/simulation/cell_level.py` (import after line 22; constructor lines 130-139; `apply` lines 141-144)
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/tests/test_cell_condition_apply.py`

**Interfaces:**
- Consumes: `CellCondition` + `resolve_cell_env` (Task 6); existing `Environment`, `operating_points` math (`cell_level.py:154-170`).
- Produces:
  - `CellModel.__init__(..., condition: CellCondition | None = None)` — new keyword with default `None` (non-breaking). Stores `self.condition = condition or CellCondition()` and initialises `self._env = resolve_cell_env(self.condition, Environment())`.
  - `CellModel.apply(env)` — resolves through the cell's condition: `self._env = resolve_cell_env(self.condition, env)`. **Idempotent** because `resolve_cell_env` reads `env` (the *base* passed in by the parent each solve), not the already-resolved `self._env` — applying the same base env twice yields the same `self._env`. (Today's `apply` at L144 just stores `env`; the change keeps the stored-env shape identical when `condition` is the default no-op `CellCondition()`.) A one-line comment documents that this idempotency guarantee depends on parents always passing the same base `Environment` down (which the current `StringModel`/`SectionModel`/`PanelModel`/`ArrayModel` `apply` methods do).
  - `CellModel.operating_points()` — **unchanged**. (`voc_override` is dropped from this plan; the `failed_open` epsilon path in `resolve_cell_env` already isolates the string, and a small Voc cap would only produce a physically degenerate `vmp == voc` curve. The voltage axis is now handled cleanly by `pmax_factor` via `voltage_loss` in `resolve_cell_env`.) With the default condition `operating_points()` is byte-identical to today.

TDD steps:

- [ ] Write failing test `tests/test_cell_condition_apply.py`:
```python
from pathlib import Path

import numpy as np
import pytest

from powerpy.loader.report import load_report_data
from powerpy.simulation.cell_level import CellModel
from powerpy.simulation.cell_condition import CellCondition
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def _params():
    return load_report_data(PARAMS, DATA).cell


def test_default_condition_is_unchanged_operating_points():
    p = _params()
    env = Environment(temperature_c=28.0)
    a = CellModel(p)                                  # no condition
    b = CellModel(p, condition=CellCondition())       # explicit no-op
    a.apply(env); b.apply(env)
    assert a.operating_points() == b.operating_points()


def test_shaded_cell_lowers_isc():
    p = _params()
    env = Environment(temperature_c=28.0)
    healthy = CellModel(p)
    shaded = CellModel(p, condition=CellCondition(shade=0.5))
    healthy.apply(env); shaded.apply(env)
    isc_h = healthy.operating_points()[0]
    isc_s = shaded.operating_points()[0]
    assert isc_s == pytest.approx(0.5 * isc_h, rel=1e-9)


def test_imp_factor_lowers_isc():
    p = _params()
    env = Environment(temperature_c=28.0)
    healthy = CellModel(p)
    variant = CellModel(p, condition=CellCondition(imp_factor=0.9))
    healthy.apply(env); variant.apply(env)
    isc_h = healthy.operating_points()[0]
    isc_v = variant.operating_points()[0]
    assert isc_v == pytest.approx(0.9 * isc_h, rel=1e-9)


def test_pmax_factor_lowers_peak_power():
    p = _params()
    env = Environment(temperature_c=28.0)
    healthy = CellModel(p)
    variant = CellModel(p, condition=CellCondition(pmax_factor=0.8))
    healthy.apply(env); variant.apply(env)
    isc_h, imp_h, vmp_h, voc_h = healthy.operating_points()
    isc_v, imp_v, vmp_v, voc_v = variant.operating_points()
    # both axes scaled by sqrt(0.8); the Imp*Vmp product ~= 0.8 of nominal
    assert (imp_v * vmp_v) == pytest.approx(0.8 * imp_h * vmp_h, rel=1e-9)


def test_apply_is_idempotent():
    p = _params()
    env = Environment(temperature_c=28.0)
    c = CellModel(p, condition=CellCondition(shade=0.5, life=0.8))
    c.apply(env)
    op_once = c.operating_points()
    c.apply(env); c.apply(env)
    op_thrice = c.operating_points()
    assert op_once == op_thrice
    v1, i1 = c.iv_curve()
    c.apply(env)
    v2, i2 = c.iv_curve()
    assert np.allclose(v1, v2, rtol=0, atol=1e-12)
    assert np.allclose(i1, i2, rtol=0, atol=1e-12)
```
- [ ] Run it (expect FAIL — `condition` kwarg not accepted):
  `PYTHONPATH=src python -m pytest tests/test_cell_condition_apply.py -v`
  Expected: `TypeError: CellModel.__init__() got an unexpected keyword argument 'condition'`.
- [ ] Minimal implementation — edit `src/powerpy/simulation/cell_level.py`:
  - Add import near the top (after line 22): `from powerpy.simulation.cell_condition import CellCondition, resolve_cell_env`.
  - Constructor (replace lines 130-139 signature + body) to add the keyword and store the condition:
```python
    def __init__(self, params: CellParameters, name: str | None = None,
                 iv_engine: str = "analytic",
                 condition: "CellCondition | None" = None) -> None:
        self.params = params
        self.name = name or params.name
        self.condition = condition or CellCondition()
        self._env = resolve_cell_env(self.condition, Environment())
        # "analytic" = the self-contained single-diode model (no ngspice).
        # "ngspice"  = the vendored ngspice/PySpice path, used when the vendor
        #              is present; it falls back to analytic if it is not.
        self.iv_engine = iv_engine
        self._legacy = None   # lazily-built SchemaCellModel for the ngspice path
```
  - `apply` (replace body at line 144):
```python
    def apply(self, env: Environment) -> None:
        """Resolve the per-cell condition onto the supplied base environment.

        Idempotent: ``resolve_cell_env`` always reads the *base* ``env`` handed
        down by the parent, never the already-resolved ``self._env``.  This
        guarantee relies on parents (String/Section/Panel/Array ``apply``)
        always passing the same base Environment down each solve, which they do.
        """
        self._env = resolve_cell_env(self.condition, env)
```
- [ ] Run it (expect PASS):
  `PYTHONPATH=src python -m pytest tests/test_cell_condition_apply.py -v`
- [ ] Run the full suite — default condition must not change any existing result (expect PASS, no regressions):
  `PYTHONPATH=src python -m pytest -q`
- [ ] Commit:
  `git add src/powerpy/simulation/cell_level.py tests/test_cell_condition_apply.py && git commit -m "feat(cell): per-cell CellCondition + idempotent apply (approach B Phase 1)"`

---

## Task 8 — Seeded, default-off manufacturing-variance sampler → `imp_factor`/`pmax_factor`

**Files:**
- Modify: `C:/Users/Nitrox/Downloads/powerpy/powerpy/src/powerpy/simulation/cell_condition.py` (append `sample_manufacturing_variance`)
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/tests/test_manufacturing_variance.py`

**Interfaces:**
- Consumes: `CellCondition` (Task 6); `resolve_cell_env` (Task 6, to prove the sampled factors actually move an IV); `numpy.random.default_rng` (numpy, already a dependency).
- Produces:
  - `sample_manufacturing_variance(conditions: list[CellCondition], *, seed: int, imp_sigma: float = 0.0, pmax_sigma: float = 0.0) -> list[CellCondition]`. Returns a NEW list of `CellCondition`s with `imp_factor`/`pmax_factor` drawn from a normal distribution centred on each cell's existing factor (`dataclasses.replace`). The draw is **deterministic per seed** (`rng = np.random.default_rng(seed)`, one draw per cell in list order). **Default sigma = 0 is a strict no-op**: when both sigmas are 0 the returned conditions equal the inputs exactly (factors stay at their input values — typically 1.0), so the mechanism changes nothing until a real supplier sigma is entered. Factors are clipped to `> 0` (lower-clamped at a tiny floor) so a draw cannot produce a non-positive factor that `CellCondition.__post_init__` would reject. The sampled factors are *consumed* downstream by `resolve_cell_env` (Task 6) — a test in this task proves a non-unit sampled `imp_factor` moves `resolve_cell_env`'s `current_loss`, so the sampler is not a producer of inert values.

TDD steps:

- [ ] Write failing test `tests/test_manufacturing_variance.py`:
```python
import pytest

from powerpy.simulation.cell_condition import (
    CellCondition, sample_manufacturing_variance, resolve_cell_env,
)
from powerpy.simulation.environment import Environment


def test_default_sigma_is_strict_noop():
    conds = [CellCondition() for _ in range(5)]
    out = sample_manufacturing_variance(conds, seed=0)   # sigmas default to 0
    assert out == conds                                  # nothing changed
    assert all(c.imp_factor == 1.0 and c.pmax_factor == 1.0 for c in out)


def test_sampler_is_deterministic_per_seed():
    conds = [CellCondition() for _ in range(8)]
    a = sample_manufacturing_variance(conds, seed=42, imp_sigma=0.02, pmax_sigma=0.03)
    b = sample_manufacturing_variance(conds, seed=42, imp_sigma=0.02, pmax_sigma=0.03)
    assert [c.imp_factor for c in a] == [c.imp_factor for c in b]
    assert [c.pmax_factor for c in a] == [c.pmax_factor for c in b]


def test_sampler_varies_with_sigma_and_stays_positive():
    conds = [CellCondition() for _ in range(50)]
    out = sample_manufacturing_variance(conds, seed=1, imp_sigma=0.05, pmax_sigma=0.05)
    imps = [c.imp_factor for c in out]
    assert len(set(imps)) > 1                 # actually spread
    assert all(c.imp_factor > 0 and c.pmax_factor > 0 for c in out)


def test_sampled_factor_actually_moves_the_env():
    """The sampled factors are consumed by resolve_cell_env (not inert)."""
    conds = [CellCondition() for _ in range(20)]
    out = sample_manufacturing_variance(conds, seed=7, imp_sigma=0.1)
    base = Environment(season=1.0, current_loss=1.0, voltage_loss=1.0)
    # find a cell whose imp_factor actually moved, and assert it moves current_loss
    moved = next(c for c in out if c.imp_factor != 1.0)
    env = resolve_cell_env(moved, base)
    assert env.current_loss == pytest.approx(moved.imp_factor)   # imp_factor is read
```
- [ ] Run it (expect FAIL — function not defined):
  `PYTHONPATH=src python -m pytest tests/test_manufacturing_variance.py -v`
  Expected: `ImportError: cannot import name 'sample_manufacturing_variance'`.
- [ ] Minimal implementation — append to `src/powerpy/simulation/cell_condition.py`:
```python
import numpy as np


def sample_manufacturing_variance(conditions: list[CellCondition], *, seed: int,
                                  imp_sigma: float = 0.0,
                                  pmax_sigma: float = 0.0) -> list[CellCondition]:
    """Seeded per-cell Imp/Pmax manufacturing variance (default sigma = no-op).

    Deterministic for a given ``seed``.  With both sigmas 0 (the default) the
    returned conditions are identical to the inputs -- the mechanism is wired
    but changes nothing until real supplier spreads are supplied.  The sampled
    ``imp_factor``/``pmax_factor`` are consumed by :func:`resolve_cell_env`.
    """
    if imp_sigma == 0.0 and pmax_sigma == 0.0:
        return list(conditions)
    rng = np.random.default_rng(seed)
    floor = 1e-9
    out: list[CellCondition] = []
    for cond in conditions:
        imp = cond.imp_factor * (1.0 + rng.normal(0.0, imp_sigma))
        pmax = cond.pmax_factor * (1.0 + rng.normal(0.0, pmax_sigma))
        out.append(dataclasses.replace(
            cond,
            imp_factor=max(float(imp), floor),
            pmax_factor=max(float(pmax), floor)))
    return out
```
- [ ] Run it (expect PASS):
  `PYTHONPATH=src python -m pytest tests/test_manufacturing_variance.py -v`
- [ ] Run the condition suite to confirm the append did not break Task 6 (expect PASS):
  `PYTHONPATH=src python -m pytest tests/test_cell_condition.py tests/test_manufacturing_variance.py -q`
- [ ] Run the full suite to confirm no regressions (expect PASS):
  `PYTHONPATH=src python -m pytest -q`
- [ ] Commit:
  `git add src/powerpy/simulation/cell_condition.py tests/test_manufacturing_variance.py && git commit -m "feat(condition): seeded manufacturing-variance sampler (default sigma=0 no-op, factors consumed)"`

---

## Task 9 — Phase-1 integration: shaded lowers IV, chipped lowers current, failed_open isolates one string without collapsing the section, apply twice == once

**Files:**
- Create: `C:/Users/Nitrox/Downloads/powerpy/powerpy/tests/test_phase1_integration.py`
- Modify: `C:/Users/Nitrox/Downloads/powerpy/powerpy/src/powerpy/simulation/spec_build.py` (add optional `conditions` mapping so the integration can attach per-tile conditions)

**Interfaces:**
- Consumes: `build_array_from_spec` (Task 3), `CellCondition` (Task 6), `ArraySpec` (Task 1); the section/string `iv_curve` combination rules (`combine_series` caps at smallest child Isc, `section_level.py:50-54` parallels strings).
- Produces:
  - Extend `build_array_from_spec(..., conditions: dict[int, CellCondition] | None = None)` — new keyword, default `None` (non-breaking). When provided, the `CellModel` created for tile index `idx` is built with `condition=conditions.get(idx, CellCondition())` (falls back to default when absent). Cells are still distinct objects (Task 3 invariant preserved).

  Why `failed_open` isolates rather than collapses: a string of cells is a *series* combine (`combine_series`, capped at the smallest child `Isc`). A truly dead cell (`Isc=0`) would cap that whole string's current to ~0. By realising `failed_open` as a near-dead-but-well-formed cell (tiny `failed_open_epsilon` on `current_loss` → tiny positive `Isc`, full `voltage_loss` → full `Voc`, never the degenerate `[0.0],[0.0]` of `single_diode_iv`), only the *affected string* collapses to ~0 current; the *parallel sibling strings* in the same section keep producing (parallel = currents add at the shared voltage, and `combine_parallel` caps at smallest child `Voc` which is near-normal). This is the documented bug-avoidance the decision calls for.

  **Magic-threshold guard:** the `failed_open` integration test does NOT hard-code an unverified `> 0.25 * nominal` bound. Instead the TDD steps below first MEASURE the real `p_failed/nominal` ratio against the live `params.xlsx` cell, then set bounds with margin around the measured value; the assertion is additionally backed by a structural check (the surviving array Pmax ≈ the Pmax of a single healthy string alone), which is robust to the exact number.

TDD steps:

- [ ] First MEASURE the real ratios (this is a one-shot grounding step, not a committed test). Run:
  `PYTHONPATH=src python -c "from pathlib import Path; from powerpy.loader.report import load_report_data; from powerpy.schemas.panel_circuit import StringSpec, SectionSpec, PanelSpec, ArraySpec; from powerpy.simulation.spec_build import build_array_from_spec; from powerpy.simulation.cell_condition import CellCondition; from powerpy.simulation.environment import Environment; R=Path('.'); cell=load_report_data(R/'params.xlsx', R/'src'/'powerpy'/'data').cell; s1=StringSpec(id='s1', members=(0,1,2)); s2=StringSpec(id='s2', members=(3,4,5)); sec=SectionSpec(id='sec_a', strings=(s1,s2)); spec=ArraySpec(name='spec', panels=(PanelSpec(id='panel_1', sections=(sec,)),)); env=Environment(temperature_c=28.0);\nimport numpy as np\n\ndef pm(a):\n a.apply(env); v,i=a.iv_curve(); return float((v*i).max())\nnom=pm(build_array_from_spec(cell,spec));\nfo=pm(build_array_from_spec(cell,spec,conditions={0:CellCondition(state=\"failed_open\")}));\nsingle=ArraySpec(name=\"one\", panels=(PanelSpec(id=\"panel_1\", sections=(SectionSpec(id=\"sec_a\", strings=(StringSpec(id=\"s1\", members=(0,1,2)),)),)),));\none=pm(build_array_from_spec(cell,single));\nprint(\"nominal\",nom,\"failed\",fo,\"ratio\",fo/nom,\"single_string\",one,\"failed/single\",fo/one)"`
  Record the printed `ratio` and `failed/single`. Use them to set the bounds in the test below (the placeholders `LO`/`HI` and the single-string tolerance) with comfortable margin (e.g. `LO = ratio - 0.1`, `HI = ratio + 0.1`, clamped into `(0, 1)`).
- [ ] Write failing test `tests/test_phase1_integration.py` (substitute the measured `LO`/`HI` for the failed_open ratio bounds; keep the structural single-string check as the robust assertion):
```python
from pathlib import Path

import numpy as np
import pytest

from powerpy.loader.report import load_report_data
from powerpy.schemas.panel_circuit import StringSpec, SectionSpec, PanelSpec, ArraySpec
from powerpy.simulation.spec_build import build_array_from_spec
from powerpy.simulation.cell_condition import CellCondition
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")

# Measured against the live params.xlsx cell (see the MEASURE step); set with
# margin around the recorded ratio.  These are placeholders the implementer
# replaces with the printed numbers.
FAILED_RATIO_LO = 0.35    # <-- replace with measured ratio - 0.1 (clamped >0)
FAILED_RATIO_HI = 0.65    # <-- replace with measured ratio + 0.1 (clamped <1)


def _cell():
    return load_report_data(PARAMS, DATA).cell


def _two_string_spec():
    # two parallel strings of 3 series cells: s1 = tiles 0,1,2 ; s2 = tiles 3,4,5
    s1 = StringSpec(id="s1", members=(0, 1, 2))
    s2 = StringSpec(id="s2", members=(3, 4, 5))
    sec = SectionSpec(id="sec_a", strings=(s1, s2))
    return ArraySpec(name="spec", panels=(PanelSpec(id="panel_1", sections=(sec,)),))


def _single_string_spec():
    s1 = StringSpec(id="s1", members=(0, 1, 2))
    sec = SectionSpec(id="sec_a", strings=(s1,))
    return ArraySpec(name="one", panels=(PanelSpec(id="panel_1", sections=(sec,)),))


def _pmax(arr, env):
    arr.apply(env)
    v, i = arr.iv_curve()
    return float((v * i).max())


def test_shaded_cell_lowers_array_pmax():
    cell, spec, env = _cell(), _two_string_spec(), Environment(temperature_c=28.0)
    nominal = _pmax(build_array_from_spec(cell, spec), env)
    shaded = _pmax(build_array_from_spec(
        cell, spec, conditions={1: CellCondition(shade=0.4)}), env)
    assert shaded < nominal


def test_chipped_cell_lowers_string_current():
    cell, spec, env = _cell(), _two_string_spec(), Environment(temperature_c=28.0)
    nominal = _pmax(build_array_from_spec(cell, spec), env)
    chipped = _pmax(build_array_from_spec(
        cell, spec, conditions={4: CellCondition(life=0.6)}), env)
    assert chipped < nominal


def test_failed_open_isolates_string_without_collapsing_section():
    cell, env = _cell(), Environment(temperature_c=28.0)
    spec = _two_string_spec()
    nominal = _pmax(build_array_from_spec(cell, spec), env)

    # kill ONE cell in string s1; string s2 must keep producing
    failed = build_array_from_spec(
        cell, spec, conditions={0: CellCondition(state="failed_open")})
    p_failed = _pmax(failed, env)

    # measured-and-margined ratio bound (NOT an arbitrary 0.25)
    ratio = p_failed / nominal
    assert FAILED_RATIO_LO < ratio < FAILED_RATIO_HI

    # ROBUST structural check: the survivor is ~the Pmax of a single healthy
    # string alone (the failed string contributes ~0).
    one_string = _pmax(build_array_from_spec(cell, _single_string_spec()), env)
    assert p_failed == pytest.approx(one_string, rel=0.05)

    # surviving curve is finite
    failed.apply(env)
    v, i = failed.iv_curve()
    assert np.all(np.isfinite(v)) and np.all(np.isfinite(i))


def test_array_apply_is_idempotent():
    cell, spec, env = _cell(), _two_string_spec(), Environment(temperature_c=28.0)
    arr = build_array_from_spec(cell, spec, conditions={1: CellCondition(shade=0.5)})
    arr.apply(env)
    v1, i1 = arr.iv_curve()
    arr.apply(env); arr.apply(env)
    v2, i2 = arr.iv_curve()
    assert np.allclose(v1, v2, rtol=0, atol=1e-12)
    assert np.allclose(i1, i2, rtol=0, atol=1e-12)
```
- [ ] Run it (expect FAIL — `conditions` kwarg not accepted):
  `PYTHONPATH=src python -m pytest tests/test_phase1_integration.py -v`
  Expected: `TypeError: build_array_from_spec() got an unexpected keyword argument 'conditions'`.
- [ ] Minimal implementation — edit `src/powerpy/simulation/spec_build.py`:
  - Add `from powerpy.simulation.cell_condition import CellCondition` to the imports.
  - Extend the signature to `def build_array_from_spec(cell_params, spec, *, iv_engine="analytic", string_shunt_vf=None, conditions=None):` and, inside the `for st in sec.strings` loop, replace the cell construction line:
```python
                cond_map = conditions or {}
                cells = [
                    CellModel(cell_params, iv_engine=iv_engine,
                              condition=cond_map.get(idx, CellCondition()))
                    for idx in st.members
                ]
```
  (Update the surrounding docstring to mention the optional `conditions` mapping from tile index → `CellCondition`.)
- [ ] Run it (expect PASS — with the measured `LO`/`HI` filled in):
  `PYTHONPATH=src python -m pytest tests/test_phase1_integration.py -v`
- [ ] Run the whole new+existing suite (expect PASS, no regressions):
  `PYTHONPATH=src python -m pytest -q`
- [ ] Commit:
  `git add src/powerpy/simulation/spec_build.py tests/test_phase1_integration.py && git commit -m "feat(spec): per-tile conditions in build_array_from_spec + Phase-1 integration tests"`

---

## Deferred to follow-on plans
- **Phase 2 (thermal + power read-back):** per-cell `p_elec` derived from each tile's operating point fed into `solve_panel(layout, p_elec=pe, ...)` (`solve/thermal.py:236`) via `make_pe` (`analysis/study.py:34`); a back-propagation solver to read per-cell power/voltage from the converged array operating point; the reverse-bias dissipation branch (`reverse_w` in `make_pe`); and per-cell thermal coupling (each cell's `Environment.temperature_c`). Lateral conduction stays off (`g_lat=0`) per the current decision. Also: wiring `build_array_from_spec`/the adapters into `app.py`'s `_build_array()` (currently dispatches only `build_array_from_circuit` vs `build_from_report`, app.py:153-161) once Phase 2 needs the position map.
- **`failed_short` and reverse-bias** remain an ngspice hatch — not analytic. A `voc_override`-style per-cell Voc cap is also deferred (not needed for `failed_open`, which the epsilon path handles); if a future failure mode needs an explicit Voc clamp it should be specced with a guard documenting the `vmp == voc` degeneracy.
- **Phase 3 (authoring):** spatial Excel condition layers (shaded / %-life / angle / bypass per cell), a `setup_sim.py` generator that emits an `ArraySpec` + per-tile `CellCondition` map, and per-run snapshot folders (see the `per-element-config-direction` memory note).
