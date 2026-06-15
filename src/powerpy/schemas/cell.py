"""Solar cell parameters from Excel + electrical params from JSON."""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CellElectrical:
    """Loaded from the referenced JSON file."""
    isc_bol: float          # A
    voc_bol: float          # V
    imp_bol: float          # A
    vmp_bol: float          # V
    temp_coeff_isc: float   # %/°C
    temp_coeff_voc: float   # %/°C
    # degradation: fluence (e/cm²) → factor — keyed by parameter name
    degradation: dict = field(default_factory=dict)
    # radiation / temperature-coefficient regressor curves vs Dose [%]:
    # {name: {"dose": [...], "value": [...]}} for r_isc/r_imp/r_vmp/r_voc
    # (remaining-factor) and isc_dt/imp_dt/vmp_dt/voc_dt (temp coefficients).
    regressors: dict = field(default_factory=dict)
    # legacy "Cell parameters" extras (reference report Table 2) — optical/
    # thermal absorptance & emittance, interconnect resistance, reference
    # temperature and active area.  Defaulted so older JSONs still load.
    alpha: float = 0.0          # solar absorptance [-]
    epsilon: float = 0.0        # IR emittance [-]
    r_interconnect: float = 0.0  # interconnect series resistance [Ohm]
    t_ref: float = 28.0         # reference temperature [°C]
    area_m2: float = 0.0        # active cell area [m²]

    def __post_init__(self):
        for name in ("isc_bol", "voc_bol", "imp_bol", "vmp_bol"):
            v = getattr(self, name)
            if v <= 0:
                raise ValueError(f"CellElectrical.{name} must be > 0, got {v}")
        if self.imp_bol > self.isc_bol:
            raise ValueError(
                f"CellElectrical: imp_bol ({self.imp_bol}) cannot exceed "
                f"isc_bol ({self.isc_bol})")
        if self.vmp_bol > self.voc_bol:
            raise ValueError(
                f"CellElectrical: vmp_bol ({self.vmp_bol}) cannot exceed "
                f"voc_bol ({self.voc_bol})")
        if not 0.0 <= self.alpha <= 1.0:
            raise ValueError(f"CellElectrical.alpha must be in [0, 1], got {self.alpha}")
        if not 0.0 <= self.epsilon <= 1.0:
            raise ValueError(f"CellElectrical.epsilon must be in [0, 1], got {self.epsilon}")
        if self.r_interconnect < 0:
            raise ValueError(f"CellElectrical.r_interconnect must be >= 0, got {self.r_interconnect}")
        if self.area_m2 < 0:
            raise ValueError(f"CellElectrical.area_m2 must be >= 0, got {self.area_m2}")


@dataclass(frozen=True)
class ShuntDiodeParameters:
    """Shunt (bypass) diode parameters — reference report Table 3.

    Loaded from the cell's ``diode_reference_file`` JSON.  Defaulted fields so
    a minimal/legacy diode JSON still loads.
    """
    name: str = ""
    reference: str = ""
    i0: float = 0.0     # saturation current [A]
    n: float = 1.0      # ideality / number of diodes [-]
    rs: float = 0.0     # series resistance [Ohm]
    t_ref: float = 25.0  # reference temperature [°C]
    v_forward: float = 0.7  # forward conduction drop [V] (used as the clamp level)


@dataclass(frozen=True)
class CellParameters:
    # identity
    name: str
    manufacturer: str

    # materials
    base_material: str
    junction: str
    ar_coating: str
    front_contact: str
    rear_contact: str
    substrate_material: str

    # geometry (units in field names — no ambiguity)
    cell_length_mm: float
    cell_width_mm: float
    cell_thickness_um: float
    substrate_thickness_um: float
    cell_area_cm2: float
    cell_mass_mg: float

    # file references (resolved paths)
    reference_file: Path
    diode_reference_file: Path

    # electrical (loaded from JSON)
    electrical: CellElectrical

    # CELL-level shunt diode (loaded from the cell_shunt_diode_reference_file JSON)
    diode: ShuntDiodeParameters | None = None

    # STRING-level shunt/bypass diode -- a real string carries its own shunt
    # diode (across the string) in addition to the per-cell one. Loaded from
    # ``string_shunt_diode_reference_file`` when the workbook provides it.
    string_diode: ShuntDiodeParameters | None = None
    string_diode_reference_file: Path | None = None

    # optional grid layout JSON whose cell tiles carry string/block tags; when
    # set, the electrical circuit is DERIVED from it (grid-as-single-source).
    grid_reference_file: Path | None = None

    def __post_init__(self):
        for name in ("cell_length_mm", "cell_width_mm", "cell_thickness_um",
                     "substrate_thickness_um", "cell_area_cm2", "cell_mass_mg"):
            v = getattr(self, name)
            if v <= 0:
                raise ValueError(f"CellParameters.{name} must be > 0, got {v}")

    @property
    def cell_area_m2(self) -> float:
        return self.cell_area_cm2 * 1e-4

    @property
    def cell_mass_kg(self) -> float:
        return self.cell_mass_mg * 1e-6
