"""Load the report-structure sheet (long-format).

Expected columns -- matches the actual workbook layout::

    include | id | title | description | type | ref

Optional columns:

    audience       -- one of `customer | engineer | both` (default `both`)

The sheet's row order is preserved as the rendered section order.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from powerpy.loader._common import (
    clean_optional,
    require_str,
    to_bool,
    validate_required_columns,
    validate_unique,
)
from powerpy.schemas.structure import (
    Audience,
    ReportSection,
    ReportStructure,
)


REQUIRED_COLUMNS = {"include", "id", "title", "description", "type"}


def load_report_structure(
    params_file: Path,
    *,
    sheet_name: str = "structure",
) -> ReportStructure:
    """Load the structure sheet.

    Returns :meth:`ReportStructure.default` if the sheet is missing.
    """
    try:
        df = pd.read_excel(params_file, sheet_name=sheet_name)
    except ValueError:
        return ReportStructure.default()

    validate_required_columns(df, sheet_name, REQUIRED_COLUMNS)
    df = df.dropna(subset=["id"])

    items: list[ReportSection] = []
    for idx, row in df.iterrows():
        excel_row = int(idx) + 2
        ctype = require_str(row, "type", sheet_name, excel_row)

        # audience is optional -- default 'both' if column missing/blank
        if "audience" in df.columns and not pd.isna(row.get("audience")):
            audience = str(row["audience"]).strip()
        else:
            audience = Audience.BOTH

        items.append(ReportSection(
            include=to_bool(row["include"]),
            id=str(row["id"]).strip(),
            title=str(row["title"]).strip()
                  if not pd.isna(row["title"]) else "",
            description=str(row["description"]).strip()
                        if not pd.isna(row["description"]) else "",
            type=ctype,
            ref=clean_optional(row, "ref"),
            audience=audience,
            row_index=excel_row,
        ))

    validate_unique(items, key_fn=lambda s: s.id, sheet_name=sheet_name)
    return ReportStructure(tuple(items))
