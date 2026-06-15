import numpy as np
from powerpy.config.layout import PanelLayout, TileType, from_dict


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
