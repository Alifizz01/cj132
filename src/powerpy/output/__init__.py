"""LaTeX templating and PDF compilation.

Public API::

    from powerpy.output import Report
    pdf = (Report.from_results(metadata, cases, requirement_w=7550.0)
                 .render(workdir="./build")
                 .compile_pdf("g2g_eol.pdf"))

Lower-level building blocks:

* ``powerpy.output.templating`` -- the Jinja2 environment factory
* ``powerpy.output.figures``    -- matplotlib figure builders
* ``powerpy.output.compile``    -- the pdflatex subprocess wrapper
"""
from __future__ import annotations

from powerpy.output.compile import CompileError, compile_pdf, have_pdflatex
from powerpy.output.report import Report
from powerpy.output.templating import escape_tex, make_environment, num

__all__ = [
    "Report",
    "CompileError",
    "compile_pdf",
    "have_pdflatex",
    "escape_tex",
    "make_environment",
    "num",
]
