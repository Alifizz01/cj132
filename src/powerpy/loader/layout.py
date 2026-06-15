"""Load the array layout from the ``sections`` sheet.

Each row is one PHYSICAL section -- it carries its own harness ``resistance``
(which varies with distance from the yoke) and explicit ``wing_id``/``panel_id``,
so the array is enumerated directly (no separate topology/panels sheets).
"""
from pathlib import Path

import pandas as pd

from powerpy.loader._common import (
    filter_included,
    require_float,
    require_positive_int,
    validate_required_columns,
    validate_unique,
)
from powerpy.schemas.layout import (
    ArrayLayout,
    PhysicalSection,
    SectionType,
    Topology,
)


def load_array_layout(params_file: Path) -> ArrayLayout:
    df = pd.read_excel(params_file, sheet_name="sections")
    validate_required_columns(
        df, "sections",
        {"section_ref", "section_id", "wing_id", "panel_id",
         "n_strings_parallel", "resistance", "n_scas_series_per_string",
         "include"},
    )
    df = filter_included(df, "sections")

    types: dict = {}
    physical: list[PhysicalSection] = []
    wings, panels_per_wing = set(), {}
    for idx, row in df.iterrows():
        excel_row = idx + 2
        sid = str(row["section_id"]).strip()
        n_par = require_positive_int(row, "n_strings_parallel", "sections", excel_row)
        n_ser = require_positive_int(row, "n_scas_series_per_string", "sections", excel_row)
        res = require_float(row, "resistance", "sections", excel_row)
        wing = str(int(row["wing_id"]))
        panel = str(int(row["panel_id"]))
        ref = str(row["section_ref"]).strip()

        key = (sid, n_par, n_ser)
        if key not in types:
            types[key] = SectionType(section_id=sid, section_name=sid,
                                     n_strings_parallel=n_par,
                                     n_sca_series_per_string=n_ser)
        physical.append(PhysicalSection(
            section_type=types[key],
            wing_id=f"wing_{wing}",
            panel_id=f"wing_{wing}.panel_{panel}",
            instance_id=ref,
            resistance_ohm=res,
        ))
        wings.add(wing)
        panels_per_wing.setdefault(wing, set()).add(panel)

    validate_unique(physical, lambda p: p.instance_id, "sections")
    n_panels = max((len(p) for p in panels_per_wing.values()), default=1)
    topology = Topology(n_wings=max(len(wings), 1), n_panels_per_wing=n_panels)
    return ArrayLayout(
        section_types=tuple(types.values()),
        topology=topology,
        physical_sections=tuple(physical),
    )
