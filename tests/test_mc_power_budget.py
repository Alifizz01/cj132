"""Monte-Carlo report: environmental power budget."""
from pathlib import Path

import pytest

from powerpy.loader.report import load_report_data
from powerpy.analysis.montecarlo_report import run_mc_study

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params.xlsx"
DATA = ROOT / "src" / "powerpy" / "data"

needs_params = pytest.mark.skipif(
    not PARAMS.exists(), reason="params.xlsx not present")


@needs_params
def test_mc_report_has_power_budget():
    md = load_report_data(PARAMS, DATA)
    d = run_mc_study(md, n_rows=4, n_cols=4, max_runs=10, target_se=99.0,
                     season=0.967, workers=1, seed=0)
    assert d.power_budget is not None
    assert d.power_budget.electrical_w_m2 > 0
    assert 0 < d.power_budget.albedo_w_m2 < 50
    assert 0 < d.power_budget.ir_w_m2 < 50
