"""Load the narrative sheet (long-format: id | paragraph)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from powerpy.loader._common import validate_required_columns
from powerpy.schemas.narrative import NarrativeBook, NarrativeParagraph


REQUIRED_COLUMNS = {"id", "paragraph"}


def load_narrative(
    params_file: Path,
    *,
    sheet_name: str = "narrative",
) -> NarrativeBook:
    """Load the narrative sheet.

    Returns an empty book if the sheet is missing -- the report will
    still render, just without prose under section-type rows.
    """
    try:
        df = pd.read_excel(params_file, sheet_name=sheet_name)
    except ValueError:
        return NarrativeBook.empty()

    validate_required_columns(df, sheet_name, REQUIRED_COLUMNS)
    df = df.dropna(subset=["id"])
    df = df.dropna(subset=["paragraph"])

    items: list[NarrativeParagraph] = []
    for idx, row in df.iterrows():
        excel_row = int(idx) + 2
        items.append(NarrativeParagraph(
            id=str(row["id"]).strip(),
            paragraph=str(row["paragraph"]).strip(),
            row_index=excel_row,
        ))
    return NarrativeBook(tuple(items))
