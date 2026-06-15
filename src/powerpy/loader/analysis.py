"""Load the ``analysis`` sheet -- the scope of configs to investigate.

Sheet schema (one row per config to include in the report)::

    launch | phase | season | temperature | string_loss | sun_angle | v_operating

``season`` may be a plain number or a ratio string like ``"1322/1367"`` (the
solar intensity at the analysis distance over AM0); both are parsed to a float.
If the workbook has no ``analysis`` sheet, an empty :class:`AnalysisScope` is
returned (and the report falls back to looping every phase).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from powerpy.schemas.analysis import AnalysisConfig, AnalysisScope


def _parse_season(raw) -> float:
    """A plain number, or an ``"a/b"`` ratio string, -> float."""
    if isinstance(raw, (int, float)) and not pd.isna(raw):
        return float(raw)
    s = str(raw).strip()
    if "/" in s:
        num, den = s.split("/", 1)
        return float(num) / float(den)
    return float(s)


def _opt_float(row, col):
    if col not in row or pd.isna(row[col]):
        return None
    return float(row[col])


def load_analysis_scope(params_file: Path) -> AnalysisScope:
    """Read the ``analysis`` sheet into an ordered :class:`AnalysisScope`.

    Returns an empty scope if the sheet is absent.
    """
    try:
        df = pd.read_excel(params_file, sheet_name="analysis")
    except ValueError:
        return AnalysisScope()          # sheet not present
    if df.empty:
        return AnalysisScope()

    configs = []
    for idx, row in df.iterrows():
        launch = row.get("launch")
        phase = row.get("phase")
        if launch is None or pd.isna(launch) or phase is None or pd.isna(phase):
            continue                    # skip blank rows
        configs.append(AnalysisConfig(
            launch=str(launch).strip(),
            phase=str(phase).strip(),
            season=_parse_season(row.get("season", 1.0)),
            temperature_c=float(row["temperature"]),
            string_loss=float(row["string_loss"]) if "string_loss" in row
                        and not pd.isna(row["string_loss"]) else 1.0,
            sun_angle_deg=float(row["sun_angle"]) if "sun_angle" in row
                          and not pd.isna(row["sun_angle"]) else 0.0,
            v_operating=_opt_float(row, "v_operating"),
        ))
    return AnalysisScope(tuple(configs))
