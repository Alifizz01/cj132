"""Report structure -- which sections appear, in what order, of what type.

The workbook's ``structure`` sheet IS the table of contents of the rendered
report.  Every row is one section; the row's ``type`` column tells the renderer
what kind of content to inject (a figure, a table, an equation list, ...).

Sheet columns (long-format)::

    include | id | title | description | type | ref

* **include**       TRUE / FALSE -- drop the row if FALSE
* **id**            slug
* **title**         the section heading rendered into the report
* **description**   a short blurb rendered under the heading (or used
                    as a figure caption suffix)
* **type**          one of ``figure | cell_params | sections_table |
                    loss_table | results_table | equations | symbols``
* **ref**           for ``figure`` rows, the figure key the renderer
                    should embed (e.g. ``iv_panel``); empty otherwise

An optional **audience** column may be added for customer/engineer filtering
(defaults to ``both`` if absent).

``type`` and ``audience`` are plain strings, not enums; the constants below are
just the framework's known render-dispatch keys.
"""
from __future__ import annotations

from dataclasses import dataclass

from powerpy.schemas._common import norm


# ------------------------------------------------ render-dispatch vocabularies
class ContentType:
    """Known content types (plain str). A row whose type is not one of these
    renders a polite placeholder rather than crashing."""
    FIGURE        = "figure"         # embed a generated figure
    EQUATIONS     = "equations"      # render the equations sheet
    SYMBOLS       = "symbols"        # render the nomenclature sheet
    RESULTS_TABLE = "results_table"  # per-section / per-case results
    LOSS_TABLE    = "loss_table"     # render the losses sheet
    CELL_PARAMS   = "cell_params"    # render the cell parameters
    SECTIONS_TABLE = "sections_table"  # render the per-section layout/harness


class Audience:
    """Who a section is for (plain str). ``both`` always passes the filter."""
    CUSTOMER = "customer"
    ENGINEER = "engineer"
    BOTH     = "both"


# ---------------------------------------------------------------- dataclasses
@dataclass(frozen=True)
class ReportSection:
    """One row of the structure sheet."""

    include: bool
    id: str
    title: str
    description: str
    type: str
    ref: str = ""
    audience: str = Audience.BOTH
    # row index from the workbook -- preserves the user's authored order
    row_index: int = 0


@dataclass(frozen=True)
class ReportStructure:
    """An ordered, filterable collection of report sections.

    Order is the order the rows appear in the workbook.  Filters
    return new ``ReportStructure`` objects rather than mutating.
    """

    sections: tuple[ReportSection, ...]

    # ---------- filters ----------
    def included(self) -> "ReportStructure":
        """Keep only rows where ``include`` is True."""
        return ReportStructure(
            tuple(s for s in self.sections if s.include))

    def for_audience(self, audience: str | None) -> "ReportStructure":
        """Keep rows whose audience matches (``both`` always passes)."""
        if audience is None:
            return self
        want = norm(audience)
        return ReportStructure(tuple(
            s for s in self.sections
            if norm(s.audience) == want or norm(s.audience) == Audience.BOTH
        ))

    def by_type(self, *types: str) -> "ReportStructure":
        """Keep only rows of the given content types."""
        wanted = {norm(t) for t in types}
        return ReportStructure(
            tuple(s for s in self.sections if norm(s.type) in wanted))

    # ---------- ergonomics ----------
    def find(self, id: str) -> ReportSection | None:
        for s in self.sections:
            if s.id == id:
                return s
        return None

    def has(self, id: str) -> bool:
        return self.find(id) is not None

    def ids(self) -> tuple[str, ...]:
        return tuple(s.id for s in self.sections)

    def figure_refs(self) -> tuple[str, ...]:
        """All ``ref`` values from rows of type ``figure`` -- the figures
        the render layer is asked to produce."""
        return tuple(s.ref for s in self.sections
                     if norm(s.type) == ContentType.FIGURE and s.ref)

    def __iter__(self):
        return iter(self.sections)

    def __len__(self):
        return len(self.sections)

    def __bool__(self):
        return bool(self.sections)

    # ---------- defaults ----------
    @classmethod
    def default(cls) -> "ReportStructure":
        """Fallback used when the workbook has no ``structure`` sheet:
        cell params, loss budget, results."""
        rows = [
            ("cell_params", "Cell Parameters", "", ContentType.CELL_PARAMS, ""),
            ("loss_budget", "Loss Factor Budget", "", ContentType.LOSS_TABLE, ""),
            ("results", "Results", "", ContentType.RESULTS_TABLE, ""),
        ]
        return cls(tuple(
            ReportSection(include=True, id=id_, title=title,
                          description=desc, type=ctype, ref=ref,
                          row_index=i + 1)
            for i, (id_, title, desc, ctype, ref) in enumerate(rows)
        ))
