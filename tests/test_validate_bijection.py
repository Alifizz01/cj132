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
