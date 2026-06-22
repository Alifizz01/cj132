"""Build the report's ArrayModel through the single spec builder.

Mirrors the dispatch order of the legacy app.py::_build_array (circuit ref ->
grid ref -> report sections), but routes every kind through
spec_adapt + build_array_from_spec so there is one assembly path.
"""
from __future__ import annotations

from powerpy.config.layout import load_layout
from powerpy.loader.circuit import load_circuit
from powerpy.simulation.array_level import ArrayModel
from powerpy.simulation.spec_adapt import adapt_circuit, adapt_grid, adapt_sections
from powerpy.simulation.spec_build import build_array_from_spec


def build_array_for_report(report, *, grid_file: str | None = None,
                           iv_engine: str = "analytic",
                           sections_only: bool = False) -> ArrayModel:
    """Return the report array, assembled via build_array_from_spec.

    Dispatch (unchanged from the legacy builder): a free-form circuit JSON if the
    cell references one; else a grid (grid-as-single-source) when referenced or
    passed via ``grid_file``; otherwise the report's section layout.

    ``sections_only=True`` forces the report's section layout regardless of any
    grid/circuit reference on the cell -- this preserves the legacy
    no-analysis-sheet fallback, which always used the sections and honoured a
    grid only on the scope-driven path.
    """
    string_shunt_vf = (report.cell.string_diode.v_forward
                       if getattr(report.cell, "string_diode", None) else None)

    if sections_only:
        spec = adapt_sections(report.array_layout)
    else:
        circuit_ref = getattr(report.cell, "circuit_reference_file", None)
        if circuit_ref:
            spec = adapt_circuit(load_circuit(circuit_ref))
        else:
            grid_ref = grid_file or getattr(report.cell, "grid_reference_file", None)
            if grid_ref:
                spec = adapt_grid(load_layout(grid_ref))
            else:
                spec = adapt_sections(report.array_layout)

    return build_array_from_spec(report.cell, spec, iv_engine=iv_engine,
                                 string_shunt_vf=string_shunt_vf)
