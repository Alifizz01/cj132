"""The root dataclass composing all loaded data."""
from dataclasses import dataclass, field

from powerpy.schemas.document import DocumentMetadata
from powerpy.schemas.cell import CellParameters
from powerpy.schemas.mission import MissionParameters
from powerpy.schemas.layout import ArrayLayout
from powerpy.schemas.losses import LossCollection
from powerpy.schemas.fluxes import RadiationFluxCollection
from powerpy.schemas.structure import ReportStructure
from powerpy.schemas.narrative import NarrativeBook


@dataclass(frozen=True)
class ReportMetadata:
    """Everything loaded from params.xlsx, fully typed and validated."""
    document: DocumentMetadata
    cell: CellParameters
    mission: MissionParameters
    array_layout: ArrayLayout
    losses: LossCollection
    radiation_fluxes: RadiationFluxCollection
    # structure & narrative are optional -- workbooks without the
    # sheets fall back to sane defaults.
    structure: ReportStructure = field(default_factory=ReportStructure.default)
    narrative: NarrativeBook = field(default_factory=NarrativeBook.empty)
