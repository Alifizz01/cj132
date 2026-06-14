"""Load document sheet (key-value format).

The ``document`` sheet is a simple key-value table with columns: key | value.
Common keys (all optional except indicated):
  - doc_title* : report title
  - project* : project code/name
  - doc_number* : document identifier
  - issued_date* : publication date (parsed as date)
  - classification* : security/privacy level
  - author* : primary author name
  - abstract : long-form summary (can span multiple cells in column B)
  - customer : customer name or code
  - contract_ref : contract reference
  - export_control : export control classification
"""
from pathlib import Path

from powerpy.loader._common import (
    load_keyvalue_sheet,
    clean_optional,
    require_keyvalue,
)
from powerpy.schemas.document import DocumentMetadata


def load_document_metadata(params_file: Path, data_dir: Path) -> DocumentMetadata:
    """Load document sheet (key-value format).

    The cover-identification fields are genuinely required: a deleted or
    mis-typed key fails loud rather than silently defaulting (e.g. an absent
    ``issued_date`` used to become *today's* date on the report).
    """
    values = load_keyvalue_sheet(params_file, "document", data_dir)

    return DocumentMetadata(
        doc_title=require_keyvalue(values, "doc_title"),
        project=require_keyvalue(values, "project"),
        doc_number=require_keyvalue(values, "doc_number"),
        issued_date=require_keyvalue(values, "issued_date"),
        logo_file=values.get("logo_file"),  # Path object from loader
        project_name=clean_optional(values, "project_name"),
        project_code=clean_optional(values, "project_code"),
        prepared_by=clean_optional(values, "prepared_by"),
        approved_by=clean_optional(values, "approved_by"),
    )
