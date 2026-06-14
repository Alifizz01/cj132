"""LaTeX templating and PDF compilation.

Public API::

    from powerpy.render import Report
    pdf = (Report.from_results(metadata, cases, requirement_w=7550.0)
                 .render(workdir="./build")
                 .compile_pdf("g2g_eol.pdf"))

Lower-level building blocks:

* ``powerpy.render.templating`` -- the Jinja2 environment factory
* ``powerpy.render.figures``    -- matplotlib figure builders
* ``powerpy.render.compile``    -- the pdflatex subprocess wrapper
"""
from __future__ import annotations

from powerpy.render.compile import CompileError, compile_pdf, have_pdflatex
from powerpy.render.report import Report
from powerpy.render.templating import escape_tex, make_environment, num

__all__ = [
    "Report",
    "CompileError",
    "compile_pdf",
    "have_pdflatex",
    "escape_tex",
    "make_environment",
    "num",
]
