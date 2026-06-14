"""Load losses sheet (long-format)."""
from pathlib import Path

import pandas as pd

from powerpy.loader._common import (
    clean_optional,
    filter_included,
    parse_enum,
    require_float_in_range,
    validate_required_columns,
    validate_unique,
)
from powerpy.schemas._common import Phase, Level
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
            phase=parse_enum(row["phase"], Phase, "losses", excel_row, "phase"),
            value=require_float_in_range(
                row, "value", "losses", excel_row, lo=0, hi=1
            ),
            level=parse_enum(row["level"], Level, "losses", excel_row, "level"),
            description=clean_optional(row, "description"),
            source=clean_optional(row, "source"),
        ))

    validate_unique(items, lambda l: (l.name, l.phase), "losses")
    return LossCollection(items=tuple(items))
