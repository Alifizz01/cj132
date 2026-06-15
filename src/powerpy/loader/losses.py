"""Load losses sheet (long-format)."""
from pathlib import Path

import pandas as pd

from powerpy.loader._common import (
    clean_optional,
    filter_included,
    require_float_in_range,
    require_str,
    validate_required_columns,
    validate_unique,
)
from powerpy.schemas.losses import LossFactor, LossCollection


def load_losses(params_file: Path) -> LossCollection:
    df = pd.read_excel(params_file, sheet_name="losses")
    validate_required_columns(
        df,
        "losses",
        {"name", "phase", "value", "level", "include"},
    )
    df = filter_included(df, "losses")
    df = df.dropna(subset=["name"])

    items = []
    for idx, row in df.iterrows():
        excel_row = idx + 2
        items.append(LossFactor(
            name=str(row["name"]).strip(),
            phase=require_str(row, "phase", "losses", excel_row),
            value=require_float_in_range(
                row, "value", "losses", excel_row, lo=0, hi=1
            ),
            level=require_str(row, "level", "losses", excel_row),
            description=clean_optional(row, "description"),
            source=clean_optional(row, "source"),
        ))

    validate_unique(items, lambda l: (l.name, l.phase), "losses")
    return LossCollection(items=tuple(items))
