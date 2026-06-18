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
        _string(block_diode_v_drop=-0.1)
    with pytest.raises(ValueError):
        _string(n_block_diodes=-1)


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
