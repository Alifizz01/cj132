"""Phase-2 gate: snapshot identity, A-minimal report, legacy end-to-end.

These must pass with no further code change; a failure here is a bug in the
P2 tasks, not in this file.
"""
import shutil
import sys
from pathlib import Path

import dataclasses
import numpy as np
import openpyxl
import pytest

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "src" / "powerpy" / "param" / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")

sys.path.insert(0, str(ROOT / "scripts"))
from split_params import split_params  # noqa: E402
from setup_sim import run_setup_sim  # noqa: E402

from powerpy.config.layout import panel_from_topology  # noqa: E402
from powerpy.loader.report import load_report_data  # noqa: E402
from powerpy.loader.analysis import load_analysis_scope  # noqa: E402
from powerpy.simulation.report_build import build_array_for_report  # noqa: E402
from powerpy.simulation.pipeline import environment_for_phase, run  # noqa: E402


def test_snapshot_identity_legacy_vs_split(tmp_path):
    """The same layout + the same condition layers must yield byte-identical
    snapshots whether the layers live in a legacy params.xlsx or a split
    scenario.xlsx."""
    legacy_wb = tmp_path / "params.xlsx"
    shutil.copy(PARAMS, legacy_wb)          # never touch the live workbook
    _, scenario = split_params(PARAMS, tmp_path / "design.xlsx",
                               tmp_path / "scenario.xlsx")
    layout = panel_from_topology(n_blocks=1, n_parallel=4, n_series=10)

    snap_legacy = run_setup_sim(layout, wb_path=legacy_wb,
                                runs_dir=tmp_path / "runs_a", run_id="gate")
    snap_split = run_setup_sim(layout, wb_path=scenario,
                               runs_dir=tmp_path / "runs_b", run_id="gate")
    assert snap_legacy.read_bytes() == snap_split.read_bytes()


def test_a_minimal_report_without_layer_sheets(tmp_path):
    """A scenario.xlsx with NO layer_* sheets still produces the same scoped
    MPP numbers as the legacy single file -- A never sees B's sheets."""
    design, scenario = split_params(PARAMS, tmp_path / "design.xlsx",
                                    tmp_path / "scenario.xlsx")
    wb = openpyxl.load_workbook(str(scenario))
    for name in list(wb.sheetnames):
        if name.startswith("layer_"):
            wb.remove(wb[name])
    wb.save(str(scenario))

    legacy = load_report_data(PARAMS, DATA)
    pair = load_report_data(design, DATA, scenario_file=scenario)
    arr_legacy = build_array_for_report(legacy)
    arr_pair = build_array_for_report(pair)

    scope = load_analysis_scope(scenario)
    assert scope, "live workbook is expected to carry an analysis sheet"
    for cfg in scope:
        env = environment_for_phase(
            legacy, phase=cfg.phase, launch_config=cfg.launch,
            temperature_c=cfg.temperature_c, season=cfg.season,
            angle_alpha_deg=cfg.sun_angle_deg)
        if cfg.string_loss != 1.0:
            env = dataclasses.replace(env, current_loss=env.current_loss * cfg.string_loss)
        r_l = run(arr_legacy, env).array
        r_p = run(arr_pair, env).array
        for attr in ("isc", "voc", "v_mp", "i_mp", "p_mp"):
            assert np.isclose(getattr(r_l, attr), getattr(r_p, attr),
                              rtol=0, atol=1e-9), (cfg.label, attr)


def test_legacy_single_file_end_to_end(tmp_path):
    """build_electrical_report over the untouched params.xlsx still runs and
    reports the same phases (PDF may be None when pdflatex is absent)."""
    from powerpy.app import build_electrical_report
    pdf, phases, report = build_electrical_report(
        PARAMS, tmp_path / "out.pdf", data_dir=DATA, engine="analytic")
    assert phases == ["single@End_of_Life", "dual@End_of_Life"]
    assert report.document.doc_number
