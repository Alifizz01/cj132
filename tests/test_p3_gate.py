"""Phase-3 gate: one output package, no stragglers.

The byte gates (report.tex, results.xlsx values, panel HTML/JSON vs the pre-P3
baselines) were run during the phase; this file pins the structural facts.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "powerpy"


def test_no_render_or_reporting_references_left_in_src():
    stale = []
    for p in SRC.rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="replace")
        if "powerpy.render" in text or "powerpy.reporting" in text:
            stale.append(str(p.relative_to(ROOT)))
    assert not stale, stale


def test_old_packages_are_gone_and_store_is_dead():
    assert not (SRC / "render").exists()
    assert not (SRC / "reporting").exists()
    assert not (SRC / "reporting" / "store.py").exists()


def test_output_package_exports_all_three_faces():
    from powerpy.output import Report, panel_report, write_results_xlsx  # noqa: F401
    from powerpy.output.compile import compile_workspace_pdf  # noqa: F401
    from powerpy.output.templating import templates_dir
    assert (templates_dir() / "report.tex.jinja").exists()
