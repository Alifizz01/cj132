"""Analysis scope -- which configs the report should actually investigate.

The workbook's ``analysis`` sheet lists, one row per case, the exact
(launch, phase) combinations to evaluate and include in the report, together
with their operating conditions. This is the *scope* of the study: the report
contains exactly these cases, in this order.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class AnalysisConfig:
    """One row of the ``analysis`` sheet -- a single config to investigate."""
    launch: str             # launch config, e.g. "single" / "dual"
    phase: str              # mission phase, e.g. "End_of_Life"
    season: float           # irradiance multiplier vs AM0 (1367 W/m^2)
    temperature_c: float    # cell operating temperature [degC]
    string_loss: float = 1.0   # extra string-level current loss factor (1 = none)
    sun_angle_deg: float = 0.0  # off-pointing angle of the array normal [deg]
    v_operating: float | None = None  # bus operating voltage for compliance [V]

    @property
    def label(self) -> str:
        return f"{self.launch}@{self.phase}"


@dataclass(frozen=True)
class AnalysisScope:
    """The ordered set of configs to investigate (the whole ``analysis`` sheet)."""
    configs: Tuple[AnalysisConfig, ...] = ()

    def __iter__(self):
        return iter(self.configs)

    def __len__(self):
        return len(self.configs)

    def __bool__(self):
        return bool(self.configs)
