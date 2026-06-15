from pathlib import Path

import numpy as np
from powerpy.config.layout import PanelLayout, TileType, from_dict
from powerpy.loader.report import load_report_data
from powerpy.simulation.grid_build import build_array_from_grid
from powerpy.simulation.environment import Environment

_PARAMS = Path("params.xlsx")
_DATA_DIR = Path("src/powerpy/data")


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
