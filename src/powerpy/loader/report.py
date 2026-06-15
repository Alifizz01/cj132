"""The entry point that composes all loaders into a single ReportMetadata."""
from pathlib import Path

from powerpy.loader.cell import load_cell_parameters
from powerpy.loader.document import load_document_metadata
from powerpy.loader.fluxes import load_radiation_fluxes
from powerpy.loader.layout import load_array_layout
from powerpy.loader.losses import load_losses
from powerpy.loader.mission import load_mission_parameters
from powerpy.loader.structure import load_report_structure
from powerpy.schemas.report import ReportMetadata


def load_report_data(params_file: Path, data_dir: Path) -> ReportMetadata:
    """Load everything from params.xlsx into a typed, validated ReportMetadata.

    Args:
        params_file: Path to the params.xlsx workbook.
        data_dir: Base directory for resolving relative file paths
                  (cell JSONs, logo, etc.) referenced from the workbook.

    Returns:
        A fully populated ReportMetadata. All values are validated and
        immutable. Downstream code can trust every field.
    """
    if not params_file.exists():
        raise FileNotFoundError(f"params file not found: {params_file}")
    if not data_dir.exists():
        raise FileNotFoundError(f"data directory not found: {data_dir}")

    return ReportMetadata(
        document=load_document_metadata(params_file, data_dir),
        cell=load_cell_parameters(params_file, data_dir),
        mission=load_mission_parameters(params_file),
        array_layout=load_array_layout(params_file),
        losses=load_losses(params_file),
        radiation_fluxes=load_radiation_fluxes(params_file),
        structure=load_report_structure(params_file),
    )
