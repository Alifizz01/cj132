import pytest
from powerpy.schemas.circuit import CircuitLayout, CircuitSection, CircuitString


def _string(id="s1", n=22, **kw):
    return CircuitString(id=id, n_series=n, **kw)


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
