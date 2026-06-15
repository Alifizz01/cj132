"""Mission operating points indexed by launch config and phase.

The mission_param sheet is long-format (like losses and fluxes):
    name | launch_config | phase | value | unit | source | description | include

Each row represents a single operating point value (e.g., bus_voltage at 
a specific phase/launch_config). The collection supports lookup by 
phase + launch_config to retrieve all operating parameters.

Common parameter names:
- bus_voltage [V]        -- system bus voltage
- req_power [W]          -- power requirement
- predicted_power [W]    -- predicted array power
- delta_to_req [%]       -- margin to requirement
- pva_temperature [°C]   -- photovoltaic array temperature
"""
from dataclasses import dataclass

from powerpy.schemas._common import norm


@dataclass(frozen=True)
class MissionOperatingPoint:
    """A single mission parameter value at a specific phase/launch_config."""
    name: str
    launch_config: str
    phase: str
    value: float
    unit: str
    source: str = ""
    description: str = ""


@dataclass(frozen=True)
class MissionParameters:
    """Collection of mission operating points, queryable by phase and launch_config."""
    items: tuple[MissionOperatingPoint, ...]

    def by_phase(self, phase: str) -> "MissionParameters":
        return MissionParameters(
            tuple(p for p in self.items if norm(p.phase) == norm(phase))
        )

    def by_launch_config(self, lc: str) -> "MissionParameters":
        return MissionParameters(
            tuple(p for p in self.items if norm(p.launch_config) == norm(lc))
        )

    def by_name(self, name: str) -> "MissionParameters":
        return MissionParameters(
            tuple(p for p in self.items if norm(p.name) == norm(name))
        )

    def lookup(self, *, name: str, launch_config: str, phase: str) -> float:
        """Get the single operating point value matching all three keys (case-insensitive)."""
        matches = [
            p for p in self.items
            if norm(p.name) == norm(name)
            and norm(p.launch_config) == norm(launch_config)
            and norm(p.phase) == norm(phase)
        ]
        if not matches:
            raise KeyError(
                f"No mission parameter found for "
                f"name={name}, launch_config={launch_config}, phase={phase}"
            )
        if len(matches) > 1:
            raise ValueError(
                f"Multiple mission parameters found for "
                f"name={name}, launch_config={launch_config}, phase={phase}"
            )
        return matches[0].value

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __bool__(self):
        return bool(self.items)


@dataclass(frozen=True)
class MissionOrbit:
    """Key-value ``mission_orbit`` sheet: orbit + environment parameters.

    Holds the raw param->value map (nothing is dropped) and exposes typed
    accessors for the values the power budget and thermal solve need.  Optical
    environment params absent from the workbook fall back to documented LEO/Earth
    defaults.

    The ``params`` dict is held by reference (not copied or deep-frozen); callers must not mutate it.
    """
    params: dict[str, object]

    def get(self, key: str, default=None):
        return self.params.get(key, default)

    @property
    def altitude_km(self) -> float:
        if "altitude_km" not in self.params:
            raise KeyError("mission_orbit: 'altitude_km' is required")
        return float(self.params["altitude_km"])

    @property
    def sun_intensity_eol_min(self) -> float:
        return float(self.params.get("sun_intensity_eol_min", 1367.0))

    @property
    def sun_intensity_bol(self) -> float:
        return float(self.params.get("sun_intensity_bol", 1367.0))

    @property
    def bond_albedo(self) -> float:
        return float(self.params.get("bond_albedo", 0.30))

    @property
    def planet_temp_k(self) -> float:
        return float(self.params.get("planet_temp_k", 255.0))

    @property
    def ir_emissivity(self) -> float:
        return float(self.params.get("ir_emissivity", 1.0))
