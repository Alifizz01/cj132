"""Load the array layout: section types template, topology, and panel overrides.

Expansion is done in Python: section_types × topology = physical_sections.
"""
from pathlib import Path

import pandas as pd

from powerpy.loader._common import (
    clean_optional,
    filter_included,
    optional_int,
    require_float,
    require_positive_int,
    validate_required_columns,
    validate_unique,
)
from powerpy.schemas.layout import (
    ArrayLayout,
    PanelOverride,
    PhysicalSection,
    SectionType,
    Topology,
)


def load_array_layout(params_file: Path) -> ArrayLayout:
    """Load the array layout from the ``sections`` sheet.

    Each row is one PHYSICAL section, with its own harness ``resistance`` (which
    varies with distance from the yoke) and explicit ``wing_id``/``panel_id`` --
    so the array is enumerated directly, no separate topology/panels sheets.
    """
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


def load_section_types(params_file: Path) -> tuple[SectionType, ...]:
    df = pd.read_excel(params_file, sheet_name="sections")
    validate_required_columns(
        df,
        "sections",
        {"section_id", "section_name", "n_strings_parallel",
         "n_sca_series_per_string", "include"},
    )
    df = filter_included(df, "sections")

    items = []
    for idx, row in df.iterrows():
        excel_row = idx + 2
        items.append(SectionType(
            section_id=str(row["section_id"]).strip(),
            section_name=str(row["section_name"]).strip(),
            n_strings_parallel=require_positive_int(
                row, "n_strings_parallel", "sections", excel_row
            ),
            n_sca_series_per_string=require_positive_int(
                row, "n_sca_series_per_string", "sections", excel_row
            ),
            notes=clean_optional(row, "notes"),
        ))

    validate_unique(items, lambda s: s.section_id, "sections")
    return tuple(items)


def load_topology(params_file: Path) -> Topology:
    """Load array topology, or default to a single panel (1 wing x 1 panel) when
    the optional ``array_topology`` sheet is absent."""
    try:
        df = pd.read_excel(params_file, sheet_name="array_topology", index_col="param")
    except ValueError:
        return Topology(n_wings=1, n_panels_per_wing=1)
    return Topology(
        n_wings=int(df.loc["n_wings", "value"]),
        n_panels_per_wing=int(df.loc["n_panels_per_wing", "value"]),
    )


def load_panel_overrides(params_file: Path) -> tuple[PanelOverride, ...]:
    """Load panel-level overrides. Usually empty (symmetric arrays)."""
    try:
        df = pd.read_excel(params_file, sheet_name="panels")
    except ValueError:
        return ()  # sheet doesn't exist — no overrides

    df = df.dropna(subset=["panel_instance_id"])
    if df.empty:
        return ()

    items = []
    for idx, row in df.iterrows():
        excel_row = idx + 2
        action = str(row["action"]).strip()
        if action not in {"modify", "remove", "add"}:
            raise ValueError(
                f"panels:row {excel_row}: action='{action}' invalid. "
                f"Must be modify/remove/add."
            )
        items.append(PanelOverride(
            panel_instance_id=str(row["panel_instance_id"]).strip(),
            override_section_id=str(row["override_section_id"]).strip(),
            action=action,
            n_strings_parallel=optional_int(row, "n_strings_parallel"),
            n_sca_series_per_string=optional_int(row, "n_sca_series_per_string"),
            notes=clean_optional(row, "notes"),
        ))
    return tuple(items)


def _expand_to_physical(
    section_types: tuple[SectionType, ...],
    topology: Topology,
    overrides: tuple[PanelOverride, ...],
) -> tuple[PhysicalSection, ...]:
    """Multiply section templates across wings × panels, applying overrides."""
    physical = []
    for w in range(1, topology.n_wings + 1):
        wing_id = f"wing_{w}"
        for p in range(1, topology.n_panels_per_wing + 1):
            panel_id = f"{wing_id}.panel_{p}"

            # Start with the template, apply overrides
            for t in section_types:
                effective = _apply_overrides(t, panel_id, overrides)
                if effective is None:
                    continue  # action="remove"
                physical.append(PhysicalSection(
                    section_type=effective,
                    wing_id=wing_id,
                    panel_id=panel_id,
                    instance_id=f"{panel_id}.{effective.section_id}",
                ))

            # Then handle action="add" — new sections specific to this panel
            for ov in overrides:
                if ov.panel_instance_id == panel_id and ov.action == "add":
                    new_type = _section_type_from_override(ov)
                    physical.append(PhysicalSection(
                        section_type=new_type,
                        wing_id=wing_id,
                        panel_id=panel_id,
                        instance_id=f"{panel_id}.{new_type.section_id}",
                    ))

    return tuple(physical)


def _apply_overrides(
    section_type: SectionType,
    panel_id: str,
    overrides: tuple[PanelOverride, ...],
) -> SectionType | None:
    """Apply overrides for this panel. Returns None if action='remove'."""
    for ov in overrides:
        if ov.panel_instance_id != panel_id:
            continue
        if ov.override_section_id != section_type.section_id:
            continue
        if ov.action == "remove":
            return None
        if ov.action == "modify":
            return SectionType(
                section_id=section_type.section_id,
                section_name=section_type.section_name,
                n_strings_parallel=(
                    ov.n_strings_parallel
                    if ov.n_strings_parallel is not None
                    else section_type.n_strings_parallel
                ),
                n_sca_series_per_string=(
                    ov.n_sca_series_per_string
                    if ov.n_sca_series_per_string is not None
                    else section_type.n_sca_series_per_string
                ),
                notes=section_type.notes,
            )
        # action="add" handled separately
    return section_type


def _section_type_from_override(ov: PanelOverride) -> SectionType:
    """Build a brand-new SectionType from an action='add' override row."""
    if ov.n_strings_parallel is None or ov.n_sca_series_per_string is None:
        raise ValueError(
            f"panels: action='add' for '{ov.override_section_id}' on panel "
            f"'{ov.panel_instance_id}' requires both n_strings_parallel and "
            f"n_sca_series_per_string."
        )
    return SectionType(
        section_id=ov.override_section_id,
        section_name=ov.override_section_id,  # use id as name if no other source
        n_strings_parallel=ov.n_strings_parallel,
        n_sca_series_per_string=ov.n_sca_series_per_string,
        notes=ov.notes,
    )
