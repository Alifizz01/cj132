"""Report structure -- which sections appear, in what order, of what type.

The workbook's ``structure`` sheet IS the table of contents of the
rendered report.  Every row is one section; the row's ``type`` column
tells the renderer what kind of content to inject (a paragraph, a
figure, a table, an equation list, ...).

Sheet columns (long-format)::

    include | id | title | description | type | ref

* **include**       TRUE / FALSE -- drop the row if FALSE
* **id**            slug; also the lookup key into the ``narrative``
                    sheet for prose-type rows
* **title**         the section heading rendered into the report
* **description**   a short blurb rendered under the heading (or used
                    as a figure caption suffix)
* **type**          one of ``section | figure | equations | symbols |
                    results_table | loss_table | cell_params``
* **ref**           for ``figure`` rows, the figure key the renderer
                    should embed (e.g. ``iv_string``); empty otherwise

An optional **audience** column may be added later for customer/
engineer filtering (defaults to ``BOTH`` if absent).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------- enums
class ContentType(str, Enum):
    """The kind of content a structure row represents."""

    SECTION       = "section"        # prose, pulled from narrative.id
    FIGURE        = "figure"         # embed a generated figure
    EQUATIONS     = "equations"      # render the equations sheet
    SYMBOLS       = "symbols"        # render the nomenclature sheet
    RESULTS_TABLE = "results_table"  # per-section / per-case results
    LOSS_TABLE    = "loss_table"     # render the losses sheet
    CELL_PARAMS   = "cell_params"    # render the effective cell parameters
    SECTIONS_TABLE = "sections_table"  # render the per-section layout/harness


class Audience(str, Enum):
    """Who a section is for.  ``BOTH`` always passes the filter."""

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
    type: ContentType
    ref: str = ""
    audience: Audience = Audience.BOTH
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

    def for_audience(self, audience: Audience | str | None) -> "ReportStructure":
        """Keep rows whose audience matches (``BOTH`` always passes)."""
        if audience is None:
            return self
        if isinstance(audience, str):
            audience = Audience(audience)
        return ReportStructure(tuple(
            s for s in self.sections
            if s.audience == audience or s.audience == Audience.BOTH
        ))

    def by_type(self, *types: ContentType) -> "ReportStructure":
        """Keep only rows of the given content types."""
        wanted = set(types)
        return ReportStructure(
            tuple(s for s in self.sections if s.type in wanted))

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
        """All ``ref`` values from rows of type FIGURE -- the figures
        the render layer is asked to produce."""
        return tuple(s.ref for s in self.sections
                     if s.type == ContentType.FIGURE and s.ref)

    def __iter__(self):
        return iter(self.sections)

    def __len__(self):
        return len(self.sections)

    def __bool__(self):
        return bool(self.sections)

    # ---------- defaults ----------
    @classmethod
    def default(cls) -> "ReportStructure":
        """Fallback used when the workbook has no ``structure`` sheet.

        Matches the canonical short layout: cell params, layout,
        losses, results, compliance.
        """
        rows = [
            ("cell_params",  "Effective Cell Parameters", "",
             ContentType.CELL_PARAMS,   ""),
            ("string_def",   "String and Section Definitions", "",
             ContentType.SECTION,       ""),
            ("loss_factor",  "Loss Factor Budget", "",
             ContentType.LOSS_TABLE,    ""),
            ("results",      "Results", "",
             ContentType.RESULTS_TABLE, ""),
        ]
        return cls(tuple(
            ReportSection(include=True, id=id_, title=title,
                          description=desc, type=ctype, ref=ref,
                          row_index=i + 1)
            for i, (id_, title, desc, ctype, ref) in enumerate(rows)
        ))
