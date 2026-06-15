"""Shared helpers used by every loader.

Two conventions are supported:

1. Key-value sheets: schema `param | name | value | unit | type | source`
   Loaded via `load_keyvalue_sheet()`.

2. Long-format sheets: schema `<identifiers> | value | <context> | description | source | include`
   Loaded via per-sheet loaders that call these primitives:
   - validate_required_columns
   - filter_included
   - parse_enum
   - require_float
   - require_float_in_range
   - validate_unique
   - clean_optional
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Hashable, TypeVar

import pandas as pd

T = TypeVar("T")


# -------------------------------------------------------------------
# Key-value sheets
# -------------------------------------------------------------------

def load_keyvalue_sheet(
    params_file: Path,
    sheet_name: str,
    data_dir: Path,
) -> dict[str, Any]:
    """Load a key-value sheet, parsing each value according to its `type` column.

    Returns a dict mapping `param` → parsed value.
    Section header rows (where `type` is empty) are skipped automatically.
    """
    df = pd.read_excel(params_file, sheet_name=sheet_name)
    df = df.dropna(subset=["param", "type"])  # skip section headers / blank rows

    values: dict[str, Any] = {}
    for idx, row in df.iterrows():
        excel_row = idx + 2  # +1 for 0-indexing, +1 for header row
        param = str(row["param"]).strip()
        type_ = str(row["type"]).strip()
        raw = row["value"]

        values[param] = _parse_typed_value(
            raw, type_, sheet_name, excel_row, param, data_dir
        )
    return values


def _parse_typed_value(
    raw: Any,
    type_: str,
    sheet: str,
    excel_row: int,
    param: str,
    data_dir: Path,
) -> Any:
    """Parse a single value according to the declared type."""
    if pd.isna(raw) or (isinstance(raw, str) and raw.strip() == ""):
        if type_ == "string":
            return ""
        raise ValueError(
            f"{sheet}:row {excel_row}: '{param}' has empty value but type='{type_}'"
        )

    if type_ == "string":
        return str(raw).strip()
    if type_ == "int":
        return int(raw)
    if type_ == "float":
        return float(raw)
    if type_ == "bool":
        return to_bool(raw)
    if type_ == "date":
        return to_date(raw)
    if type_ == "path":
        return (data_dir / str(raw).strip()).resolve()
    raise ValueError(
        f"{sheet}:row {excel_row}: unknown type '{type_}' for param '{param}'"
    )


# -------------------------------------------------------------------
# Long-format sheets — building blocks
# -------------------------------------------------------------------

def validate_required_columns(
    df: pd.DataFrame,
    sheet_name: str,
    required: set[str],
) -> None:
    """Raise if any required column is missing from the DataFrame."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Sheet '{sheet_name}' is missing required columns: {sorted(missing)}"
        )


def _is_included(v: Any) -> bool:
    """Per-cell truthiness for an `include` column, robust to how Excel/pandas
    surface the value: bool, int/float (0/1), or string ('TRUE'/'true'/'yes'/
    'x'/'1', with surrounding whitespace).  Blank / NaN / None -> False.
    """
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, float) and pd.isna(v):
        return False
    if isinstance(v, (int, float)):
        return bool(v)
    return str(v).strip().upper() in {"TRUE", "1", "YES", "Y", "X"}


def filter_included(df: pd.DataFrame, sheet_name: str = "") -> pd.DataFrame:
    """Keep only rows where the `include` column is truthy.

    Robust to whitespace/case/numeric encodings (see :func:`_is_included`).
    If a sheet has rows but *none* are included, that is almost always a
    mistake (e.g. a blank or mis-typed `include` column silently dropping the
    whole sheet), so we raise rather than return an empty-but-"valid" result.
    """
    if "include" not in df.columns:
        return df
    mask = df["include"].map(_is_included)
    out = df[mask].copy()
    if len(df) > 0 and len(out) == 0:
        where = sheet_name or "sheet"
        raise ValueError(
            f"{where}: has {len(df)} row(s) but none are included -- check the "
            f"'include' column (expected TRUE/FALSE)."
        )
    return out


