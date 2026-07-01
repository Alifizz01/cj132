"""The entry point that composes all loaders into a single ReportMetadata."""
from pathlib import Path

from powerpy.loader.cell import load_cell_parameters
from powerpy.loader.document import load_document_metadata
from powerpy.loader.fluxes import load_radiation_fluxes
from powerpy.loader.layout import load_array_layout
from powerpy.loader.losses import load_losses
from powerpy.loader.mission import load_mission_parameters, load_mission_orbit
from powerpy.loader.structure import load_report_structure
from powerpy.schemas.report import ReportMetadata


def load_report_data(params_file: Path, data_dir: Path,
                     *, scenario_file: Path | None = None) -> ReportMetadata:
    """Load everything into a typed, validated ReportMetadata.

    Args:
        params_file: The DESIGN workbook (cell + array layout) — or, in legacy
                     single-file mode, the whole params.xlsx.
        data_dir: Base directory for resolving relative file paths
                  (cell JSONs, logo, etc.) referenced from the workbook.
        scenario_file: The SCENARIO workbook (losses, mission, document,
                       structure, fluxes). Defaults to ``params_file`` — the
                       legacy single-file mode, byte-identical to before.

    Returns:
        A fully populated ReportMetadata. All values are validated and
        immutable. Downstream code can trust every field.
    """
    scenario_file = Path(scenario_file) if scenario_file else params_file
    if not params_file.exists():
        raise FileNotFoundError(f"design/params file not found: {params_file}")
    if not scenario_file.exists():
        raise FileNotFoundError(f"scenario file not found: {scenario_file}")
    if not data_dir.exists():
        raise FileNotFoundError(f"data directory not found: {data_dir}")

    return ReportMetadata(
        document=load_document_metadata(scenario_file, data_dir),
        cell=load_cell_parameters(params_file, data_dir),
        mission=load_mission_parameters(scenario_file),
        mission_orbit=load_mission_orbit(scenario_file, data_dir),
        array_layout=load_array_layout(params_file),
        losses=load_losses(scenario_file),
        radiation_fluxes=load_radiation_fluxes(scenario_file),
        structure=load_report_structure(scenario_file),
    )
