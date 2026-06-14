"""Load radiation_fluxes sheet (long-format)."""
from pathlib import Path

import pandas as pd

from powerpy.loader._common import (
    clean_optional,
    filter_included,
    parse_enum,
    require_float,
    validate_required_columns,
    validate_unique,
)
from powerpy.schemas._common import Phase
from powerpy.schemas.fluxes import (
    FluxParam,
    LaunchConfig,
    RadiationFlux,
    RadiationFluxCollection,
)


def load_radiation_fluxes(params_file: Path) -> RadiationFluxCollection:
    df = pd.read_excel(params_file, sheet_name="radiation_fluxes")
    validate_required_columns(
        df,
        "radiation_fluxes",
        {"name", "launch_config", "phase", "param", "value", "include"},
    )
    df = filter_included(df, "radiation_fluxes")
    df = df.dropna(subset=["name"])

    items = []
    for idx, row in df.iterrows():
        excel_row = idx + 2

        value = require_float(row, "value", "radiation_fluxes", excel_row)
        if value <= 0:
            raise ValueError(
                f"radiation_fluxes:row {excel_row}: value={value} must be positive"
            )

        items.append(RadiationFlux(
            name=str(row["name"]).strip(),
            launch_config=parse_enum(
                row["launch_config"], LaunchConfig,
                "radiation_fluxes", excel_row, "launch_config",
            ),
            phase=parse_enum(
                row["phase"], Phase,
                "radiation_fluxes", excel_row, "phase",
            ),
            param=parse_enum(
                row["param"], FluxParam,
                "radiation_fluxes", excel_row, "param",
            ),
            value=value,
            unit=clean_optional(row, "unit") or "e/cm2",
            source=clean_optional(row, "source"),
        ))

    validate_unique(
        items,
        lambda f: (f.name, f.launch_config, f.phase, f.param),
        "radiation_fluxes",
    )
    return RadiationFluxCollection(items=tuple(items))