def require_str(row: pd.Series, col: str, sheet: str, excel_row: int) -> str:
    """Require a non-empty string label (phase, launch_config, type, ...).

    These vocabularies are project-defined, so the value is taken as-is
    (stripped) -- no fixed enum to validate against, only non-emptiness.
    """
    val = row[col] if col in (row.index if hasattr(row, "index") else row) else None
    if val is None or pd.isna(val) or str(val).strip() == "":
        raise ValueError(f"{sheet}:row {excel_row}: '{col}' is empty")
    return str(val).strip()


def require_float(
    row: pd.Series,
    col: str,
    sheet: str,
    excel_row: int,
) -> float:
    """Require a non-empty float in the given column."""
    val = row[col]
    if pd.isna(val):
        raise ValueError(f"{sheet}:row {excel_row}: '{col}' is empty")
    return float(val)


def require_float_in_range(
    row: pd.Series,
    col: str,
    sheet: str,
    excel_row: int,
    *,
    lo: float,
    hi: float,
) -> float:
    """Require a float in the open-closed range (lo, hi]."""
    val = require_float(row, col, sheet, excel_row)
    if not lo < val <= hi:
        raise ValueError(
            f"{sheet}:row {excel_row}: '{col}'={val} out of range ({lo}, {hi}]"
        )
    return val


def require_positive_int(
    row: pd.Series,
    col: str,
    sheet: str,
    excel_row: int,
) -> int:
    """Require a positive integer (>= 1)."""
    val = row[col]
    if pd.isna(val):
        raise ValueError(f"{sheet}:row {excel_row}: '{col}' is empty")
    val_int = int(val)
    if val_int < 1:
        raise ValueError(
            f"{sheet}:row {excel_row}: '{col}'={val_int} must be >= 1"
        )
    return val_int


def validate_unique(
    items: tuple[T, ...] | list[T],
    key_fn: Callable[[T], Hashable],
    sheet_name: str,
) -> None:
    """Raise if two items share the same composite key."""
    seen: dict[Hashable, int] = {}
    for i, item in enumerate(items):
        key = key_fn(item)
        if key in seen:
            raise ValueError(
                f"{sheet_name}: duplicate key {key} "
                f"(at items index {seen[key]} and {i})"
            )
        seen[key] = i


def require_keyvalue(values: dict, key: str, sheet: str = "document") -> Any:
    """Return ``values[key]`` or raise if it is missing or blank.

    Use for key-value-sheet fields that are genuinely required, so a deleted
    or mis-typed key fails loud instead of silently defaulting.
    """
    if key not in values:
        raise ValueError(f"{sheet}: required key '{key}' is missing")
    val = values[key]
    if val is None or (isinstance(val, str) and not val.strip()):
        raise ValueError(f"{sheet}: required key '{key}' is missing or blank")
    return val


def clean_optional(row, col: str) -> str:
    """Return the column's value as a stripped string, or '' if missing/empty.

    Accepts either a pandas row (Series) or a key-value ``dict`` (as returned by
    :func:`load_keyvalue_sheet`) -- the document loader passes the latter.
    """
    keys = row.index if hasattr(row, "index") else row
    if col not in keys:
        return ""
    val = row[col]
    if pd.isna(val):
        return ""
    return str(val).strip()


# -------------------------------------------------------------------
# Type conversion helpers
# -------------------------------------------------------------------

def to_bool(raw: Any) -> bool:
    """Convert a cell value to bool. Handles strings, ints, and actual bools."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    return str(raw).strip().upper() == "TRUE"


def to_date(raw: Any) -> date:
    """Convert a cell value to a date. Accepts date, datetime, Timestamp, or ISO string."""
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if isinstance(raw, pd.Timestamp):
        return raw.date()
    return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
