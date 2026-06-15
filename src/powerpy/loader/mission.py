"""Load mission_params sheet (long-format).

The mission_params sheet contains operating point values indexed by
launch_config and phase, with columns:

    name | launch_config | phase | value | unit | source | description | include

Example rows:
    bus_voltage | single | End_of_LEOP | 105.5 | V | ... | TRUE
    req_power | single | End_of_Life | 8350 | W | ... | TRUE
    pva_temperature | single | End_of_Life | 51.1 | C | ... | TRUE
"""
from pathlib import Path

import pandas as pd

from powerpy.loader._common import (
    clean_optional,
    filter_included,
    require_float,
    require_str,
    validate_required_columns,
    validate_unique,
)
from powerpy.schemas.mission import MissionOperatingPoint, MissionParameters


def load_mission_parameters(params_file: Path) -> MissionParameters:
    """Load mission_params sheet (long-format)."""
    df = pd.read_excel(params_file, sheet_name="mission_param")
    validate_required_columns(
        df,
        "mission_param",
        {"name", "launch_config", "phase", "value", "unit", "include"},
    )
    df = filter_included(df, "mission_param")
    df = df.dropna(subset=["name"])

    items = []
    for idx, row in df.iterrows():
        excel_row = idx + 2

        value = require_float(row, "value", "mission_param", excel_row)

        items.append(MissionOperatingPoint(
            name=str(row["name"]).strip(),
            launch_config=require_str(row, "launch_config", "mission_param", excel_row),
            phase=require_str(row, "phase", "mission_param", excel_row),
            value=value,
            unit=clean_optional(row, "unit"),
            source=clean_optional(row, "source"),
            description=clean_optional(row, "description"),
        ))

    validate_unique(
        items,
        lambda m: (m.name, m.launch_config, m.phase),
        "mission_param",
    )
    return MissionParameters(items=tuple(items))
