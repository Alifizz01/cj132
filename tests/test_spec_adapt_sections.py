from pathlib import Path

import numpy as np
import pytest

from powerpy.loader.report import load_report_data
from powerpy.loader.circuit import load_circuit
from powerpy.schemas.panel_circuit import validate_bijection
from powerpy.simulation.spec_adapt import adapt_sections, adapt_circuit
from powerpy.simulation.spec_build import build_array_from_spec
from powerpy.simulation.array_level import build_from_report
from powerpy.simulation.circuit_build import build_array_from_circuit
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "src" / "powerpy" / "param" / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
SAMPLE = DATA / "circuits" / "msro_nominal.json"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def _report():
    return load_report_data(PARAMS, DATA)


def test_adapt_sections_is_a_bijection_over_all_scas():
    report = _report()
    spec = adapt_sections(report.array_layout)
    validate_bijection(spec, report.array_layout.n_sca_total)


def test_adapt_sections_reproduces_build_from_report_iv():
    report = _report()
    env = Environment(temperature_c=28.0)

    string_shunt_vf = (report.cell.string_diode.v_forward
                       if getattr(report.cell, "string_diode", None) else None)
    spec = adapt_sections(report.array_layout)
    arr_spec = build_array_from_spec(report.cell, spec, iv_engine="analytic",
                                     string_shunt_vf=string_shunt_vf)
    arr_spec.apply(env)
    v_spec, i_spec = arr_spec.iv_curve()

    arr_ref = build_from_report(report, iv_engine="analytic")
    arr_ref.apply(env)
    v_ref, i_ref = arr_ref.iv_curve()

    assert np.allclose(v_spec, v_ref, rtol=0, atol=1e-9)
    assert np.allclose(i_spec, i_ref, rtol=0, atol=1e-9)


def test_adapt_circuit_reproduces_build_array_from_circuit_iv():
    report = _report()
    circuit = load_circuit(SAMPLE)
    env = Environment(temperature_c=28.0)
    string_shunt_vf = (report.cell.string_diode.v_forward
                       if getattr(report.cell, "string_diode", None) else None)

    spec = adapt_circuit(circuit)
    arr_spec = build_array_from_spec(report.cell, spec, iv_engine="analytic",
                                     string_shunt_vf=string_shunt_vf)
    arr_spec.apply(env)
    v_spec, i_spec = arr_spec.iv_curve()

    arr_ref = build_array_from_circuit(report.cell, circuit, iv_engine="analytic",
                                       string_shunt_vf=string_shunt_vf)
    arr_ref.apply(env)
    v_ref, i_ref = arr_ref.iv_curve()

    assert np.allclose(v_spec, v_ref, rtol=0, atol=1e-9)
    assert np.allclose(i_spec, i_ref, rtol=0, atol=1e-9)
