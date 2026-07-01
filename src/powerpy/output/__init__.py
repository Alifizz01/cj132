"""The ONE output package: every result format the framework emits.

Public API::

    from powerpy.output import Report              # electrical LaTeX -> PDF
    pdf = (Report.from_results(metadata, cases, requirement_w=7550.0)
                 .render(workdir="./build")
                 .compile_pdf("g2g_eol.pdf"))

    from powerpy.output import panel_report        # thermal HTML heat-map + JSON
    from powerpy.output import write_results_xlsx  # use case B's results.xlsx

Sibling PDF builders: ``powerpy.output.thermal_report.ThermalReport`` and
``powerpy.output.montecarlo_report.MonteCarloReport``.

Lower-level building blocks:

* ``powerpy.output.templating`` -- the Jinja2 environment factory + templates_dir
* ``powerpy.output.figures``    -- matplotlib figure builders
* ``powerpy.output.compile``    -- the pdflatex subprocess wrapper
"""
from __future__ import annotations

from powerpy.output.compile import (CompileError, compile_pdf,
                                    compile_workspace_pdf, have_pdflatex)
from powerpy.output.excel import write_results_xlsx
from powerpy.output.html import panel_report, write_html, write_json
from powerpy.output.report import Report
from powerpy.output.templating import escape_tex, make_environment, num, templates_dir

__all__ = [
    "Report",
    "panel_report",
    "write_html",
    "write_json",
    "write_results_xlsx",
    "CompileError",
    "compile_pdf",
    "compile_workspace_pdf",
    "have_pdflatex",
    "escape_tex",
    "make_environment",
    "num",
    "templates_dir",
]
