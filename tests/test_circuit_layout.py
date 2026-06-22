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


import numpy as np
from powerpy.loader.report import load_report_data
from powerpy.simulation.circuit_build import build_array_from_circuit
from powerpy.simulation.environment import Environment

_DATA_DIR = Path("src/powerpy/data")
_PARAMS = Path("src/powerpy/param/params.xlsx")


def test_build_array_from_circuit_structure_and_curve():
    report = load_report_data(_PARAMS, _DATA_DIR)
    circuit = load_circuit(_SAMPLE)
    array = build_array_from_circuit(report.cell, circuit, iv_engine="analytic")
    # one panel ("panel_1"), two sections, strings 2 + 1
    assert len(array.panels) == 1
    sections = list(array.iter_sections())
    assert len(sections) == 2
    assert [len(s.strings) for s in sections] == [2, 1]
    # heterogeneous series counts preserved
    assert len(sections[0].strings[0].cells) == 22
    assert len(sections[1].strings[0].cells) == 20
    # nominal curve is finite with a positive peak power
    array.apply(Environment(temperature_c=28.0))
    v, i = array.iv_curve()
    p = v * i
    assert np.all(np.isfinite(v)) and np.all(np.isfinite(i))
    assert float(p.max()) > 0.0


from powerpy.schemas.cell import CellParameters


def test_cellparameters_has_optional_circuit_reference():
    report = load_report_data(_PARAMS, _DATA_DIR)
    assert hasattr(report.cell, "circuit_reference_file")
    # the workbook may or may not reference a circuit yet; either None or a Path
    ref = report.cell.circuit_reference_file
    assert ref is None or ref.name.endswith(".json")


from powerpy.app import build_electrical_report


def test_build_electrical_report_uses_circuit(tmp_path, monkeypatch):
    import dataclasses
    import powerpy.simulation.report_build as rb
    import powerpy.loader.report as report_mod

    captured = {}
    real_build = rb.build_array_from_spec

    # the report path now assembles every topology through build_array_from_spec;
    # a circuit ref must reach it as a circuit-shaped spec ([2, 1] strings/section).
    def spy(cell_params, spec, **kw):
        captured["sections"] = [len(s.strings) for p in spec.panels for s in p.sections]
        return real_build(cell_params, spec, **kw)

    monkeypatch.setattr(rb, "build_array_from_spec", spy)

    real_load = report_mod.load_report_data

    def patched_load(params, data_dir):
        rep = real_load(params, data_dir)
        cell = dataclasses.replace(rep.cell, circuit_reference_file=_SAMPLE.resolve())
        return dataclasses.replace(rep, cell=cell)

    monkeypatch.setattr(report_mod, "load_report_data", patched_load)

    pdf, labels, rep = build_electrical_report(
        _PARAMS, tmp_path / "out.pdf", data_dir=_DATA_DIR, engine="analytic")
    assert captured.get("sections") == [2, 1]   # circuit topology flowed through the spec builder
    assert labels                                # at least one scoped case


def test_build_electrical_report_without_circuit_uses_arraylayout(tmp_path, monkeypatch):
    """Regression: with no circuit_reference_file (the default workbook), the
    report falls back to the ArrayLayout path and does NOT touch the circuit
    builder -- so existing report output is unchanged."""
    import powerpy.simulation.circuit_build as cb

    called = {"n": 0}
    real_build = cb.build_array_from_circuit

    def spy(*a, **kw):
        called["n"] += 1
        return real_build(*a, **kw)

    monkeypatch.setattr(cb, "build_array_from_circuit", spy)

    pdf, labels, rep = build_electrical_report(
        _PARAMS, tmp_path / "out.pdf", data_dir=_DATA_DIR, engine="analytic")
    assert rep.cell.circuit_reference_file is None   # default workbook: no circuit
    assert called["n"] == 0                          # circuit builder NOT used
    assert labels                                    # report still produced cases
