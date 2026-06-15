"""Load the ``requirement`` sheet -> :class:`Requirement`.

Key-value layout (``param | type | value`` plus separate ``*_unit`` rows), read
with the shared key-value loader. Returns ``None`` if the workbook has no
``requirement`` (or ``requirements``) sheet.
"""
from __future__ import annotations

from pathlib import Path

from powerpy.loader._common import load_keyvalue_sheet
from powerpy.schemas.requirement import Requirement

_SHEET_NAMES = ("requirement", "requirements")


def load_requirement(params_file: Path, data_dir: Path) -> Requirement | None:
    values = None
    for name in _SHEET_NAMES:
        try:
            values = load_keyvalue_sheet(params_file, name, data_dir)
            break
        except ValueError:
            continue                    # sheet not present under this name
    if not values:
        return None

    def num(key, default=0.0):
        v = values.get(key, default)
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    return Requirement(
        voltage_operating_v=num("voltage_operating"),
        eor_power_min_w=num("eor_power_min"),
        eol_power_min_w=num("eol_power_min"),
        max_section_current_a=num("max_section_current"),
        magnetic_moment_max=num("magnetic_moment_max"),
        sun_angle_deg=num("sun_angle"),
        flux_at_array_w_m2=num("flux_at_array"),
    )
