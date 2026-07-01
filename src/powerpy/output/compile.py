"""pdflatex wrapper -- compile a .tex workspace into a PDF.

Runs pdflatex twice so the table of contents and cross-references
resolve.  Captures stderr/stdout so a failure is loud and located.
The compile step is optional; the rest of the render pipeline still
produces a valid .tex workspace when pdflatex is unavailable.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class CompileError(RuntimeError):
    """pdflatex returned a non-zero exit code."""


def have_pdflatex() -> bool:
    return shutil.which("pdflatex") is not None


def compile_pdf(workspace_dir: Path, main_tex: str = "report.tex",
                *, passes: int = 2,
                pdflatex: str = "pdflatex") -> Path:
    """Compile ``workspace_dir/main_tex`` to a PDF, return the path.

    Raises :class:`CompileError` on failure -- never silently produces
    an outdated PDF.  Use :func:`have_pdflatex` first if you want a
    soft fall-through on machines without a TeX install.
    """
    workspace = Path(workspace_dir)
    if not (workspace / main_tex).exists():
        raise FileNotFoundError(workspace / main_tex)
    if shutil.which(pdflatex) is None:
        raise CompileError(
            f"{pdflatex} not found on PATH. Install a TeX distribution "
            f"(MiKTeX or TeX Live) or set pdflatex='full/path/to/pdflatex'."
        )

    log_tail = ""
    for i in range(passes):
        proc = subprocess.run(
            [pdflatex, "-interaction=nonstopmode",
             "-halt-on-error",
             "-output-directory", str(workspace),
             main_tex],
            cwd=str(workspace),
            capture_output=True, text=True, timeout=180,
        )
        log_tail = (proc.stdout or "")[-1500:]
        if proc.returncode != 0:
            raise CompileError(
                f"pdflatex pass {i + 1} failed (exit "
                f"{proc.returncode}).\nlast 1500 chars of stdout:\n"
                f"{log_tail}"
            )

    pdf_path = workspace / (Path(main_tex).stem + ".pdf")
    if not pdf_path.exists():
        raise CompileError(
            f"pdflatex finished but {pdf_path} was not produced.\n"
            f"last 1500 chars of stdout:\n{log_tail}"
        )
    return pdf_path


def compile_workspace_pdf(workspace: Path | None, out_pdf=None, *,
                          main_tex: str = "report.tex",
                          tag: str = "output") -> Path | None:
    """The shared compile-and-copy tail every PDF report class delegates to.

    Returns the produced PDF path (copied to ``out_pdf`` when given), or
    ``None`` when pdflatex is unavailable -- the .tex workspace stays valid.
    """
    if workspace is None:
        raise RuntimeError("call .render(...) before .compile_pdf(...)")
    if not have_pdflatex():
        print("[%s] pdflatex not found; .tex workspace at %s" % (tag, workspace))
        return None
    pdf = compile_pdf(workspace, main_tex=main_tex)
    if out_pdf is not None:
        out_pdf = Path(out_pdf).resolve()
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(pdf, out_pdf)
        return out_pdf
    return pdf
