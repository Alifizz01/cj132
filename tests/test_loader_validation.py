"""V3/V4/V2: loud-failure guards for the Excel-as-database layer.

V3 -- include-column parsing is robust, and a non-empty sheet that filters
     to zero rows raises instead of silently vanishing.
V4 -- required document keys (incl. issued_date) fail loud, no silent default.
V2 -- physics schemas reject impossible values at construction.
"""
import pandas as pd
import pytest

from powerpy.loader._common import filter_included, require_keyvalue
from powerpy.schemas.cell import CellElectrical, CellParameters, ShuntDiodeParameters
from powerpy.schemas.layout import SectionType


# ---------------------------------------------------------------- V3
def _df(include_values):
    return pd.DataFrame({"value": range(len(include_values)),
                         "include": include_values})


def test_filter_included_robust_truthy():
    # whitespace, mixed case, numeric 1, bool True all count as included
    df = _df(["TRUE ", "true", 1, True, "Yes"])
    assert len(filter_included(df, "s")) == 5


def test_filter_included_robust_falsey():
    df = _df(["FALSE", 0, False, None, float("nan")])
    # all excluded -> non-empty input filtered to zero -> raise
    with pytest.raises(ValueError, match="none are included"):
        filter_included(df, "mysheet")


def test_filter_included_partial_ok():
    df = _df(["TRUE", "FALSE", "TRUE"])
    assert len(filter_included(df, "s")) == 2


def test_filter_included_empty_input_ok():
    # genuinely empty sheet -> nothing to drop, no raise
    df = pd.DataFrame({"value": [], "include": []})
    assert len(filter_included(df, "s")) == 0


def test_filter_included_no_include_column_passthrough():
    df = pd.DataFrame({"value": [1, 2]})
    assert len(filter_included(df, "s")) == 2


# ---------------------------------------------------------------- V4
def test_require_keyvalue_present():
    assert require_keyvalue({"k": "v"}, "k", "document") == "v"


def test_require_keyvalue_missing_raises():
    with pytest.raises(ValueError, match="required key 'doc_title'"):
        require_keyvalue({}, "doc_title", "document")


def test_require_keyvalue_blank_raises():
    with pytest.raises(ValueError, match="missing or blank"):
        require_keyvalue({"author": "   "}, "author", "document")


# ---------------------------------------------------------------- V2
def _electrical(**kw):
    base = dict(isc_bol=1.2, voc_bol=2.7, imp_bol=1.1, vmp_bol=2.4,
                temp_coeff_isc=0.04, temp_coeff_voc=-0.006)
    base.update(kw)
    return CellElectrical(**base)


def test_cell_electrical_ok():
    _electrical(alpha=0.91, epsilon=0.83, area_m2=0.007)  # no raise


def test_cell_electrical_negative_isc_raises():
    with pytest.raises(ValueError, match="isc_bol"):
        _electrical(isc_bol=-1.0)


def test_cell_electrical_zero_voc_raises():
    with pytest.raises(ValueError, match="voc_bol"):
        _electrical(voc_bol=0.0)


def test_cell_electrical_alpha_out_of_range_raises():
    with pytest.raises(ValueError, match="alpha"):
        _electrical(alpha=1.5)


def test_section_type_zero_strings_raises():
    with pytest.raises(ValueError, match="n_strings_parallel"):
        SectionType(section_id="a", section_name="A",
                    n_strings_parallel=0, n_sca_series_per_string=54)


def test_section_type_ok():
    SectionType(section_id="a", section_name="A",
                n_strings_parallel=4, n_sca_series_per_string=54)  # no raise


def test_cell_parameters_negative_area_raises():
    with pytest.raises(ValueError, match="cell_area_cm2"):
        CellParameters(
            name="c", manufacturer="m", base_material="b", junction="j",
            ar_coating="a", front_contact="f", rear_contact="r",
            substrate_material="s",
            cell_length_mm=124.3, cell_width_mm=60.5, cell_thickness_um=160.0,
            substrate_thickness_um=140.0, cell_area_cm2=-1.0, cell_mass_mg=6100.0,
            reference_file=None, diode_reference_file=None,
            electrical=_electrical(),
        )
