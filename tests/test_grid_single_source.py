from pathlib import Path

import numpy as np
from powerpy.config.layout import PanelLayout, TileType, from_dict, load_layout
from powerpy.loader.report import load_report_data
from powerpy.simulation.grid_build import build_array_from_grid
from powerpy.simulation.environment import Environment

_ROOT = Path(__file__).resolve().parents[1]
_PARAMS = _ROOT / "src" / "powerpy" / "param" / "params.xlsx"
_DATA_DIR = _ROOT / "src" / "powerpy" / "data"


def _demo_dict():
    # 2 rows x 3 cols. Row 1 = string s1 (3 cells in series), block bA.
    # Row 2 = string s2 (3 cells), block bA. So block bA has 2 parallel strings.
    return {
        "name": "demo",
        "pitch_mm": 40.0,
        "palette": {
            "1": {"is_cell": True, "string": "s1", "block": "bA"},
            "2": {"is_cell": True, "string": "s2", "block": "bA"},
        },
        "layout": ["1 1 1", "2 2 2"],
        "circuit": {
            "s1": {"n_block_diodes": 1, "block_diode_v_drop": 0.6, "string_shunt_diode": True},
            "bA": {"resistance_ohm": 0.01},
        },
    }


def test_from_dict_parses_circuit_block():
    lay = from_dict(_demo_dict())
    assert lay.circuit_params["s1"]["n_block_diodes"] == 1
    assert lay.circuit_params["bA"]["resistance_ohm"] == 0.01


def test_circuit_params_defaults_empty_when_absent():
    d = _demo_dict()
    d.pop("circuit")
    lay = from_dict(d)
    assert lay.circuit_params == {}


def test_cell_strings_groups_by_string_and_block():
    lay = from_dict(_demo_dict())
    strings, string_block = lay.cell_strings()
    assert {sid: len(idxs) for sid, idxs in strings.items()} == {"s1": 3, "s2": 3}
    assert string_block == {"s1": "bA", "s2": "bA"}


def test_cell_strings_rejects_string_spanning_two_blocks():
    import pytest
    d = {
        "palette": {
            "1": {"is_cell": True, "string": "s1", "block": "bA"},
            "2": {"is_cell": True, "string": "s1", "block": "bB"},  # same string, other block
        },
        "layout": ["1 2"],
    }
    lay = from_dict(d)
    with pytest.raises(ValueError):
        lay.cell_strings()


def test_build_array_from_grid_structure_and_curve():
    report = load_report_data(_PARAMS, _DATA_DIR)
    lay = from_dict(_demo_dict())
    array = build_array_from_grid(report.cell, lay, lay.circuit_params,
                                  iv_engine="analytic")
    assert len(array.panels) == 1
    sections = list(array.iter_sections())
    assert len(sections) == 1                 # one block bA -> one section
    assert len(sections[0].strings) == 2      # two parallel strings
    assert sorted(len(s.cells) for s in sections[0].strings) == [3, 3]
    array.apply(Environment(temperature_c=28.0))
    v, i = array.iv_curve()
    p = v * i
    assert np.all(np.isfinite(v)) and float(p.max()) > 0.0


def test_cellparameters_has_optional_grid_reference():
    report = load_report_data(_PARAMS, _DATA_DIR)
    assert hasattr(report.cell, "grid_reference_file")
    ref = report.cell.grid_reference_file
    assert ref is None or ref.name.endswith(".json")


def test_cellparameters_has_optional_substrate_reference():
    report = load_report_data(_PARAMS, _DATA_DIR)
    assert hasattr(report.cell, "substrate_reference_file")
    ref = report.cell.substrate_reference_file
    assert ref is None or ref.name.endswith(".json")


def test_report_uses_grid_when_referenced(tmp_path, monkeypatch):
    import json
    import dataclasses
    import powerpy.simulation.grid_build as gb
    import powerpy.loader.report as report_mod
    from powerpy.app import build_electrical_report

    grid_path = tmp_path / "grid.json"
    grid_path.write_text(json.dumps(_demo_dict()), encoding="utf-8")

    called = {"n": 0}
    real = gb.build_array_from_grid

    def spy(cell_params, layout, circuit_params=None, **kw):
        called["n"] += 1
        return real(cell_params, layout, circuit_params, **kw)

    monkeypatch.setattr(gb, "build_array_from_grid", spy)

    real_load = report_mod.load_report_data

    def patched_load(params, data_dir):
        rep = real_load(params, data_dir)
        cell = dataclasses.replace(rep.cell, grid_reference_file=grid_path)
        return dataclasses.replace(rep, cell=cell)

    monkeypatch.setattr(report_mod, "load_report_data", patched_load)

    pdf, labels, rep = build_electrical_report(
        _PARAMS, tmp_path / "out.pdf", data_dir=_DATA_DIR, engine="analytic")
    assert called["n"] == 1     # grid path used exactly once (one panel built)
    assert labels


def test_report_without_grid_does_not_use_grid_builder(tmp_path, monkeypatch):
    """Negative: the default workbook has no grid_reference_file, so the grid
    builder must NOT be invoked (the report falls back to the ArrayLayout)."""
    import powerpy.simulation.grid_build as gb
    from powerpy.app import build_electrical_report

    called = {"n": 0}
    real = gb.build_array_from_grid

    def spy(*a, **kw):
        called["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(gb, "build_array_from_grid", spy)

    pdf, labels, rep = build_electrical_report(
        _PARAMS, tmp_path / "out.pdf", data_dir=_DATA_DIR, engine="analytic")
    assert rep.cell.grid_reference_file is None   # default workbook: no grid
    assert called["n"] == 0                       # grid builder NOT used
    assert labels


_SAMPLE_GRID = Path("src/powerpy/data/layouts/grid_circuit_demo.json")


def test_sample_grid_builds_expected_circuit():
    report = load_report_data(_PARAMS, _DATA_DIR)
    lay = load_layout(_SAMPLE_GRID)
    array = build_array_from_grid(report.cell, lay, lay.circuit_params,
                                  iv_engine="analytic")
    sections = list(array.iter_sections())
    # blocks bA, bB -> two sections; bA has 2 strings, bB has 1
    assert len(sections) == 2
    assert sorted(len(s.strings) for s in sections) == [1, 2]
    # s1/s2 are 4 cells in series, s3 is 3 (the "." tile generates no power)
    all_series = sorted(len(s.cells) for sec in sections for s in sec.strings)
    assert all_series == [3, 4, 4]
    array.apply(Environment(temperature_c=28.0))
    v, i = array.iv_curve()
    assert float((v * i).max()) > 0.0
