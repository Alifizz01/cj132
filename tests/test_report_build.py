from pathlib import Path

import numpy as np
import pytest

from powerpy.loader.report import load_report_data
from powerpy.loader.circuit import load_circuit
from powerpy.config.layout import load_layout
from powerpy.simulation.report_build import build_array_for_report
from powerpy.simulation.array_level import build_from_report
from powerpy.simulation.circuit_build import build_array_from_circuit
from powerpy.simulation.grid_build import build_array_from_grid
from powerpy.simulation.environment import Environment

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "src" / "powerpy" / "param" / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
GRID = DATA / "layouts" / "grid_3x2x12.json"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def _report():
    return load_report_data(PARAMS, DATA)


def _shunt_vf(report):
    return (report.cell.string_diode.v_forward
            if getattr(report.cell, "string_diode", None) else None)


def _iv(array, env):
    array.apply(env)
    return array.iv_curve()


def test_report_build_sections_matches_legacy():
    report = _report()
    env = Environment(temperature_c=28.0)
    v_new, i_new = _iv(build_array_for_report(report), env)
    v_ref, i_ref = _iv(build_from_report(report, iv_engine="analytic"), env)
    assert np.allclose(v_new, v_ref, rtol=0, atol=1e-9)
    assert np.allclose(i_new, i_ref, rtol=0, atol=1e-9)


def test_report_build_grid_matches_legacy():
    report = _report()
    env = Environment(temperature_c=28.0)
    layout = load_layout(str(GRID))
    v_new, i_new = _iv(build_array_for_report(report, grid_file=str(GRID)), env)
    ref = build_array_from_grid(report.cell, layout, layout.circuit_params,
                                iv_engine="analytic", string_shunt_vf=_shunt_vf(report))
    v_ref, i_ref = _iv(ref, env)
    assert np.allclose(v_new, v_ref, rtol=0, atol=1e-9)
    assert np.allclose(i_new, i_ref, rtol=0, atol=1e-9)


def _first_phase(report):
    return sorted({f.phase for f in report.losses}, key=str)[0]


def test_evaluate_with_prebuilt_array_matches_internal_build():
    from powerpy.simulation.pipeline import evaluate, AnalysisCase
    report = _report()
    phase = _first_phase(report)
    cases = [AnalysisCase(label=str(phase), phase=phase)]

    ref = evaluate(report, cases, build_kwargs={"iv_engine": "analytic"})
    pre = evaluate(report, cases, array=build_array_for_report(report))

    r0, p0 = ref[0].results.array, pre[0].results.array
    for attr in ("p_mp", "v_mp", "i_mp", "isc", "voc"):
        assert np.isclose(getattr(r0, attr), getattr(p0, attr), rtol=0, atol=1e-9), attr


def test_report_build_sections_only_matches_build_from_report():
    """The no-analysis-sheet fallback uses sections_only -> must equal the legacy
    build_from_report regardless of any grid/circuit ref on the cell."""
    report = _report()
    env = Environment(temperature_c=28.0)
    v_new, i_new = _iv(build_array_for_report(report, sections_only=True), env)
    v_ref, i_ref = _iv(build_from_report(report, iv_engine="analytic"), env)
    assert np.allclose(v_new, v_ref, rtol=0, atol=1e-9)
    assert np.allclose(i_new, i_ref, rtol=0, atol=1e-9)


def test_whole_report_numbers_unchanged_scope_path():
    """Every scoped case's array MPP is identical legacy-vs-spec builder.
    This is the P1 gate: it must stay green after app.py is rewired."""
    import dataclasses
    from powerpy.loader.analysis import load_analysis_scope
    from powerpy.simulation.pipeline import environment_for_phase, run
    report = _report()
    scope = load_analysis_scope(PARAMS)
    if not scope:
        pytest.skip("no analysis sheet -> scope path not exercised")

    legacy = build_from_report(report, iv_engine="analytic")
    spec = build_array_for_report(report)

    for cfg in scope:
        env = environment_for_phase(
            report, phase=cfg.phase, launch_config=cfg.launch,
            temperature_c=cfg.temperature_c, season=cfg.season,
            angle_alpha_deg=cfg.sun_angle_deg)
        if cfg.string_loss != 1.0:
            env = dataclasses.replace(env, current_loss=env.current_loss * cfg.string_loss)
        r_leg = run(legacy, env).array
        r_new = run(spec, env).array
        for attr in ("isc", "voc", "v_mp", "i_mp", "p_mp"):
            assert np.isclose(getattr(r_leg, attr), getattr(r_new, attr),
                              rtol=0, atol=1e-9), (cfg.label, attr)
