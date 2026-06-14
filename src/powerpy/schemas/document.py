"""Document cover metadata.

Excel sheet: ``document`` (key-value format)
  ├─ doc_title: report title
  ├─ project: project code/name
  ├─ doc_number: document identifier
  ├─ issued_date: publication date
  ├─ classification: security level
  ├─ author: primary author name
  └─ abstract: summary text

Optional fields (with defaults):
  ├─ customer
  ├─ contract_ref
  ├─ export_control
  └─ logo_file
"""
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class DocumentMetadata:
    """Document-level metadata loaded from ``document`` sheet (key-value format)."""

    # core identification
    doc_title: str          # report title
    project: str            # project code or name
    doc_number: str         # document identifier (e.g., "TN-G2G-PVA-001")
    issued_date: date       # publication date

    # title-block extras
    project_name: str = ""
    project_code: str = ""
    prepared_by: str = ""
    approved_by: str = ""

    # rendering hint (not typically in workbook, set programmatically)
    logo_file: Path | None = None
