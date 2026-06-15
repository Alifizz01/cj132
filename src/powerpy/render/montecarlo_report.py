"""High-level MonteCarloReport -- worst-case thermal failure analysis.

Runs the auto-stopping Monte-Carlo failure study + greedy worst-case search
on a panel built from the cell/substrate JSONs, and renders an AIRBUS-style
PDF (peak-temperature distribution, over-limit probability, worst-case
cluster).  Reuses the shared preamble and compile pipeline.
"""
from __future__ import annotations

import importlib.resources as ir
import shutil
from dataclasses import dataclass
from pathlib import Path

from powerpy.analysis.montecarlo_report import MCReportData, run_mc_study
from powerpy.render import montecarlo_figures as _figs
from powerpy.render.compile import compile_pdf, have_pdflatex
from powerpy.render.templating import make_environment
from powerpy.schemas import ReportMetadata


def _templates_dir() -> Path:
    with ir.as_file(ir.files("powerpy.render").joinpath("templates")) as p:
        return Path(p)


@dataclass
class MonteCarloReport:
    metadata: ReportMetadata
    data: MCReportData
    workspace: Path | None = None

    @classmethod
    def from_metadata(cls, metadata: ReportMetadata, **study_kwargs
                      ) -> "MonteCarloReport":
        data = run_mc_study(metadata, **study_kwargs)
        return cls(metadata=metadata, data=data)

    def render(self, workdir: str | Path, *,
               template: str = "montecarlo_report.tex.jinja",
               main_tex: str = "montecarlo_report.tex") -> "MonteCarloReport":
        workdir = Path(workdir).resolve()
        figs_dir = workdir / "figures"
        workdir.mkdir(parents=True, exist_ok=True)
        figs_dir.mkdir(exist_ok=True)
        self.workspace = workdir

        fig_path = figs_dir / "mc_hist.png"
        _figs.peak_temp_hist_figure(
            self.data.peaks, fig_path, t_limit_c=self.data.t_limit_c,
            mean_c=self.data.summary.get("mean_peak_c"))
        hist_figure = fig_path.relative_to(workdir).as_posix()

        # worst-case temperature map
        worst_figure = ""
        if self.data.worst_grid is not None:
            from powerpy.render.thermal_figures import panel_heatmap_figure
            wp = figs_dir / "mc_worst.png"
            panel_heatmap_figure(
                self.data.worst_grid, wp,
                title=f"Worst case: {len(self.data.worst['failed'])} failed "
                      f"cells -> peak {self.data.worst['peak_t_c']:.0f} °C")
            worst_figure = wp.relative_to(workdir).as_posix()

        env = make_environment([_templates_dir()])
        tmpl = env.get_template(template)
        tex_out = tmpl.render(
            document=self.metadata.document,
            inputs=self.data.inputs,
            summary=self.data.summary,
            p_over_limit=self.data.p_over_limit,
            worst=self.data.worst,
            hist_figure=hist_figure,
            worst_figure=worst_figure,
            power_budget=self.data.power_budget,
        )
        (workdir / main_tex).write_text(tex_out, encoding="utf-8")
        return self

    def compile_pdf(self, out_pdf: str | Path | None = None, *,
                    main_tex: str = "montecarlo_report.tex") -> Path | None:
        if self.workspace is None:
            raise RuntimeError("call .render(...) before .compile_pdf(...)")
        if not have_pdflatex():
            print("[mc] pdflatex not found; .tex workspace at "
                  + str(self.workspace))
            return None
        pdf = compile_pdf(self.workspace, main_tex=main_tex)
        if out_pdf is not None:
            out_pdf = Path(out_pdf).resolve()
            out_pdf.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(pdf, out_pdf)
            return out_pdf
        return pdf
