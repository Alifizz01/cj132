"""The root dataclass composing all loaded data."""
from dataclasses import dataclass, field

from powerpy.schemas.document import DocumentMetadata
from powerpy.schemas.cell import CellParameters
from powerpy.schemas.mission import MissionParameters, MissionOrbit
from powerpy.schemas.layout import ArrayLayout
from powerpy.schemas.losses import LossCollection
from powerpy.schemas.fluxes import RadiationFluxCollection
from powerpy.schemas.structure import ReportStructure


@dataclass(frozen=True)
class ReportMetadata:
    """Everything loaded from params.xlsx, fully typed and validated."""
    document: DocumentMetadata
    cell: CellParameters
    mission: MissionParameters
    array_layout: ArrayLayout
    losses: LossCollection
    radiation_fluxes: RadiationFluxCollection
    # structure is optional -- a workbook without the sheet falls back to a
    # sane default.
    structure: ReportStructure = field(default_factory=ReportStructure.default)
    # mission_orbit is optional at the dataclass level: the loader always
    # supplies it, but hand-built metadata may omit it -- the analysis layer
    # falls back to a default GEO orbit when it is None.
    mission_orbit: MissionOrbit | None = None
