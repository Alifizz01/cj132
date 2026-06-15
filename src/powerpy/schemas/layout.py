"""Solar array hierarchy: section types, topology, panel overrides, full layout."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SectionType:
    """A section template — describes one panel's worth of one section."""
    section_id: str
    section_name: str
    n_strings_parallel: int
    n_sca_series_per_string: int
    notes: str = ""

    def __post_init__(self):
        if self.n_strings_parallel < 1:
            raise ValueError(
                f"SectionType.n_strings_parallel must be >= 1, "
                f"got {self.n_strings_parallel}")
        if self.n_sca_series_per_string < 1:
            raise ValueError(
                f"SectionType.n_sca_series_per_string must be >= 1, "
                f"got {self.n_sca_series_per_string}")

    @property
    def n_sca_per_section(self) -> int:
        return self.n_strings_parallel * self.n_sca_series_per_string


@dataclass(frozen=True)
class Topology:
    """How section templates are multiplied across the array."""
    n_wings: int
    n_panels_per_wing: int

    def __post_init__(self):
        if self.n_wings < 1:
            raise ValueError(f"Topology.n_wings must be >= 1, got {self.n_wings}")
        if self.n_panels_per_wing < 1:
            raise ValueError(
                f"Topology.n_panels_per_wing must be >= 1, "
                f"got {self.n_panels_per_wing}")

    @property
    def n_panels_total(self) -> int:
        return self.n_wings * self.n_panels_per_wing


@dataclass(frozen=True)
class PhysicalSection:
    """A concrete instance: a section type placed on a specific panel/wing,
    with its own harness resistance (varies with distance from the yoke)."""
    section_type: SectionType
    wing_id: str
    panel_id: str
    instance_id: str
    resistance_ohm: float = 0.0

    @property
    def n_sca(self) -> int:
        return self.section_type.n_sca_per_section


@dataclass(frozen=True)
class ArrayLayout:
    """Full array layout — section templates, topology, and expanded physical sections."""
    section_types: tuple[SectionType, ...]
    topology: Topology
    physical_sections: tuple[PhysicalSection, ...]

    @property
    def n_sections_total(self) -> int:
        return len(self.physical_sections)

    @property
    def n_sca_total(self) -> int:
        return sum(s.n_sca for s in self.physical_sections)

    @property
    def n_strings_total(self) -> int:
        return sum(s.section_type.n_strings_parallel for s in self.physical_sections)

    def by_panel(self, panel_id: str) -> tuple[PhysicalSection, ...]:
        return tuple(s for s in self.physical_sections if s.panel_id == panel_id)

    def by_wing(self, wing_id: str) -> tuple[PhysicalSection, ...]:
        return tuple(s for s in self.physical_sections if s.wing_id == wing_id)
