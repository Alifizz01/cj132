"""High-level ThermalReport -- the thermal analogue of render.Report.

Typical use::

    from powerpy.output.thermal_report import ThermalReport
    from powerpy.analysis.thermal_report import ThermalCase
    pdf = (ThermalReport.from_metadata(report_meta, cases)
                        .render("build_thermal")
                        .compile_pdf("thermal.pdf"))

It reuses the shared AIRBUS preamble (``_preamble.tex.jinja``) and the same
compile pipeline as the electrical report.
"""
from __future__ import annotations

import importlib.resources as ir
import shutil
from dataclasses import dataclass
from pathlib import Path

from powerpy.analysis.thermal_report import (
    ThermalCase,
    ThermalReportData,
    run_thermal_report,
)
from powerpy.config.substrate import Substrate
from powerpy.output import thermal_figures as _figs
from powerpy.output.compile import compile_pdf, have_pdflatex
from powerpy.output.templating import make_environment
from powerpy.schemas import ReportMetadata


def _templates_dir() -> Path:
    with ir.as_file(ir.files("powerpy.output").joinpath("templates")) as p:
        return Path(p)


@dataclass
class ThermalReport:
    metadata: ReportMetadata
    data: ThermalReportData
    workspace: Path | None = None

    @classmethod
    def from_metadata(cls, metadata: ReportMetadata, cases: list[ThermalCase],
                      *, substrate: Substrate | str = "FSP-SFLA",
                      layout_file: str | None = None,
                      layout=None,
                      t_limit_c: float = 150.0,
                      efficiency: float = 0.30) -> "ThermalReport":
        data = run_thermal_report(metadata, cases, substrate=substrate,
                                  layout_file=layout_file, layout=layout,
                                  t_limit_c=t_limit_c, efficiency=efficiency)
        return cls(metadata=metadata, data=data)

    def render(self, workdir: str | Path, *,
               template: str = "thermal_report.tex.jinja",
               main_tex: str = "thermal_report.tex") -> "ThermalReport":
        workdir = Path(workdir).resolve()
        figs_dir = workdir / "figures"
        workdir.mkdir(parents=True, exist_ok=True)
        figs_dir.mkdir(exist_ok=True)
        self.workspace = workdir

        fig_path = figs_dir / "panel_thermal.png"
        _figs.panel_heatmap_figure(
            self.data.panel_grid_c, fig_path,
            title=f"Panel temperature map -- {self.data.panel_case_label}")
        panel_figure = fig_path.relative_to(workdir).as_posix()

        # layout map (cell vs bare/no-SCA) when a layout was supplied
        layout_figure = ""
        if self.data.layout is not None:
            from powerpy.output import layout_figures as _lfigs
            lp = figs_dir / "panel_layout.png"
            _lfigs.layout_map_figure(
                self.data.layout, lp, label_tiles=False,
                title="Panel layout -- SCA (cell) vs bare (no SCA)")
            layout_figure = lp.relative_to(workdir).as_posix()

        env = make_environment([_templates_dir()])
        tmpl = env.get_template(template)
        tex_out = tmpl.render(
            document=self.metadata.document,
            inputs=self.data.inputs,
            points=self.data.points,
            hotspot=self.data.hotspot,
            panel_figure=panel_figure,
            layout_figure=layout_figure,
            power_budget=self.data.power_budget,
        )
        (workdir / main_tex).write_text(tex_out, encoding="utf-8")
        return self

    def compile_pdf(self, out_pdf: str | Path | None = None, *,
                    main_tex: str = "thermal_report.tex") -> Path | None:
        if self.workspace is None:
            raise RuntimeError("call .render(...) before .compile_pdf(...)")
        if not have_pdflatex():
            print("[thermal] pdflatex not found; .tex workspace at "
                  + str(self.workspace))
            return None
        pdf = compile_pdf(self.workspace, main_tex=main_tex)
        if out_pdf is not None:
            out_pdf = Path(out_pdf).resolve()
            out_pdf.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(pdf, out_pdf)
            return out_pdf
        return pdf
