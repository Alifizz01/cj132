# -*- coding: utf-8 -*-
"""Result storage and presentation for a Monte-Carlo sweep.

A sweep produces, for every run x every cell, a row of numbers. We store that as
a TIDY / LONG table (one row per run-cell) in a compact columnar binary file
(Parquet, or HDF5) as the source of truth, and generate an Excel summary and
aggregations (heat-maps, histograms, rankings) ON TOP of it.

Excel is intentionally NOT the primary store: a per-run x per-cell tensor passes
Excel's ~1.05M-row limit quickly and is slow as a database.

Status: DataFrame assembly & summaries use pandas (available) and are tested;
Parquet/HDF5/Excel writers are thin wrappers guarded on their optional engines
(pyarrow / pytables / openpyxl).
"""
from __future__ import annotations

from typing import Dict, List, Sequence

LONG_COLUMNS = [
    "run_id", "mode", "failed_ids", "cell_id",
    "V", "I", "P_elec", "T_front", "T_rear",
    "reverse_flag", "hotspot_flag",
]


def records_to_long_rows(records: Sequence[Dict]) -> List[Dict]:
    """Flatten per-run records (each holding per-cell arrays/lists) into rows.

    Each record is expected to have ``run_id``, ``mode``, ``failed_ids`` and a
    ``cells`` list of dicts with the per-cell fields. Missing fields default to None.
    """
    rows: List[Dict] = []
    for rec in records:
        base = {
            "run_id": rec.get("run_id"),
            "mode": rec.get("mode"),
            "failed_ids": rec.get("failed_ids"),
        }
        for cell in rec.get("cells", []):
            row = dict(base)
            row["cell_id"] = cell.get("cell_id")
            for k in ("V", "I", "P_elec", "T_front", "T_rear", "reverse_flag", "hotspot_flag"):
                row[k] = cell.get(k)
            rows.append(row)
    return rows


def to_dataframe(records: Sequence[Dict]):
    """Build the long-format pandas DataFrame (source of truth)."""
    import pandas as pd
    rows = records_to_long_rows(records)
    df = pd.DataFrame(rows, columns=LONG_COLUMNS)
    return df


def save(df, path: str) -> str:
    """Persist the long table. ``.parquet`` -> Parquet, ``.h5`` -> HDF5, else CSV."""
    if path.endswith(".parquet"):
        df.to_parquet(path)            # needs pyarrow/fastparquet
    elif path.endswith(".h5") or path.endswith(".hdf5"):
        df.to_hdf(path, key="results", mode="w")  # needs pytables
    else:
        df.to_csv(path, index=False)
    return path


def summarise(df):
    """Per-run aggregates: total power, max temperature, hot-spot count."""
    import pandas as pd  # noqa: F401
    g = df.groupby("run_id")
    out = g.agg(
        total_power=("P_elec", "sum"),
        max_temp_c=("T_front", "max"),
        n_hotspots=("hotspot_flag", "sum"),
        n_cells=("cell_id", "count"),
    ).reset_index()
    return out


def export_excel(summary_df, path: str, raw_df=None) -> str:
    """Write a human-facing Excel workbook (summary sheet, optional raw sheet)."""
    import pandas as pd
    with pd.ExcelWriter(path) as xl:    # needs openpyxl
        summary_df.to_excel(xl, sheet_name="summary", index=False)
        if raw_df is not None:
            raw_df.to_excel(xl, sheet_name="raw", index=False)
    return path
