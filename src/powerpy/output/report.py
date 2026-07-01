"""High-level Report -- the one object you build from results.

Typical use::

    from powerpy.output import Report
    pdf = (Report.from_results(report_meta, case_results,
                                requirement_w=7550.0)
                 .render(workdir="./build")
                 .compile_pdf("solar_array_eol.pdf"))

A Report owns a workspace directory; rendering writes a ``report.tex``
plus a ``figures/`` folder; compiling runs pdflatex twice and copies
the resulting PDF out.

Section types and which figures they need come from the workbook's
``structure`` sheet, not from this file.  The render layer is purely a
dispatcher.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from powerpy.schemas import (
    ReportMetadata,
    ReportStructure,
)
# NOTE: the simulation engine (and its legacy cell/electric chain) is imported
# LAZILY inside from_results(build_array=True). With `from __future__ import
# annotations`, the ArrayModel/CaseResult type hints are strings, so a CONFIG-ONLY
# report (build_array=False) renders without importing the simulation engine.

from powerpy.output import figures as _figs
from powerpy.output.compile import compile_workspace_pdf
from powerpy.output.templating import make_environment, templates_dir


# ---------------------------------------------------------------- figure dispatch
def _figure_builders(array: ArrayModel, cases: list[CaseResult],
                     requirement_w: float | None,
                     array_layout=None, cell=None
                     ) -> dict[str, Callable[[Path], Path]]:
    """Return a dict mapping figure-ref keys -> a builder taking out_path.

    Add a new figure type by registering one entry here.  Anything the
    structure sheet asks for via a ``figure`` row is looked up in this
    dict; if the key is missing the figure section emits a polite
    placeholder rather than crashing.
    """
    # default operating condition for "static" figures (first case if any)
    if cases:
        env_for_static = cases[0].environment
        bus_v = cases[0].bus.bus_voltage_v if cases[0].bus else None
    else:
        env_for_static = None
        bus_v = None

    def _array_iv(out):
        if env_for_static is not None:
            array.apply(env_for_static)
        return _figs.iv_pv_figure(
            array, out, bus_voltage_v=bus_v,
            requirement_w=requirement_w,
            title="Whole-array I-V / P-V")

    def _sections_grid(out):
        if env_for_static is not None:
            array.apply(env_for_static)
        return _figs.sections_grid_figure(
            array, out, bus_voltage_v=bus_v,
            title="Per-section I-V / P-V")

    def _string_iv(out):
        # one representative string -- pick the first cell of the first
        # section of the first panel
        if env_for_static is not None:
            array.apply(env_for_static)
        try:
            string = array.panels[0].sections[0].strings[0]
        except (AttributeError, IndexError):
            raise RuntimeError("string_iv: cannot find a representative "
                               "string in the array")
        # wrap the string in a minimal "array of one section of one
        # string" so iv_pv_figure works unchanged
        from powerpy.simulation import (PanelModel, SectionModel)
        single_section = SectionModel([string], name="representative_string")
        single_panel = PanelModel([single_section], name="representative_panel")
        from powerpy.simulation import ArrayModel as _Array
        single_array = _Array([single_panel], name="representative")
        return _figs.iv_pv_figure(
            single_array, out, bus_voltage_v=None,
            requirement_w=None,
            title="Cell-block (representative string) I-V / P-V")

    def _compliance(out):
        return _figs.case_compliance_figure(
            cases, out, requirement_w=requirement_w,
            title="Bus power vs. requirement (all cases)")

    def _panel_layout(out):
        from powerpy.output import layout_figures as _lfigs
        secs = array_layout.section_types if array_layout is not None else None
        if not secs:
            raise RuntimeError("panel_layout: no section types in array_layout")
        return _lfigs.panel_schematic_figure(
            secs, out, title="Panel layout -- sections, parallel strings, harness")

    def _cell_regressors(out):
        regs = getattr(cell.electrical, "regressors", None) if cell else None
        if not regs:
            raise RuntimeError("cell_regressors: cell has no regressor curves")
        return _figs.cell_regressors_figure(
            regs, out, title="Cell radiation regressors")

    def _missing(name: str):
        def _miss(out):
            raise RuntimeError(f"figure builder '{name}' is not "
                               "registered yet; add it to "
                               "_figure_builders() in render/report.py")
        return _miss

    return {
        "iv_panel":         _array_iv,
        "iv_sections":      _sections_grid,
        "iv_string":        _string_iv,
        "compliance":       _compliance,
        "panel_layout":     _panel_layout,
        "cell_regressors":  _cell_regressors,
    }


# ---------------------------------------------------------------- Report
@dataclass
class Report:
    metadata: ReportMetadata
    cases: list[CaseResult]
    array: ArrayModel
    requirement_w: float | None = None
    workspace: Path | None = None

    # ---- factories ----
    @classmethod
    def from_results(
        cls,
        metadata: ReportMetadata,
        cases: Iterable[CaseResult],
        *,
        array: "ArrayModel | None" = None,
        requirement_w: float | None = None,
        build_array: bool = True,
        iv_engine: str = "analytic",
    ) -> "Report":
        cases = list(cases)
        if array is None and build_array:
            from powerpy.simulation import build_from_report   # lazy: needs the cell engine
            array = build_from_report(metadata, iv_engine=iv_engine)
        return cls(metadata=metadata, cases=cases, array=array,
                   requirement_w=requirement_w)

    # ---- main steps ----
    def render(self, workdir: str | Path,
               *, template: str = "report.tex.jinja",
               main_tex: str = "report.tex",
               audience: str | None = None) -> "Report":
        """Render the .tex workspace.  Returns self for chaining."""
        workdir = Path(workdir).resolve()
        figs_dir = workdir / "figures"
        workdir.mkdir(parents=True, exist_ok=True)
        figs_dir.mkdir(exist_ok=True)
        self.workspace = workdir

        # filter the structure for this audience, but PRESERVE row order
        # from the workbook -- the user-authored order IS the section
        # order.  for_audience() preserves it; included() preserves it.
        structure: ReportStructure = (self.metadata.structure
                                      .included()
                                      .for_audience(audience))
        audience_label = audience or "full"

        # build only the figures the structure actually asks for
        builders = _figure_builders(self.array, self.cases,
                                    self.requirement_w,
                                    self.metadata.array_layout,
                                    self.metadata.cell)
        figures: dict[str, str] = {}
        for ref in structure.figure_refs():
            build = builders.get(ref)
            if build is None:
                # leave it missing -- the template emits a placeholder
                continue
            out_path = figs_dir / f"{ref}.png"
            try:
                build(out_path)
                figures[ref] = out_path.relative_to(workdir).as_posix()
            except Exception as e:
                print(f"[render] WARNING: figure '{ref}' not built: {e}")

        # render the master template
        env = make_environment([templates_dir()])
        tmpl = env.get_template(template)
        ctx = dict(
            document=self.metadata.document,
            mission=self.metadata.mission,
            cell=self.metadata.cell,
            layout=self.metadata.array_layout,
            losses=list(self.metadata.losses),
            cases=self.cases,
            requirement_w=self.requirement_w,
            structure=structure,
            audience=audience_label,
            figures=figures,
            # placeholders -- equations / symbols loaders not built yet
            equations=[],
            symbols=[],
            # template legacy: results.tex.jinja used these names
            case_figures=[],
            has_compliance=False,
            compliance_figure="",
        )
        tex_out = tmpl.render(**ctx)
        (workdir / main_tex).write_text(tex_out, encoding="utf-8")
        return self

    def compile_pdf(self, out_pdf: str | Path | None = None,
                    *, main_tex: str = "report.tex") -> Path | None:
        """Compile the workspace into a PDF (None when pdflatex is absent)."""
        return compile_workspace_pdf(self.workspace, out_pdf,
                                     main_tex=main_tex, tag="report")
