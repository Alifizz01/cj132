"""Mission requirements -- what the array must satisfy.

The workbook's ``requirement`` sheet states the targets the analysis checks the
array against: the operating bus voltage, the minimum power at end-of-reach
(EOR) and end-of-life (EOL), the max section current, sun angle, flux at the
array, and the magnetic-moment limit. Without these the report can show the
array's output but cannot judge compliance.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Requirement:
    """Mission requirement targets (from the ``requirement`` sheet)."""
    voltage_operating_v: float          # bus operating voltage [V]
    eor_power_min_w: float              # minimum power at end-of-reach [W]
    eol_power_min_w: float              # minimum power at end-of-life [W]
    max_section_current_a: float = 0.0  # max current per section [A]
    magnetic_moment_max: float = 0.0    # magnetic-moment limit [Am^2]
    sun_angle_deg: float = 0.0          # worst-case sun angle [deg]
    flux_at_array_w_m2: float = 0.0     # solar flux at the array [W/m^2]

    def power_min_for_phase(self, phase: str) -> float:
        """The binding minimum power for a phase name: EOL phases use
        ``eol_power_min_w``; everything else uses ``eor_power_min_w``."""
        p = (phase or "").lower()
        if "life" in p or "eol" in p:
            return self.eol_power_min_w
        return self.eor_power_min_w
