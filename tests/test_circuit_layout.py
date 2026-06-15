from pathlib import Path

import pytest
from powerpy.schemas.circuit import CircuitLayout, CircuitSection, CircuitString


def _string(string_id="s1", n=22, **kw):
    return CircuitString(id=string_id, n_series=n, **kw)


def test_string_defaults_and_validation():
    s = _string()
    assert s.n_series == 22
    assert s.block_diode_v_drop == 0.6
    assert s.string_shunt_diode is True
    with pytest.raises(ValueError):
        _string(n=0)                      # n_series must be >= 1
    with pytest.raises(ValueError):
        CircuitString(id="", n_series=5)  # id required


def test_section_requires_strings_and_unique_ids():
    sec = CircuitSection(id="sec_a", strings=(_string("s1"), _string("s2")))
    assert sec.panel == "panel_1"
    assert len(sec.strings) == 2
    with pytest.raises(ValueError):
        CircuitSection(id="sec_a", strings=())               # >= 1 string
    with pytest.raises(ValueError):
        CircuitSection(id="sec_a", strings=(_string("s1"), _string("s1")))  # dup ids


def test_layout_requires_sections_and_unique_ids():
    lay = CircuitLayout(name="c", sections=(
        CircuitSection(id="a", strings=(_string(),)),
        CircuitSection(id="b", strings=(_string(),)),
    ))
    assert lay.name == "c" and len(lay.sections) == 2
    with pytest.raises(ValueError):
        CircuitLayout(name="c", sections=())
    with pytest.raises(ValueError):
        CircuitLayout(name="c", sections=(
            CircuitSection(id="a", strings=(_string(),)),
            CircuitSection(id="a", strings=(_string(),)),
        ))


def test_string_rejects_negative_values():
    with pytest.raises(ValueError):
        _string(series_resistance_ohm=-0.1)
    with pytest.raises(ValueError):
        _string(block_diode_v_drop=-0.1)


from powerpy.loader.circuit import load_circuit

_SAMPLE = Path("src/powerpy/data/circuits/msro_nominal.json")


def test_load_circuit_parses_sample():
    c = load_circuit(_SAMPLE)
    assert c.name == "msro_nominal"
    assert [s.id for s in c.sections] == ["sec_a", "sec_b"]
    sec_a = c.sections[0]
    assert sec_a.panel == "panel_1"
    assert [s.id for s in sec_a.strings] == ["s1", "s2"]
    assert sec_a.strings[0].n_series == 22
    assert sec_a.strings[1].block_diode_v_drop == 0.6   # default applied where omitted
    assert c.sections[1].strings[0].n_series == 20
    assert c.sections[1].resistance_ohm == 0.0


def test_load_circuit_missing_file():
    with pytest.raises(FileNotFoundError):
        load_circuit(Path("does/not/exist.json"))
