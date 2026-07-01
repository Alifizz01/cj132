"""High-level MonteCarloReport -- worst-case thermal failure analysis.

Runs the auto-stopping Monte-Carlo failure study + greedy worst-case search
on a panel built from the cell/substrate JSONs, and renders an AIRBUS-style
PDF (peak-temperature distribution, over-limit probability, worst-case
cluster).  Reuses the shared preamble and compile pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from powerpy.analysis.montecarlo_report import MCReportData, run_mc_study
from powerpy.output import montecarlo_figures as _figs
from powerpy.output.compile import compile_workspace_pdf
from powerpy.output.templating import make_environment, templates_dir
from powerpy.schemas import ReportMetadata


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
            from powerpy.output.thermal_figures import panel_heatmap_figure
            wp = figs_dir / "mc_worst.png"
            panel_heatmap_figure(
                self.data.worst_grid, wp,
                title=f"Worst case: {len(self.data.worst['failed'])} failed "
                      f"cells -> peak {self.data.worst['peak_t_c']:.0f} °C")
            worst_figure = wp.relative_to(workdir).as_posix()

        env = make_environment([templates_dir()])
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
        return compile_workspace_pdf(self.workspace, out_pdf,
                                     main_tex=main_tex, tag="mc")
