# Phase 4 — CLI Intent Verbs: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the CLI its final intent-verb shape — `report` (PDF, use case A), `analyse` (results.xlsx, use case B, absorbing `scripts/write_results.py`), `sweep` (Monte-Carlo + worst-case, absorbing the `worst` subcommand) — and delete the duplicate example and the four one-sheet mutator scripts.

**Architecture:** `report` already exists (P2). `analyse` is `write_results.py`'s flow relocated: the per-string/per-cell operating-point breakdown moves into `powerpy/analysis/operating.py` (compute), `app.py::_cmd_analyse` (wiring, flag-compatible with the script), and `output/excel.py` (already the writer); the script shrinks to a forwarding shim so existing invocations and tests keep working. `worst` folds into `sweep --worst` (identical code path — greedy `worst_case_search` with the same `make_pe` heuristic). Byte gates: `analyse` reproduces the P3 `results.xlsx` baseline; `sweep --worst` reproduces the pre-P4 `worst` HTML/JSON baseline (captured before any edit).

## Global Constraints

- No numeric change: `analyse` output value-identical to `write_results.py`; `sweep --worst` artifacts byte-identical to old `worst`.
- Legacy invocations keep working: `python scripts/write_results.py ...` (shim), `powerpy run` stays untouched.
- No `pip install`; suite via `PYTHONPATH=src python -m pytest`.

## Deliberate deviations from the design doc §6 (recorded)

1. **`run` stays** as the quick layout thermal check. The doc absorbed it via "failure injection = condition layers", but condition-driven thermal is the deferred per-cell-physics path (approach-B Q3: standalone API only); deleting `run` today would lose its `make_pe`-based output with no equivalent. It folds into `analyse --thermal` later, when per-cell thermal is wired into the CLI.
2. **`analyse --thermal` deferred** with it (same reason). `analyse` in P4 = electrical results.xlsx exactly as `write_results.py` produced.
3. `build_sample_params.py` / `_gen_build_params.py` stay for **P5** (already on the §7 prune list).

## Tasks

### Task 1: `powerpy analyse`
- Create `src/powerpy/analysis/operating.py` — `analyse_operating_point(cell, layout, conditions, env) -> (summary, strings, cells)`: the exact `analyse()` body from `scripts/write_results.py` (including its nominal-comparison second build). No numeric edits.
- `app.py`: `_cmd_analyse` + subparser with the script's flag set (`--design --scenario --params --layout --parallel --series --blocks --irradiance --out`, plus hidden no-op `--no-report` for shim compat). Heavy imports stay local to the function.
- `scripts/write_results.py` → shim: forwards `sys.argv[1:]` to `powerpy.app.main(["analyse", ...])` (module keeps `main(argv)` so tests still call it).
- Gate: `powerpy analyse --no-report --out X` value-identical (all sheets/rows) to `p3_baseline/baseline_results.xlsx`; `tests/test_b_path_partial_load.py` green through the shim.

### Task 2: `sweep --worst`
- `sweep` subparser gains `--worst`, `--max-failures`, `--report`, `--json`; `_cmd_sweep` dispatches to the old `_cmd_worst` body when `--worst`.
- Remove the `worst` subparser + `_cmd_worst` registration.
- `tests/test_cli.py::test_worst_subcommand` becomes `sweep --worst`.
- Gate: `sweep --worst` HTML/JSON byte-identical to `p4_baseline/worst.{html,json}`; stdout trajectory equivalent.

### Task 3: delete the debris
- `examples/build_noNG_elec_report.py` (verbatim duplicate of `powerpy report` by its own docstring).
- `scripts/add_analysis_sheet.py`, `add_requirement_sheet.py`, `set_mission_orbit.py`, `edit_structure.py` (one-shot sheet mutators with hard-coded edit constants; their sheets ship in the workbook and `build_params.py` regenerates everything). No external references (grep-verified).

### Task 4: phase gate
`tests/test_p4_gate.py`: parser subcommands == `{run, sweep, report, analyse}`; `--help` builds for each verb; `analyse` module has no import-time dependency on `scripts/`.
